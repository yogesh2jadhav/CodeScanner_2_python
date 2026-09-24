from fastapi import APIRouter, Depends

from codeknowledge.api.deps import kb as get_kb
from codeknowledge.models.query import SearchRequest, SearchResponse
from codeknowledge.services.indexing_service import KnowledgeBase

router = APIRouter(tags=["search"])


@router.post("/api/search", response_model=SearchResponse)
def search(req: SearchRequest, kb: KnowledgeBase = Depends(get_kb)) -> SearchResponse:
    kb.require_ready()
    return kb.retriever.search(req)
