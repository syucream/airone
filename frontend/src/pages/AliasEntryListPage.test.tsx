/**
 */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { createMemoryRouter, RouterProvider } from "react-router";

import { TestWrapperWithoutRoutes } from "TestWrapper";
import i18n from "i18n/config";
import { AliasEntryListPage } from "pages/AliasEntryListPage";
import { listAliasPath } from "routes/Routes";

const server = setupServer(
  // GET /entity/api/v2/:entityId/
  http.get("http://localhost/entity/api/v2/1/", () => {
    return HttpResponse.json({
      id: 1,
      name: "Entity1",
      note: "Test Entity",
      isToplevel: true,
      hasOngoingChanges: false,
      attrs: [],
      webhooks: [],
      isolation_rules: [],
      delete_chain_exclude_entities: [],
    });
  }),

  // GET /entity/api/v2/:entityId/entries/
  http.get("http://localhost/entity/api/v2/1/entries/", ({ request }) => {
    // Get query parameters (when isAlias is true)
    const url = new URL(request.url);
    const withAlias = url.searchParams.get("with_alias");

    if (withAlias === "1") {
      return HttpResponse.json({
        count: 2,
        next: null,
        previous: null,
        results: [
          {
            id: 1,
            name: "entry1",
            schema: 1,
            created_at: "2023-01-01T00:00:00Z",
            updated_at: "2023-01-01T00:00:00Z",
            created_user: { id: 1, username: "user1" },
            updated_user: { id: 1, username: "user1" },
            attrs: [],
            referrals: [],
            aliases: [{ id: 101, name: "Existing alias", entry: 1 }],
            is_public: true,
            status: 0,
          },
          {
            id: 2,
            name: "entry2",
            schema: 1,
            created_at: "2023-01-02T00:00:00Z",
            updated_at: "2023-01-02T00:00:00Z",
            created_user: { id: 1, username: "user1" },
            updated_user: { id: 1, username: "user1" },
            attrs: [],
            referrals: [],
            aliases: [],
            is_public: true,
            status: 0,
          },
        ],
      });
    }

    return HttpResponse.json({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
  }),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderAliasPage() {
  const router = createMemoryRouter(
    [{ path: listAliasPath(":entityId"), element: <AliasEntryListPage /> }],
    { initialEntries: [listAliasPath(1)] },
  );
  return act(async () => {
    render(<RouterProvider router={router} />, {
      wrapper: TestWrapperWithoutRoutes,
    });
  });
}

describe("AliasEntryListPage", () => {
  it("renders the alias entry list", async () => {
    await renderAliasPage();
    const titleElement = screen.getByRole("heading", { name: "Entity1" });
    expect(titleElement).toBeInTheDocument();
    expect(await screen.findByText("Existing alias")).toBeInTheDocument();
  });

  it("adds an alias to the selected entry and clears the input", async () => {
    const createAlias = vi.fn();
    server.use(
      http.post("http://localhost/entry/api/v2/alias/", async ({ request }) => {
        createAlias(await request.json());
        return HttpResponse.json(
          { id: 201, name: "New alias", entry: 2 },
          { status: 201 },
        );
      }),
    );

    await renderAliasPage();
    const addButtons = await screen.findAllByTestId("AddIcon");
    fireEvent.click(addButtons[1]);

    const input = screen.getByPlaceholderText("エイリアスを追加");
    fireEvent.change(input, { target: { value: "New alias" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    expect(await screen.findByText("New alias")).toBeInTheDocument();
    expect(createAlias).toHaveBeenCalledExactlyOnceWith({
      entry: 2,
      name: "New alias",
    });
    expect(input).toHaveValue("");
  });

  it("renders in English", async () => {
    await act(async () => {
      await i18n.changeLanguage("en");
    });

    await renderAliasPage();

    expect(screen.getAllByText("Alias settings").length).toBeGreaterThan(0);
  });
});
