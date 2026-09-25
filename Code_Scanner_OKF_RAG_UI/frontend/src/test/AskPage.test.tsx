import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AskPage } from "../pages/AskPage";
import { entity, entityDetail, mockApi, relationships, renderWithProviders } from "./utils";

const answer = {
  request_id: "abc123", question: "What does A eventually call?", category: "CALLEES", confidence: 0.9,
  classification_method: "rules", plan: ["1. Exact symbol lookup", "2. Graph forward traversal over CALLS (depth 3)"],
  target: "demo.A", answer: "Call chains starting at A:\n\n- A → B → C", facts: [{ claim: "A → B → C", kind: "fact", evidence: ["demo.A", "demo.B", "demo.C"] }],
  interpretation: "### Interpretation\n`A` appears to delegate to `C`.", evidence: ["demo.A", "demo.B", "demo.C"].map((id) => ({
    entity_id: id, title: id.slice(5), type: "class", document: `${id.slice(5)}.md`, source: `src/demo/${id.slice(5)}.java`,
    source_line: 1, reason: "on call chain", cited: id !== "demo.B",
  })),
  related_entities: [entity("demo.B"), entity("demo.C")], relationships: [], paths: [["demo.A", "demo.B", "demo.C"]],
  flow: null, llm_used: true, llm_model: "qwen3:8b", llm_error: null, warnings: [], timings_ms: { total: 12 }, cached: false,
};

describe("AskPage", () => {
  it("asks a question and renders facts, interpretation, path and evidence", async () => {
    const fetchMock = mockApi({ "POST /api/ask": answer });
    renderWithProviders(<AskPage />);
    await userEvent.type(screen.getByLabelText("Question"), "What does A eventually call?");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText("CALLEES")).toBeInTheDocument();
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body).toEqual({ question: "What does A eventually call?", use_llm: true });

    const path = screen.getByTestId("path");
    expect(within(path).getAllByRole("button").map((b) => b.textContent)).toEqual(["A", "B", "C"]);
    expect(screen.getByText(/AI interpretation/)).toBeInTheDocument();
    expect(screen.getByText("qwen3:8b; verify against evidence", { exact: false })).toBeInTheDocument();
    const evidence = screen.getByTestId("evidence");
    expect(within(evidence).getAllByRole("listitem")).toHaveLength(3);
    expect(within(evidence).getAllByText("cited")).toHaveLength(2);
    expect(screen.getByText("request_id=abc123")).toBeInTheDocument();
  });

  it("evidence links open the entity panel (final acceptance: A, B and C are clickable)", async () => {
    mockApi({
      "POST /api/ask": answer,
      "/api/entities/demo.B/relationships": relationships("demo.B"),
      "/api/entities/demo.B": entityDetail("demo.B"),
    });
    renderWithProviders(<AskPage />);
    await userEvent.type(screen.getByLabelText("Question"), "What does A eventually call?");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    const facts = await screen.findAllByRole("button", { name: "B" });
    expect(facts.length).toBeGreaterThan(1); // path chip + linkified fact text + evidence
    await userEvent.click(within(screen.getByTestId("evidence")).getByRole("button", { name: /B/ }));

    const dialog = await screen.findByRole("dialog", { name: "Entity details" });
    expect(within(dialog).getByText("demo.B", { selector: "p" })).toBeInTheDocument();
    await waitFor(() => expect(within(dialog).getByText("src/demo/B.java:1")).toBeInTheDocument());
    await userEvent.click(within(dialog).getByRole("tab", { name: "relationships" }));
    expect(within(dialog).getByText("CALLS (1)")).toBeInTheDocument();
  });

  it("renders the source code with comment and condition lines", async () => {
    mockApi({ "POST /api/ask": { ...answer, source: {
      file: "src/A.java", start_line: 10, decl_line: 11, end_line: 14, truncated: false, notes: [],
      code: "// set flag\nvoid run() {\n  if (enabled) { flag = 1; }\n}",
      comments: [{ start_line: 10, end_line: 10, kind: "line", text: "set flag" }],
      conditions: [{ line: 12, kind: "if", expression: "enabled" }] } } });
    renderWithProviders(<AskPage />);
    await userEvent.type(screen.getByLabelText("Question"), "Explain A.run");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText("Source code (5 lines, 1 comments)")).toBeInTheDocument();
    const code = screen.getByTestId("source-code");
    expect(within(code).getByText("12")).toBeInTheDocument();
    expect(code).toHaveTextContent("if (enabled) { flag = 1; }");
  });

  it("shows LLM errors without hiding deterministic facts", async () => {
    mockApi({ "POST /api/ask": { ...answer, interpretation: null, llm_used: false, llm_error: "LLM unavailable: down" } });
    renderWithProviders(<AskPage />);
    await userEvent.type(screen.getByLabelText("Question"), "q");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText(/LLM unavailable: down/)).toBeInTheDocument();
    expect(screen.getByText(/Verified facts/)).toBeInTheDocument();
  });

  it("renders API errors", async () => {
    mockApi({});
    renderWithProviders(<AskPage />);
    await userEvent.type(screen.getByLabelText("Question"), "q");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No mock for POST");
  });
});
