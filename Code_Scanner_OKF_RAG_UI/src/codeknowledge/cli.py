"""Command line interface: python -m codeknowledge <command>."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from codeknowledge.config.settings import load_settings
from codeknowledge.okf.loader import OKFLoader, OKFSourceMissingError
from codeknowledge.okf.validator import OKFValidator
from codeknowledge.utils.logging import setup_logging


def _cmd_validate(args, settings) -> int:
    source = args.input or settings.okf.source_dir
    print(f"OKF source: {Path(source).resolve()}")
    report = OKFValidator(source, settings.okf.required_metadata).validate()
    print(report.render(verbose=args.verbose))
    return 0 if report.passed else 1


def _cmd_ingest(args, settings) -> int:
    print(f"OKF source: {Path(args.input or settings.okf.source_dir).resolve()}")
    result = OKFLoader(args.input or settings.okf.source_dir).load()
    print(result.report.render())
    if args.verbose:
        for issue in result.report.issues:
            print(f"  [{issue.level.upper()}] {issue.path}: {issue.message}")
    return 0 if result.report.errors == 0 else 1


def _kb(settings, rebuild: bool = False, vectors: bool | None = None):
    from codeknowledge.services.indexing_service import KnowledgeBase

    kb = KnowledgeBase(settings)
    status = kb.load(rebuild=rebuild, rebuild_vectors=vectors)
    if not status.ready:
        print(status.error, file=sys.stderr)
        return None
    return kb


def _cmd_rebuild(args, settings) -> int:
    from codeknowledge.services.cache_service import AnswerCache

    if args.input:
        settings.okf.source_dir = args.input
    print(f"OKF source: {Path(settings.okf.source_dir).resolve()}")
    kb = _kb(settings, rebuild=True, vectors=not args.skip_vectors)
    if kb is None:
        return 1
    s = kb.status
    if s.documents == 0:
        print("No OKF documents found in that directory. Put the Java2OKF output there, set okf.source_dir in "
              "config/config.yaml, set CODEKNOWLEDGE_OKF_SOURCE_DIR, or pass --input.", file=sys.stderr)
        return 1
    purged = AnswerCache(settings).purge(keep_version=s.bundle_hash)
    print("Index rebuild")
    print("-------------")
    print(f"Documents: {s.documents}")
    print(f"Graph nodes: {s.graph_nodes}")
    print(f"Graph relationships: {s.graph_edges} (unresolved: {s.unresolved_relationships}, "
          f"external: {s.external_relationships})")
    print(f"Vector index: {s.vector_status} ({s.vector_documents} documents)")
    if s.error:
        print(f"Warning: {s.error}")
    print(f"Cache entries purged: {purged}")
    print("Timings (ms): " + ", ".join(f"{k}={v}" for k, v in s.timings_ms.items()))
    return 0 if s.vector_status in ("ok",) or args.skip_vectors else 1


def _cmd_search(args, settings) -> int:
    from codeknowledge.models.query import SearchRequest

    kb = _kb(settings)
    if kb is None:
        return 1
    res = kb.retriever.search(SearchRequest(query=args.query, top_k=args.top_k, mode=args.mode,
                                            entity_type=args.type, package=args.package))
    if args.json:
        print(res.model_dump_json(indent=2))
        return 0
    for w in res.warnings:
        print(f"Warning: {w}")
    for i, h in enumerate(res.hits, 1):
        e = h.entity
        loc = f"  {e.source_file}:{e.source_line}" if e.source_file else ""
        print(f"{i:2}. [{h.score:.2f}] {e.title} ({e.type.value}) <{'+'.join(h.match_types)}> {e.id}{loc}")
    if not res.hits:
        print("No results.")
    return 0


def _cmd_ask(args, settings) -> int:
    from codeknowledge.llm.provider import create_llm_provider
    from codeknowledge.models.answers import AskRequest
    from codeknowledge.services.ask_service import AskService
    from codeknowledge.services.cache_service import AnswerCache

    kb = _kb(settings)
    if kb is None:
        return 1
    svc = AskService(kb, create_llm_provider(settings.llm), AnswerCache(settings))
    r = svc.ask(AskRequest(question=args.question, use_llm=not args.no_llm, use_cache=not args.no_cache))
    if args.json:
        print(r.model_dump_json(indent=2))
        return 0
    print(f"Category: {r.category} (confidence {r.confidence:.2f}, {r.classification_method})")
    print("Plan:\n  " + "\n  ".join(r.plan))
    print("\nAnswer (deterministic facts):\n" + r.answer)
    if r.interpretation:
        print(f"\nAI interpretation ({r.llm_model}):\n{r.interpretation}")
    if r.llm_error:
        print(f"\nLLM: {r.llm_error}")
    for w in r.warnings:
        print(f"Warning: {w}")
    print("\nEvidence:")
    for e in r.evidence:
        loc = f" [{e.source}:{e.source_line}]" if e.source else ""
        print(f"- {e.document}{loc}{' *cited*' if e.cited else ''}")
    print("\nQuery latency: " + ", ".join(f"{k}={v}ms" for k, v in r.timings_ms.items())
          + (" (cached)" if r.cached else ""))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="codeknowledge", description="CodeKnowledgeAI command line")
    p.add_argument("--config", help="Path to config.yaml")
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="Validate an OKF bundle")
    v.add_argument("--input", help="OKF directory (defaults to okf.source_dir)")
    v.add_argument("-v", "--verbose", action="store_true")
    v.set_defaults(func=_cmd_validate)

    i = sub.add_parser("ingest", help="Load an OKF bundle and print the ingestion report")
    i.add_argument("--input", help="OKF directory (defaults to okf.source_dir)")
    i.add_argument("-v", "--verbose", action="store_true")
    i.set_defaults(func=_cmd_ingest)

    r = sub.add_parser("rebuild", help="Rebuild graph and vector indexes from OKF")
    r.add_argument("--input", help="OKF directory (defaults to okf.source_dir)")
    r.add_argument("--skip-vectors", action="store_true", help="Rebuild the graph only")
    r.set_defaults(func=_cmd_rebuild)

    s = sub.add_parser("search", help="Hybrid search (symbol + semantic + graph)")
    s.add_argument("query")
    s.add_argument("--top-k", type=int, default=None)
    s.add_argument("--mode", choices=["hybrid", "symbol", "semantic"], default="hybrid")
    s.add_argument("--type", help="Entity type filter (class, method, interface, ...)")
    s.add_argument("--package", help="Package filter")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=_cmd_search)

    a = sub.add_parser("ask", help="Ask a question")
    a.add_argument("question")
    a.add_argument("--no-llm", action="store_true", help="Deterministic answer only")
    a.add_argument("--no-cache", action="store_true")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=_cmd_ask)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(args.config)
    # CLI output is for humans; keep logs quiet on the console unless something is wrong.
    setup_logging("WARNING", settings.logging.file, None)
    try:
        return args.func(args, settings)
    except OKFSourceMissingError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
