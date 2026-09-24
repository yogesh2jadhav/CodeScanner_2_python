from dataclasses import asdict

from fastapi import APIRouter, Depends, Request

from codeknowledge.api.deps import kb as get_kb
from codeknowledge.services.indexing_service import KnowledgeBase

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health(request: Request) -> dict:
    return {"status": "ok", "version": request.app.state.settings.application.version}


@router.get("/api/status")
def status(request: Request, kb: KnowledgeBase = Depends(get_kb)) -> dict:
    """Knowledge-base/index status plus LLM availability (for the UI status bar)."""
    llm = request.app.state.llm
    s = asdict(kb.status)
    s["bundle_hash"] = (s["bundle_hash"] or "")[:12] or None
    return {
        "knowledge_base": s,
        "llm": {"provider": getattr(llm, "name", None), "model": getattr(llm, "model", None),
                "available": bool(llm and llm.is_available())},
        "embedding": {"provider": kb.settings.embedding.provider, "model": kb.settings.embedding.model},
    }
