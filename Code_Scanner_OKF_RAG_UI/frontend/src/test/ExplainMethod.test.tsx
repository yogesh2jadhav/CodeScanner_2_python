import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { useEffect } from "react";
import { useEntityPanel } from "../components/EntityPanelContext";
import { entity, mockApi, relationships, renderWithProviders } from "./utils";

const MID = "java-method:p.S.run(int)";

const detail = (id: string, type: string) => ({
  entity: entity(id, type), content: "# doc", signature: "void run(int n)", metadata: {}, flow_available: false,
  owner: null, members: [], link_targets: {},
});

const explanation = {
  request_id: "rid-7", method_id: MID, method_signature: "void run(int n)", method_title: "S.run(int)",
  evidence: [
    { evidence_id: "E1", kind: "method_metadata", title: "S.run(int) (metadata)", entity_id: MID, file: "src/S.java",
      start_line: 10, end_line: 14, status: "resolved", depth: 0, priority: 1, content: "Method: S.run", lines: [] },
    { evidence_id: "E2", kind: "method_source", title: "S.run(int) source", entity_id: MID, file: "src/S.java",
      start_line: 10, end_line: 14, status: "resolved", depth: 0, priority: 0, lines: [],
      content: "10| void run(int n) {\n11|   if (n > 0) {\n12|     helper();\n13|   }\n14| }" },
    { evidence_id: "E3", kind: "callee_signature", title: "S.helper() (callee, body unavailable)", entity_id: "java-method:p.S.helper()",
      file: "src/S.java", start_line: 20, end_line: 20, status: "unavailable", depth: 1, priority: 6, content: "void helper()", lines: [] },
  ],
  facts: { comments: [], conditions: [{ line: 11, kind: "if", expression: "n > 0" }], calls: [] },
  warnings: ["1 statement(s) have no verified source reference (marked unverified)."],
  validation: { valid: true, repair_attempts: 0, invalid_refs_removed: 0, ungrounded_items: 1, corrected_call_statuses: 0, errors: [] },
  model: { provider: "ollama", model: "qwen3:8b", prompt_version: "method-explanation-v1", num_ctx: 16384 },
  cached: false, timings_ms: { llm: 1200, total: 1250 }, estimated_prompt_tokens: 900, markdown: "## S.run(int)",
  explanation: {
    summary: "Runs the helper when n is positive. <img src=x onerror=alert(1)>", purpose_is_inferred: true,
    inputs_outputs: [{ name: "n", role: "input", description: "a count" }],
    execution_steps: [
      { step_number: 1, title: "Check n", description: "Only continues when n > 0.", certainty: "observed", grounded: true,
        source_refs: [{ evidence_id: "E2", start_line: 11, end_line: 13 }] },
      { step_number: 2, title: "Unclear", description: "Something.", certainty: "derived", grounded: false, source_refs: [] },
    ],
    branches: [{ condition: "n > 0", when_true: "calls helper()", when_false: null, grounded: true,
                 source_refs: [{ evidence_id: "E2", start_line: 11, end_line: 11 }] }],
    data_transformations: [], side_effects: [], exceptions: [],
    calls: [{ callee: "java-method:p.S.helper()", evidence_status: "signature_only", summary: "does work", grounded: true,
              source_refs: [{ evidence_id: "E9", start_line: 1, end_line: 1 }] }],
    uncertainties: ["helper() body is not available"],
  },
};

function Open({ id }: { id: string }) {
  const { open } = useEntityPanel();
  useEffect(() => open(id), [id, open]);
  return null;
}

function setup(id: string, type: string, explainResponse: unknown = explanation) {
  const fetchMock = mockApi({
    [`/api/entities/${encodeURIComponent(id)}/relationships`]: relationships(id),
    [`/api/entities/${encodeURIComponent(id)}`]: detail(id, type),
    "POST /api/methods/": explainResponse,
  });
  renderWithProviders(<Open id={id} />);
  return fetchMock;
}

describe("Explain Method", () => {
  it("shows the Explain tab only for methods", async () => {
    setup("p.S", "class");
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(within(dialog).getByRole("tab", { name: "overview" })).toBeInTheDocument());
    expect(within(dialog).queryByRole("tab", { name: "explain" })).toBeNull();
  });

  it("sends the entity id and options, renders sections, citations and callee links", async () => {
    const fetchMock = setup(MID, "method");
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(await within(dialog).findByRole("tab", { name: "explain" }));
    await userEvent.selectOptions(within(dialog).getByLabelText("Callee depth"), "2");
    await userEvent.click(within(dialog).getByRole("button", { name: "Explain method" }));

    const view = await within(dialog).findByTestId("method-explanation");
    const call = fetchMock.mock.calls.find((c) => String(c[0]).includes("/api/methods/"))!;
    expect(String(call[0])).toBe(`/api/methods/${encodeURIComponent(MID)}/explain`);
    expect(JSON.parse(String(call[1]?.body))).toMatchObject({ max_callee_depth: 2, detail: "detailed", use_llm: true });

    expect(within(view).getByText("1. Check n")).toBeInTheDocument();
    expect(within(view).getByText("unverified")).toBeInTheDocument();
    expect(within(view).getByText("1 statement(s) have no verified source reference (marked unverified).")).toBeInTheDocument();
    expect(within(view).getByText("helper() body is not available")).toBeInTheDocument();
    // model text is rendered as text, never as HTML
    expect(view.querySelector("img")).toBeNull();
    expect(within(view).getByText(/<img src=x onerror=alert\(1\)>/)).toBeInTheDocument();
    // callee link opens the entity; a citation to unknown evidence (E9) is not rendered
    const calls = within(view).getByTestId("calls");
    expect(within(calls).getByRole("button", { name: /helper/ })).toBeInTheDocument();
    expect(within(calls).queryByRole("button", { name: /Show source/ })).toBeNull();

    await userEvent.click(within(view).getByRole("button", { name: "Show source S.java:11-13" }));
    const cited = within(view).getByRole("region", { name: "Cited source" });
    const hl = cited.querySelectorAll("[data-highlighted]");
    expect([...hl].map((el) => el.textContent?.trim().slice(0, 2))).toEqual(["11", "12", "13"]);
  });

  it("shows API errors with the request id and retries", async () => {
    let n = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/relationships")) return new Response(JSON.stringify(relationships(MID)));
      if (url.includes("/api/entities/")) return new Response(JSON.stringify(detail(MID, "method")));
      n += 1;
      return n === 1
        ? new Response(JSON.stringify({ detail: "Ollama did not answer within 600s", request_id: "rid-err" }), { status: 504 })
        : new Response(JSON.stringify(explanation));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<Open id={MID} />);
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(await within(dialog).findByRole("tab", { name: "explain" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Explain method" }));
    const alert = await within(dialog).findByRole("alert");
    expect(alert).toHaveTextContent("Ollama did not answer within 600s");
    expect(alert).toHaveTextContent("request_id=rid-err");
    await userEvent.click(within(dialog).getByRole("button", { name: "Retry" }));
    expect(await within(dialog).findByTestId("method-explanation")).toBeInTheDocument();
  });

  it("renders deterministic facts when the model output was invalid", async () => {
    setup(MID, "method", { ...explanation, explanation: null, warnings: ["The model did not return a valid explanation"] });
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(await within(dialog).findByRole("tab", { name: "explain" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Evidence only" }));
    const view = await within(dialog).findByTestId("method-explanation");
    expect(within(view).getByText(/Deterministic facts/)).toBeInTheDocument();
    expect(within(view).getByText("n > 0")).toBeInTheDocument();
  });
});
