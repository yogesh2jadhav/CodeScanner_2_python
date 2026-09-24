from typing import Literal

from fastapi import APIRouter, Depends, Query

from codeknowledge.api.deps import graph_service
from codeknowledge.services.graph_service import GraphService

router = APIRouter(tags=["graph"])
TYPES_HELP = "Comma-separated filters: calls, dependencies, inheritance, implements, uses, contains, references (or raw types)"


@router.get("/api/graph/node/{node_id:path}")
def node(node_id: str, svc: GraphService = Depends(graph_service)) -> dict:
    return svc.node(node_id)


@router.get("/api/graph/neighbors/{node_id:path}")
def neighbors(node_id: str, direction: Literal["in", "out", "both"] = "both",
              types: str | None = Query(None, description=TYPES_HELP),
              svc: GraphService = Depends(graph_service)) -> dict:
    return svc.neighbors(node_id, direction, types)


@router.get("/api/graph/path")
def path(from_: str = Query(..., alias="from"), to: str = Query(...),
         types: str | None = Query(None, description=TYPES_HELP), directed: bool = True,
         svc: GraphService = Depends(graph_service)) -> dict:
    return svc.path(from_, to, types, directed)


@router.get("/api/graph/subgraph/{node_id:path}")
def subgraph(node_id: str, depth: int = Query(2, ge=0, le=6), types: str | None = Query(None, description=TYPES_HELP),
             direction: Literal["in", "out", "both"] = "both", svc: GraphService = Depends(graph_service)) -> dict:
    return svc.subgraph(node_id, depth, types, direction)
