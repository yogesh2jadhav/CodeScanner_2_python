"""Deterministic-first question classification.

Why rules first: most developer questions ("who calls X", "what does X depend
on") have unambiguous phrasing. Regex rules are instant, testable and work when
the LLM is down; the LLM is consulted only for low-confidence cases.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from codeknowledge.models.query import QueryCategory as C
from codeknowledge.retrieval.symbol import SymbolIndex, extract_symbols
from codeknowledge.utils.logging import get_logger

logger = get_logger("QueryClassifier")

Direction = Literal["in", "out"]


@dataclass
class Classification:
    category: C
    confidence: float
    method: str = "rules"  # rules | llm
    direction: Direction | None = None
    transitive: bool = False
    wants_explanation: bool = False
    symbols: list[str] = field(default_factory=list)  # resolved entity ids mentioned in the question
    matched_rule: str | None = None


_I = re.IGNORECASE
# (category, confidence, direction, pattern). Order matters: first match wins.
RULES: list[tuple[C, float, Direction | None, re.Pattern]] = [
    (C.PATH, 0.9, None, re.compile(r"\bpath\b.*\bfrom\b.*\bto\b|\bhow does .+ (reach|get to|lead to)\b|\bconnect(ed|ion)? between\b", _I)),
    (C.IMPACT_ANALYSIS, 0.9, "in", re.compile(r"\bimpact|\bwhat (would |will )?break|\bif i (change|modify|remove|delete)|\baffected by\b|\bripple|\bblast radius", _I)),
    (C.CALLERS, 0.9, "in", re.compile(r"\b(who|what|which\s+\w+)\s+(else\s+)?(calls|invokes|uses the method)\b|\bcallers? of\b|\bcalled (by|from)\b|\bwhere is .+ (called|invoked)\b|\busages? of\b|\bis .+ called\b", _I)),
    (C.CALLEES, 0.9, "out", re.compile(r"\bwhat (else )?(does|do) .+ (eventually |transitively |indirectly )?(call|invoke)s?\b|\bcallees? of\b|\bcalls made by\b|\bwhat is called by\b|\bwhich methods does .+ call\b|\bdoes .+ call\b", _I)),
    (C.DEPENDENCIES, 0.88, "out", re.compile(r"\bwhat (does|do) .+ (depend|rely) on\b|\bwhat does .+ use\b|\bdependenc(y|ies) of\b|\bimports? of\b", _I)),
    (C.DEPENDENCIES, 0.88, "in", re.compile(r"\b(what|which|who)\b.*\b(depend|depends|rely|relies) on\b|\bdependents of\b|\bwho uses\b|\bwhat uses\b|\bwhich classes use\b", _I)),
    (C.DEPENDENCIES, 0.85, "out", re.compile(r"\bdependenc(y|ies)\b", _I)),
    (C.ARCHITECTURE, 0.8, None, re.compile(r"\barchitecture\b|\bmodules?\b|\blayers?\b|\bpackage structure\b|\bhigh[- ]level overview\b|\bcomponents?\b.*\b(system|application)\b|\binheritance hierarch", _I)),
    (C.BUSINESS_RULE, 0.8, None, re.compile(r"\bbusiness rules?\b|\brules?\b.*\b(for|in|of|applied)\b|\bunder what conditions?\b|\bwhat conditions?\b|\bwhen (is|are|does) .+ (set|rejected|approved|valid|invalid|eligible)\b|\bvalidation (logic|rules)\b|\beligib", _I)),
    (C.FLOW, 0.85, None, re.compile(r"\bflows?\b|\bexecution path\b|\bcontrol flow\b|\bsequence of (calls|steps)\b|\bstep[- ]by[- ]step\b|\bwhat happens (when|if|in|during)\b|\bwalk me through\b", _I)),
    (C.FUNCTIONAL_EXPLANATION, 0.85, None, re.compile(r"\bwhat (does|do|is) .+ (do|for|responsible)\b|\bexplain\b|\bdescribe\b|\bpurpose of\b|\bresponsibilit|\bhow (is|are|does) .+ (calculated|computed|determined|derived|assigned|set|work|handled|implemented)\b", _I)),
    (C.SEMANTIC_SEARCH, 0.75, None, re.compile(r"\bwhere (is|are|do|does)\b|\bwhich (code|class|method|file)s?\b|\bfind\b|\bsearch\b|\blocate\b|\bshow me\b", _I)),
]

_EXPLAIN_RE = re.compile(r"\bexplain|\bwhy\b|\bdescribe|\bsummar|\bwhat does .+ do\b", _I)
_TRANSITIVE_RE = re.compile(r"\beventually|\btransitive|\bindirect|\ball the way|\bchain\b|\bdownstream|\bupstream|\bentire\b|\bfull\b", _I)
_ONLY_SYMBOL_RE = re.compile(r"^\s*`?[A-Za-z_$][\w$]*(?:[.#][A-Za-z_$][\w$]*)*(?:\(\))?`?\s*\??\s*$")


class QueryClassifier:
    def __init__(self, symbols: SymbolIndex | None = None, llm=None, threshold: float = 0.6):
        self.symbols = symbols
        self.llm = llm
        self.threshold = threshold

    def _resolve(self, question: str) -> list[str]:
        if not self.symbols:
            return []
        return [h.entity_id for h in self.symbols.resolve_question(question)]

    def classify_rules(self, question: str) -> Classification:
        q = question.strip()
        symbols = self._resolve(q)
        transitive = bool(_TRANSITIVE_RE.search(q))
        explain = bool(_EXPLAIN_RE.search(q))

        if _ONLY_SYMBOL_RE.match(q):
            cat = C.CLASS_LOOKUP
            if symbols and self.symbols:
                doc = self.symbols.repo.get(symbols[0])
                if doc and doc.type.value in ("method", "field"):
                    cat = C.METHOD_LOOKUP
            elif extract_symbols(q) and "." in q and q.split(".")[-1][:1].islower():
                cat = C.METHOD_LOOKUP
            return Classification(cat, 0.95 if symbols else 0.7, symbols=symbols, matched_rule="bare_symbol",
                                  transitive=transitive)

        for cat, conf, direction, pattern in RULES:
            if pattern.search(q):
                # Structural questions need a concrete target; without one we are less sure.
                needs_target = cat in (C.CALLERS, C.CALLEES, C.DEPENDENCIES, C.IMPACT_ANALYSIS, C.PATH)
                if needs_target and not symbols:
                    conf = min(conf, 0.55)
                return Classification(cat, conf, direction=direction, transitive=transitive,
                                      wants_explanation=explain, symbols=symbols, matched_rule=pattern.pattern[:40])
        return Classification(C.GENERAL, 0.3, transitive=transitive, wants_explanation=True, symbols=symbols)

    def classify(self, question: str) -> Classification:
        result = self.classify_rules(question)
        if result.confidence < self.threshold and self.llm is not None:
            try:
                llm_cat = self._classify_llm(question)
                if llm_cat is not None:
                    result.category, result.method, result.confidence = llm_cat, "llm", max(result.confidence, self.threshold)
            except Exception as exc:  # LLM is optional for classification
                logger.warning("LLM classification failed, keeping rule result: %s", exc)
        logger.info("QUERY_CLASSIFIED category=%s confidence=%.2f method=%s symbols=%d",
                    result.category.value, result.confidence, result.method, len(result.symbols))
        return result

    def _classify_llm(self, question: str) -> C | None:
        from codeknowledge.llm.prompts import classification_prompt

        text = self.llm.generate(classification_prompt(question), system=None).upper()
        for cat in C:
            if re.search(rf"\b{cat.value}\b", text):
                return cat
        return None
