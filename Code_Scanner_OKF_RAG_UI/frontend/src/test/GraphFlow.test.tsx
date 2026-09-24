import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { FlowPage } from "../pages/FlowPage";
import { GraphPage } from "../pages/GraphPage";
import { mockApi, renderWithProviders } from "./utils";

const subgraph = {
  root: "demo.A", depth: 2,
  nodes: [{ id: "demo.A", label: "A", type: "class" }, { id: "demo.B", label: "B", type: "class" }, { id: "demo.X", label: "X", type: "unresolved", status: "unresolved" }],
  edges: [{ source: "demo.A", target: "demo.B", type: "CALLS" }, { source: "demo.B", target: "demo.X", type: "CALLS", status: "unresolved" }],
};

const flow = {
  root: "demo.A.run", title: "A.run", availability: "explicit", notes: [], call_chains: [["demo.A.run", "demo.B.go"]],
  outline: ["A.run()", "  IF ready", "    CALL B.go()", "  END IF"], text: "A.run()\n  IF ready\n    CALL B.go()\n  END IF",
  nodes: [
    { id: "n1", kind: "start", label: "A.run()", entity_id: "demo.A.run", status: "resolved" },
    { id: "n2", kind: "condition", label: "ready", status: "resolved" },
    { id: "n3", kind: "call", label: "B.go()", entity_id: "demo.B.go", status: "resolved" },
    { id: "n4", kind: "end", label: "end", status: "resolved" },
  ],
  edges: [{ source: "n1", target: "n2" }, { source: "n2", target: "n3", label: "yes" }, { source: "n2", target: "n4", label: "no" }, { source: "n3", target: "n4" }],
  rules: [{ entity_id: "demo.A.run", condition: "ready", then: ["B.go()"], otherwise: [] }],
};

describe("GraphPage", () => {
  it("renders nodes, relationship filters and the selection sidebar", async () => {
    const fetchMock = mockApi({ "/api/graph/subgraph/demo.A": subgraph });
    renderWithProviders(<GraphPage />, "/graph?id=demo.A");
    expect(await screen.findByTestId("graph-view")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("3 nodes · 2 edges", { exact: false })).toBeInTheDocument());
    expect(screen.getAllByText("A").length).toBeGreaterThan(0);
    expect(String(fetchMock.mock.calls[0][0])).toContain("types=calls%2Cdependencies%2Cinheritance%2Cimplements%2Cuses");

    await userEvent.click(screen.getByLabelText("Calls"));
    await waitFor(() => expect(String(fetchMock.mock.calls.at(-1)?.[0])).not.toContain("calls%2C"));
    for (const f of ["Calls", "Dependencies", "Inheritance", "Implements", "Uses"]) {
      expect(screen.getByLabelText(f)).toBeInTheDocument();
    }
  });
});

describe("FlowPage", () => {
  it("renders the flow diagram, outline and rules", async () => {
    mockApi({ "/api/flow/demo.A.run": flow });
    renderWithProviders(<FlowPage />, "/flow?id=demo.A.run");
    expect(await screen.findByTestId("flow-diagram")).toBeInTheDocument();
    expect(screen.getByText("explicit")).toBeInTheDocument();
    expect(screen.getByText(/IF ready/, { selector: "pre" })).toBeInTheDocument();
    expect(screen.getByText("Conditional rules (from flow)")).toBeInTheDocument();
    expect(screen.getAllByText("B.go()").length).toBeGreaterThan(0);
  });

  it("marks unavailable flow without inventing nodes", async () => {
    mockApi({ "/api/flow/demo.Z": { ...flow, root: "demo.Z", title: "Z", availability: "unavailable", nodes: [], edges: [],
      rules: [], outline: [], text: "", call_chains: [], notes: ["No control-flow or call information for this entity in the OKF bundle."] } });
    renderWithProviders(<FlowPage />, "/flow?id=demo.Z");
    expect(await screen.findByText(/nothing is inferred/)).toBeInTheDocument();
    expect(screen.queryByTestId("flow-diagram")).toBeNull();
  });
});
