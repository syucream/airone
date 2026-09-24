/**
 * @jest-environment jsdom
 */

import { render, screen, act, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { TestWrapper } from "TestWrapper";
import i18n from "i18n/config";
import { AdvancedSearchResultsPage } from "pages/AdvancedSearchResultsPage";

const server = setupServer(
  // getEntityAttrs
  http.get(
    "http://localhost/entity/api/v2/attrs?entity_ids=1&referral_attr=",
    () => {
      return HttpResponse.json([]);
    },
  ),
  // advancedSearch
  http.post("http://localhost/entry/api/v2/advanced_search/", () => {
    return HttpResponse.json({
      count: 1,
      total_count: 1,
      values: [
        {
          entry: {
            id: 2,
            name: "entry1",
          },
          entity: {
            id: 1,
            name: "entity1",
          },
          attrs: {
            attr1: {
              type: 2,
              value: { asString: "attr1" },
              isReadable: true,
            },
            attr2: {
              type: 2,
              value: { asString: "attr1" },
              isReadable: true,
            },
          },
          isReadable: true,
        },
      ],
    });
  }),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

test("should match snapshot", async () => {
  Object.defineProperty(window, "django_context", {
    value: {
      user: {
        is_superuser: false,
      },
    },
    writable: false,
  });

  // wait async calls and get rendered fragment
  const result = await act(async () => {
    return render(<AdvancedSearchResultsPage />, {
      wrapper: TestWrapper,
    });
  });
  await waitFor(() => {
    expect(screen.queryByTestId("loading")).not.toBeInTheDocument();
  });

  expect(result).toMatchSnapshot();
});

test("renders in English", async () => {
  // "should match snapshot" (which runs before this test in this file)
  // already defines window.django_context as a non-writable property.
  await act(async () => {
    await i18n.changeLanguage("en");
  });

  await act(async () => {
    render(<AdvancedSearchResultsPage />, {
      wrapper: TestWrapper,
    });
  });
  await waitFor(() => {
    expect(screen.queryByTestId("loading")).not.toBeInTheDocument();
  });

  expect(screen.getAllByText("Search results").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Advanced Search").length).toBeGreaterThan(0);
  expect(screen.getByText("Reset attributes")).toBeInTheDocument();
  expect(screen.getByText("Export YAML")).toBeInTheDocument();
  expect(screen.getByText("Export CSV")).toBeInTheDocument();
  expect(screen.getByText("Bulk delete")).toBeInTheDocument();
});
