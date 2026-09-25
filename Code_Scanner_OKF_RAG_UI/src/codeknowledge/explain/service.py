"""MethodExplanationService: orchestration only (evidence -> budget -> cache -> prompt -> LLM -> validate)."""
from __future__ import annotations

import json
import time

from codeknowledge.explain.budget import EvidenceBudgetManager
from codeknowledge.explain.evidence import MethodEvidenceBuilder
from codeknowledge.explain.models import (EvidencePackage, ExplainOptions, LLMExplanation, MethodExplanationResponse,
                                          ModelMetadata, ValidationReport)
from codeknowledge.explain.prompt import SYSTEM_PROMPT, MethodExplanationPromptBuilder, schema
from codeknowledge.explain.render import to_markdown
from codeknowledge.explain.validator import ExplanationResponseValidator, parse
from codeknowledge.llm.provider import LLMProvider, LLMUnavailableError
from codeknowledge.services.cache_service import AnswerCache
from codeknowledge.services.indexing_service import KnowledgeBase
from codeknowledge.utils.ids import new_request_id, stable_hash, strip_kind_prefix
from codeknowledge.utils.logging import get_logger, request_id_var
from codeknowledge.utils.timing import Timings, timed

logger = get_logger("MethodExplanation")


class ExplanationDisabledError(RuntimeError):
    pass


