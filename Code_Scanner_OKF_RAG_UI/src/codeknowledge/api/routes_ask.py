from fastapi import APIRouter, Depends, Request

from codeknowledge.api.deps import ask_service
from codeknowledge.models.answers import AskRequest, AskResponse
from codeknowledge.services.ask_service import AskService

router = APIRouter(tags=["ask"])


@router.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest, request: Request, svc: AskService = Depends(ask_service)) -> AskResponse:
    return svc.ask(req, request_id=request.state.request_id)
