from fastapi import APIRouter, Depends, Query

from codeknowledge.api.deps import flow_service
from codeknowledge.services.flow_service import FlowService

router = APIRouter(tags=["flow"])


@router.get("/api/flow/{entity_id:path}")
def flow(entity_id: str, depth: int | None = Query(None, ge=1, le=10), svc: FlowService = Depends(flow_service)) -> dict:
    return svc.flow(entity_id, depth)