class MethodExplanationService:
    def __init__(self, kb: KnowledgeBase, llm: LLMProvider | None, cache: AnswerCache | None = None):
        self.kb = kb
        self.llm = llm
        self.cache = cache
        self.cfg = kb.settings.method_explanation

    # ---------------------------------------------------------------- utils
    def budget_tokens(self) -> int:
        """Reconcile the configured budget with the model's context window minus the output reserve."""
        num_ctx = getattr(self.llm, "num_ctx", None) or self.kb.settings.llm.num_ctx
        return max(1500, min(self.cfg.max_context_tokens, num_ctx - self.cfg.output_token_reserve))

    def _cache_key(self, pkg: EvidencePackage, opts: ExplainOptions, version: str) -> str:
        llm = self.kb.settings.llm
        fingerprint = stable_hash(*(f"{i.evidence_id}|{i.kind}|{i.status}|{i.content}" for i in pkg.items))
        parts = {
            "bundle": self.kb.repo.bundle_hash, "method": pkg.method_id,
            "options": opts.model_dump(exclude={"force_refresh"}),
            "budget": [self.cfg.max_callee_depth, self.cfg.max_callees_per_method, self.cfg.max_evidence_documents,
                       self.budget_tokens(), self.cfg.chars_per_token],
            "model": [getattr(self.llm, "name", "none"), getattr(self.llm, "model", "none"), llm.num_ctx, llm.temperature],
            "prompt": version, "evidence": fingerprint,
        }
        return "explain-" + stable_hash(json.dumps(parts, sort_keys=True, default=str))

    def _generate(self, prompt: str, report: ValidationReport) -> tuple[LLMExplanation | None, list[str]]:
        """One call plus at most max_repair_attempts repairs driven by the validation errors."""
        raw = self.llm.generate_json(prompt, SYSTEM_PROMPT, schema())
        exp, errors = parse(raw)
        while exp is None and report.repair_attempts < self.cfg.max_repair_attempts:
            report.repair_attempts += 1
            logger.warning("EXPLAIN_REPAIR attempt=%d errors=%d", report.repair_attempts, len(errors))
            raw = self.llm.generate_json(MethodExplanationPromptBuilder.repair(prompt, errors), SYSTEM_PROMPT, schema())
            exp, errors = parse(raw)
        return exp, errors

    # ----------------------------------------------------------------- main
    def explain(self, method_id: str, opts: ExplainOptions, request_id: str | None = None,
                use_llm: bool = True) -> MethodExplanationResponse:
        if not self.cfg.enabled:
            raise ExplanationDisabledError("Method explanation is disabled (method_explanation.enabled=false).")
        request_id = request_id or request_id_var.get() or new_request_id()
        start = time.perf_counter()
        timings = Timings()
        logger.info("EXPLAIN_REQUEST method=%s detail=%s depth=%s", strip_kind_prefix(method_id)[:200],
                    opts.detail, opts.max_callee_depth)

        with timed(logger, "evidence_build", timings):
            pkg, facts = MethodEvidenceBuilder(self.kb, self.cfg).build(method_id, opts)
        with timed(logger, "budget", timings):
            pkg = EvidenceBudgetManager(self.budget_tokens(), self.cfg.chars_per_token,
                                        self.cfg.max_evidence_documents).apply(pkg)
        counts: dict[str, int] = {}
        for i in pkg.items:
            counts[f"{i.kind}:{i.status}"] = counts.get(f"{i.kind}:{i.status}", 0) + 1
        logger.info("EVIDENCE_READY items=%d by_kind=%s source=%s omitted=%d est_tokens=%d segments=%d",
                    len(pkg.items), counts, pkg.source_available, len(pkg.omitted), pkg.estimated_tokens, pkg.segments)

        builder = MethodExplanationPromptBuilder(opts.detail)
        resp = MethodExplanationResponse(
            request_id=request_id, method_id=pkg.method_id, method_signature=pkg.method_signature,
            method_title=pkg.method_title, evidence=pkg.items, facts=facts, warnings=list(pkg.warnings),
            estimated_prompt_tokens=pkg.estimated_tokens)
        if not use_llm or self.llm is None:
            resp.warnings.append("Evidence only: the model was not called.")
            resp.timings_ms = {**timings, "total": round((time.perf_counter() - start) * 1000, 2)}
            return resp
        resp.model = ModelMetadata(provider=self.llm.name, model=self.llm.model, prompt_version=builder.version,
                                   num_ctx=getattr(self.llm, "num_ctx", None))

        key = self._cache_key(pkg, opts, builder.version)
        if self.cache and self.cfg.cache_enabled and not opts.force_refresh:
            hit = self.cache.get(key, self.kb.repo.bundle_hash)
            if hit:
                cached = MethodExplanationResponse.model_validate(hit["response"])
                cached.request_id, cached.cached = request_id, True
                cached.timings_ms = {"cache": round((time.perf_counter() - start) * 1000, 2)}
                logger.info("EXPLAIN_CACHE hit")
                return cached
            logger.info("EXPLAIN_CACHE miss")

        report = ValidationReport(valid=False)
        explanation: LLMExplanation | None = None
        errors: list[str] = []
        try:
            if pkg.segments > 1:
                explanation, errors = self._explain_segments(pkg, builder, report, timings)
            else:
                with timed(logger, "prompt_build", timings):
                    prompt = builder.build(pkg)
                if self.cfg.debug_prompt_logging:
                    logger.debug("EXPLAIN_PROMPT (truncated): %s", prompt[:2000])
                logger.info("LLM_STARTED model=%s est_prompt_tokens=%d", self.llm.model, pkg.estimated_tokens)
                with timed(logger, "llm", timings):
                    explanation, errors = self._generate(prompt, report)
        except LLMUnavailableError:
            logger.warning("EXPLAIN_LLM_FAILED", exc_info=True)
            raise

        with timed(logger, "validation", timings):
            if explanation is None:
                report.errors = errors
                resp.warnings.append("The model did not return a valid explanation after "
                                     f"{report.repair_attempts} repair attempt(s); showing evidence only.")
            else:
                explanation, vreport, vwarnings = ExplanationResponseValidator(
                    pkg, self.cfg.validate_citations).validate(explanation)
                vreport.repair_attempts = report.repair_attempts
                report = vreport
                resp.warnings.extend(vwarnings)
        resp.explanation = explanation
        resp.validation = report
        if explanation is not None:
            resp.markdown = to_markdown(explanation, pkg, resp.warnings)
        resp.timings_ms = {**timings, "total": round((time.perf_counter() - start) * 1000, 2)}
        logger.info("EXPLAIN_DONE valid=%s repairs=%d refs_removed=%d ungrounded=%d total_ms=%s",
                    report.valid, report.repair_attempts, report.invalid_refs_removed, report.ungrounded_items,
                    resp.timings_ms["total"])
        if explanation is not None and self.cache and self.cfg.cache_enabled:
            self.cache.put(key, pkg.method_id, self.kb.repo.bundle_hash, resp.model_dump(mode="json"))
        return resp

    def _explain_segments(self, pkg, builder, report, timings):
        """Explain an oversized body part by part (source order), then merge deterministically."""
        segments = [i for i in pkg.items if i.kind == "source_segment"]
        merged: LLMExplanation | None = None
        errors: list[str] = []
        for n, seg in enumerate(segments, 1):
            offset = len(merged.execution_steps) if merged else 0
            prompt = builder.build(pkg, segment=seg, segment_index=n, step_offset=offset)
            with timed(logger, f"llm_segment_{n}", timings):
                part, errs = self._generate(prompt, report)
            if part is None:
                errors.extend(f"part {n}: {e}" for e in errs)
                continue
            for i, step in enumerate(part.execution_steps, offset + 1):
                step.step_number = i
            if merged is None:
                merged = part
                merged.uncertainties.append(f"Long method explained in {len(segments)} ordered parts.")
            else:
                for field in ("inputs_outputs", "execution_steps", "branches", "data_transformations", "calls",
                              "side_effects", "exceptions", "uncertainties"):
                    getattr(merged, field).extend(getattr(part, field))
        if merged is not None and errors:
            merged.uncertainties.append(f"{len(errors)} problem(s) while explaining some parts; those parts may be missing.")
        return merged, errors
