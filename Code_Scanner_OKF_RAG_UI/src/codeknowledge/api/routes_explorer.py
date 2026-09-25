from fastapi import APIRouter, Depends

from codeknowledge.api.deps import explorer
from codeknowledge.services.explorer_service import ExplorerService

router = APIRouter(tags=["explorer"])


@router.get("/api/explorer/tree")
def tree(svc: ExplorerService = Depends(explorer)) -> list[dict]:
    return svc.tree()


@router.get("/api/entities/{entity_id:path}/source")
def source(entity_id: str, svc: ExplorerService = Depends(explorer)) -> dict:
    return svc.source(entity_id)


@router.get("/api/entities/{entity_id:path}/relationships")
def relationships(entity_id: str, svc: ExplorerService = Depends(explorer)) -> dict:
    return svc.relationships(entity_id)


@router.get("/api/entities/{entity_id:path}")
def entity(entity_id: str, svc: ExplorerService = Depends(explorer)) -> dict:
    return svc.entity(entity_id)
