"""Build a Flow from OKF method metadata.

Supported `flow:` step forms in OKF frontmatter (list, possibly nested):
  - call: <target>                  (resolved to an entity when possible)
  - if: <condition>  then: [...]  else: [...]   (condition_call: optional target)
  - loop: <expression>  body: [...]   (aliases: for, while, foreach)
  - statement: <text> | assign: <text>
  - return: <text> | throw: <text>

Why never infer control flow from CALLS edges: the plan requires marking flow as
unavailable rather than inventing it. CALLS edges only yield an unordered
"call_sequence" view, explicitly labelled as such.
"""
from __future__ import annotations

from typing import Any

from codeknowledge.flow.path import Flow, FlowEdge, FlowNode
from codeknowledge.graph.store import GraphStore
from codeknowledge.okf.repository import OKFRepository
from codeknowledge.utils.ids import normalize_id, short_name

LOOP_KEYS = ("loop", "for", "foreach", "while")


def call_label(name: str) -> str:
    """"A.run" -> "A.run()"; names that already carry a parameter list are kept."""
    return name if name.endswith(")") else name + "()"
STATEMENT_KEYS = ("statement", "assign", "set", "step")


class _Ctx:
    def __init__(self, flow: Flow, repo: OKFRepository, source_id: str):
        self.flow = flow
        self.repo = repo
        self.source_id = source_id
        self.counter = 0
        self.depth = 0

    def line(self, text: str) -> None:
        self.flow.outline.append("  " * self.depth + text)

    def node(self, kind: str, label: str, entity_id: str | None = None, status: str = "resolved") -> str:
        self.counter += 1
        nid = f"n{self.counter}"
        self.flow.nodes.append(FlowNode(id=nid, kind=kind, label=label, entity_id=entity_id, status=status))
        return nid

    def edge(self, src: str, dst: str, label: str | None = "next") -> None:
        self.flow.edges.append(FlowEdge(source=src, target=dst, label=label))


