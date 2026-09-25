from fastapi import APIRouter, Depends, Request

from codeknowledge.api.deps import method_explainer
from codeknowledge.explain.models import ExplainOptions, MethodExplanationResponse
from codeknowledge.explain.service import MethodExplanationService

router = APIRouter(tags=["methods"])


class ExplainRequest(ExplainOptions):
    use_llm: bool = True  # false = deterministic evidence only (no model call)


@router.post("/api/methods/{method_id:path}/explain", response_model=MethodExplanationResponse)
def explain_method(method_id: str, request: Request, body: ExplainRequest | None = None,
                   svc: MethodExplanationService = Depends(method_explainer)) -> MethodExplanationResponse:
    """Evidence-grounded, step-by-step explanation of one method/constructor (canonical OKF id)."""
    body = body or ExplainRequest()
    return svc.explain(method_id, ExplainOptions(**body.model_dump(exclude={"use_llm"})),
                       request_id=request.state.request_id, use_llm=body.use_llm)
