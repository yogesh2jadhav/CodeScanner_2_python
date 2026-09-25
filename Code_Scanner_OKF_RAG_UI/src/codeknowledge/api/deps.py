"""Accessors for services stored on app.state (keeps routes free of globals)."""
from fastapi import Request

from codeknowledge.explain.service import MethodExplanationService
from codeknowledge.services.ask_service import AskService
from codeknowledge.services.explorer_service import ExplorerService
from codeknowledge.services.flow_service import FlowService
from codeknowledge.services.graph_service import GraphService
from codeknowledge.services.indexing_service import KnowledgeBase


def kb(request: Request) -> KnowledgeBase:
    return request.app.state.kb


def ask_service(request: Request) -> AskService:
    return request.app.state.ask_service


def explorer(request: Request) -> ExplorerService:
    return request.app.state.explorer


def graph_service(request: Request) -> GraphService:
    return request.app.state.graph_service


def method_explainer(request: Request) -> MethodExplanationService:
    return request.app.state.method_explainer


def flow_service(request: Request) -> FlowService:
    return request.app.state.flow_service
