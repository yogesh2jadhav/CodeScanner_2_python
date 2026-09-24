import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { SearchPage } from "../pages/SearchPage";
import { entity, mockApi, renderWithProviders } from "./utils";

describe("SearchPage", () => {
  it("sends filters and renders hits", async () => {
    const fetchMock = mockApi({
      "POST /api/search": {
        query: "A", mode: "symbol", warnings: ["Semantic search unavailable: x"], timings_ms: { symbol_search: 1 },
        hits: [{ entity: entity("demo.A"), score: 1, match_types: ["symbol"], matched_on: "class_name" }],
      },
    });
    renderWithProviders(<SearchPage />);
    await userEvent.type(screen.getByLabelText("Search query"), "A");
    await userEvent.selectOptions(screen.getByLabelText("Mode"), "symbol");
    await userEvent.selectOptions(screen.getByLabelText("Entity type"), "class");
    await userEvent.type(screen.getByLabelText("Package"), "demo");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(await screen.findByRole("button", { name: "A" })).toBeInTheDocument();
    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body).toMatchObject({ query: "A", mode: "symbol", entity_type: "class", package: "demo" });
    expect(screen.getByText("class_name")).toBeInTheDocument();
    expect(screen.getByText(/Semantic search unavailable/)).toBeInTheDocument();
  });
});
