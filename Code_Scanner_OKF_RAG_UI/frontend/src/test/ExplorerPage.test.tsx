import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ExplorerPage } from "../pages/ExplorerPage";
import { entityDetail, mockApi, relationships, renderWithProviders } from "./utils";

const tree = [{ id: "demo", title: "demo", type: "package", has_document: false, children: [
  { id: "demo.A", title: "A", type: "class", children: [{ id: "demo.A.run", title: "run", type: "method", children: [] }] },
] }];

describe("ExplorerPage", () => {
  it("shows the tree, loads a document and relationships, and sanitizes markdown", async () => {
    mockApi({
      "/api/explorer/tree": tree,
      "/api/entities/demo.A/relationships": relationships("demo.A"),
      "/api/entities/demo.A": entityDetail("demo.A"),
    });
    const { container } = renderWithProviders(<ExplorerPage />, "/explorer");
    await userEvent.click(await screen.findByRole("button", { name: /CLASS\s*A/i }));

    expect(await screen.findByRole("heading", { name: "demo.A", level: 1 })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Relationships")).toHaveTextContent("CALLS (1)"));
    expect(container.querySelector("script")).toBeNull(); // raw HTML is never rendered
    // relative OKF link resolved to an entity reference
    const docLink = container.querySelector(".prose-ck button.entity-ref");
    expect(docLink).toHaveTextContent("B");
    expect(docLink).toHaveAttribute("title", "demo.B");
    // tree expanded to show methods
    expect(screen.getByText("run")).toBeInTheDocument();
  });
});
