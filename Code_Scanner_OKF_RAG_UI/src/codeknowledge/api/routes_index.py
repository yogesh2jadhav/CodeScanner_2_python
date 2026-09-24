from dataclasses import asdict

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from codeknowledge.api.deps import kb as get_kb
from codeknowledge.services.indexing_service import KnowledgeBase

router = APIRouter(tags=["index"])


class RebuildRequest(BaseModel):
    vectors: bool = True


@router.post("/api/index/rebuild")
def rebuild(request: Request, body: RebuildRequest | None = None, kb: KnowledgeBase = Depends(get_kb)) -> dict:
    """Reload OKF and rebuild graph (and, by default, the vector index). Purges stale cache entries."""
    body = body or RebuildRequest()
    status = kb.load(rebuild=True, rebuild_vectors=body.vectors)
    purged = request.app.state.cache.purge(keep_version=status.bundle_hash) if status.ready else 0
    s = asdict(status)
    s["bundle_hash"] = (s["bundle_hash"] or "")[:12] or None
    return {"status": "ok" if status.ready else "error", "index": s, "cache_entries_purged": purged}
