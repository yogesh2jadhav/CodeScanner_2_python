"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from codeknowledge.api import (routes_ask, routes_explorer, routes_flow, routes_graph, routes_health,
                               routes_index, routes_methods, routes_search)
from codeknowledge.explain.evidence import InvalidMethodIdError, MethodNotFoundError
from codeknowledge.explain.service import ExplanationDisabledError, MethodExplanationService
from codeknowledge.llm.provider import LLMTimeoutError, LLMUnavailableError
from codeknowledge.config.settings import Settings, get_settings
from codeknowledge.llm.provider import LLMProvider, create_llm_provider
from codeknowledge.services.ask_service import AskService
from codeknowledge.services.cache_service import AnswerCache
from codeknowledge.services.explorer_service import EntityNotFoundError, ExplorerService
from codeknowledge.services.flow_service import FlowService
from codeknowledge.services.graph_service import GraphService
from codeknowledge.services.indexing_service import KnowledgeBase, KnowledgeBaseNotReadyError
from codeknowledge.utils.ids import new_request_id
from codeknowledge.utils.logging import get_logger, request_id_var, setup_logging

logger = get_logger("App")


def create_app(settings: Settings | None = None, llm: LLMProvider | None = None, load_on_startup: bool = True) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.logging.level, settings.logging.file, settings.logging.config_file)

    kb = KnowledgeBase(settings)
    llm = llm or create_llm_provider(settings.llm)
    cache = AnswerCache(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if load_on_startup:
            kb.load()
            if kb.status.ready:
                cache.purge(keep_version=kb.status.bundle_hash)
        yield

    app = FastAPI(title=settings.application.name, version=settings.application.version, lifespan=lifespan,
                  description="OKF + Graph + RAG for Java code understanding. OKF is canonical; indexes are derived.")
    app.state.settings = settings
    app.state.kb = kb
    app.state.llm = llm
    app.state.cache = cache
    app.state.method_explainer = MethodExplanationService(kb, llm, cache)
    app.state.ask_service = AskService(kb, llm, cache, app.state.method_explainer)
    app.state.explorer = ExplorerService(kb)
    app.state.graph_service = GraphService(kb)
    app.state.flow_service = FlowService(kb)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.application.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def correlation_id(request: Request, call_next):
        # Every request gets a correlation id so all log lines of one /api/ask can be traced.
        rid = request.headers.get("X-Request-ID") or new_request_id()
        rid = "".join(c for c in rid if c.isalnum() or c in "-_")[:64] or new_request_id()
        request.state.request_id = rid
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        return response

    @app.exception_handler(KnowledgeBaseNotReadyError)
    async def not_ready(_: Request, exc: KnowledgeBaseNotReadyError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(EntityNotFoundError)
    async def not_found(_: Request, exc: EntityNotFoundError):
        return JSONResponse(status_code=404, content={"detail": f"Entity not found: {exc.args[0]}"})

    def _error(request: Request, status: int, detail: str) -> JSONResponse:
        # Safe client error: message + correlation id; stack traces stay in the server log.
        return JSONResponse(status_code=status, content={"detail": detail, "request_id": request.state.request_id})

    @app.exception_handler(MethodNotFoundError)
    async def method_not_found(request: Request, exc: MethodNotFoundError):
        return _error(request, 404, f"Method not found: {exc.args[0]}")

    @app.exception_handler(InvalidMethodIdError)
    async def invalid_method_id(request: Request, exc: InvalidMethodIdError):
        return _error(request, 422, str(exc))

    @app.exception_handler(ExplanationDisabledError)
    async def explanation_disabled(request: Request, exc: ExplanationDisabledError):
        return _error(request, 404, str(exc))

    @app.exception_handler(LLMUnavailableError)
    async def llm_unavailable(request: Request, exc: LLMUnavailableError):
        status = 504 if isinstance(exc, LLMTimeoutError) else 503
        logger.error("LLM error (%s): %s", type(exc).__name__, exc)
        return _error(request, status, str(exc))

    for r in (routes_health, routes_index, routes_search, routes_ask, routes_explorer, routes_graph, routes_flow,
              routes_methods):
        app.include_router(r.router)
    logger.info("Application created name=%s version=%s", settings.application.name, settings.application.version)
    return app


def _default_app() -> FastAPI:
    return create_app()


app = _default_app()