class FlowBuilder:
    def __init__(self, repo: OKFRepository, graph: GraphStore | None = None):
        self.repo = repo
        self.graph = graph

    def _call_node(self, ctx: _Ctx, target: str) -> str:
        norm = normalize_id(str(target))
        eid = self.repo.resolve(norm, ctx.source_id)
        doc = self.repo.get(eid) if eid else None
        label = call_label(doc.display_name()) if doc else call_label(norm)
        return ctx.node("call", label, eid, "resolved" if eid else "unresolved")

    def _steps(self, ctx: _Ctx, steps: list[Any], entry: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
        """Append steps after `entry` exits; returns the dangling exits (node, edge label)."""
        exits = entry
        for step in steps:
            exits = self._step(ctx, step, exits)
        return exits

    def _connect(self, ctx: _Ctx, exits: list[tuple[str, str | None]], nid: str) -> None:
        for src, label in exits:
            ctx.edge(src, nid, label or "next")

    def _step(self, ctx: _Ctx, step: Any, exits: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
        if isinstance(step, str):
            ctx.line(step)
            nid = ctx.node("statement", step)
            self._connect(ctx, exits, nid)
            return [(nid, None)]
        if not isinstance(step, dict):
            ctx.flow.notes.append(f"Ignored unrecognised flow step: {step!r}")
            return exits

        if "call" in step:
            nid = self._call_node(ctx, step["call"])
            ctx.line(f"CALL {ctx.flow.nodes[-1].label}")
            self._connect(ctx, exits, nid)
            return [(nid, None)]

        if "if" in step or "condition" in step:
            cond = str(step.get("if", step.get("condition")))
            cond_eid = None
            if step.get("condition_call"):
                cond_eid = self.repo.resolve(normalize_id(str(step["condition_call"])), ctx.source_id)
            nid = ctx.node("condition", cond, cond_eid)
            self._connect(ctx, exits, nid)
            ctx.line(f"IF {cond}")
            ctx.depth += 1
            then_exits = self._steps(ctx, step.get("then") or [], [(nid, "yes")])
            ctx.depth -= 1
            else_steps = step.get("else") or []
            if else_steps:
                ctx.line("ELSE")
                ctx.depth += 1
            else_exits = self._steps(ctx, else_steps, [(nid, "no")]) if else_steps else [(nid, "no")]
            if else_steps:
                ctx.depth -= 1
            ctx.line("END IF")
            merge = ctx.node("merge", "")
            self._connect(ctx, then_exits + else_exits, merge)
            return [(merge, None)]

        loop_key = next((k for k in LOOP_KEYS if k in step), None)
        if loop_key:
            nid = ctx.node("loop", str(step[loop_key]))
            self._connect(ctx, exits, nid)
            ctx.line(f"LOOP {step[loop_key]}")
            ctx.depth += 1
            body_exits = self._steps(ctx, step.get("body") or step.get("do") or [], [(nid, "loop")])
            ctx.depth -= 1
            ctx.line("END LOOP")
            for src, label in body_exits:
                ctx.edge(src, nid, label or "repeat")
            return [(nid, "done")]

        if "return" in step:
            nid = ctx.node("return", f"return {step['return']}")
            ctx.line(f"RETURN {step['return']}")
            self._connect(ctx, exits, nid)
            return [(nid, None)]
        if "throw" in step:
            nid = ctx.node("throw", f"throw {step['throw']}")
            ctx.line(f"THROW {step['throw']}")
            self._connect(ctx, exits, nid)
            return []  # terminal: nothing continues after a throw

        stmt_key = next((k for k in STATEMENT_KEYS if k in step), None)
        if stmt_key:
            nid = ctx.node("statement", str(step[stmt_key]))
            ctx.line(str(step[stmt_key]))
            self._connect(ctx, exits, nid)
            return [(nid, None)]

        ctx.flow.notes.append(f"Ignored unrecognised flow step: {step!r}")
        return exits

    def build(self, entity_id: str, max_depth: int = 3) -> Flow | None:
        doc = self.repo.get(entity_id)
        if doc is None and not (self.graph and self.graph.has_node(entity_id)):
            return None
        title = doc.display_name() if doc else short_name(entity_id)
        steps = doc.metadata.get("flow") if doc else None

        flow = Flow(root=entity_id, title=title, availability="unavailable")
        if self.graph is not None:
            from codeknowledge.graph.traversal import GraphTraversal

            chains = GraphTraversal(self.graph).reachable_call_chains(entity_id, max_depth)
            flow.call_chains = [c for c in chains if len(c) > 1]

        ctx = _Ctx(flow, self.repo, entity_id)
        if isinstance(steps, list) and steps:
            flow.availability = "explicit"
            start = ctx.node("start", call_label(title), entity_id)
            ctx.line(call_label(title))
            ctx.depth = 1
            exits = self._steps(ctx, steps, [(start, None)])
            end = ctx.node("end", "end")
            self._connect(ctx, exits, end)
            # Nodes reached only via throw have no path to end; that is intentional.
            return flow

        call_edges = self.graph.edges(entity_id, "out", {"CALLS"}) if self.graph is not None else []
        if call_edges:
            flow.availability = "call_sequence"
            with_lines = [e for e in call_edges if e.attrs.get("line") is not None]
            # Java2OKF records the source line of each call, which gives a faithful textual
            # order. It is still not control flow: branches and loops stay unknown.
            ordered = sorted(call_edges, key=lambda e: (e.attrs.get("line") is None, e.attrs.get("line") or 0, e.target))
            if with_lines:
                flow.notes.append("Control flow (conditions, loops) is not available in OKF; calls are shown "
                                  "in source-line order.")
            else:
                flow.notes.append("Control flow (order, conditions, loops) is not available in OKF; "
                                  "showing known calls only. Order is not implied.")
            start = ctx.node("start", call_label(title), entity_id)
            ctx.line(call_label(title))
            prev = start
            for e in ordered:
                node = self.graph.get_node(e.target) or {}
                doc = self.repo.get(e.target)
                label = (doc.display_name() if doc else node.get("label", short_name(e.target)))
                label = call_label(label)
                status = node.get("status", "resolved")
                nid = ctx.node("call", label, e.target if doc else None, status)
                line = e.attrs.get("line")
                ctx.line(f"  CALL {label}" + (f"  (line {line})" if line else "") + ("  [external]" if status == "external" else ""))
                if with_lines:
                    ctx.edge(prev, nid, "next")
                    prev = nid
                else:
                    ctx.edge(start, nid, "calls")
            end = ctx.node("end", "end")
            if with_lines:
                ctx.edge(prev, end, None)
            else:
                for n in flow.nodes:
                    if n.kind == "call":
                        ctx.edge(n.id, end, None)
            return flow

        flow.notes.append("No control-flow or call information for this entity in the OKF bundle.")
        return flow
