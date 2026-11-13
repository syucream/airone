/**
 */

import { renderHook, act, screen } from "@testing-library/react";
import { FC, ReactNode } from "react";
import { ErrorBoundary } from "react-error-boundary";
import { MemoryRouter } from "react-router";

import { useSimpleSearch } from "./useSimpleSearch";

const mockNavigation = vi.hoisted(() => ({
  enabled: false,
  navigate: vi.fn<(to: import("react-router").To) => Promise<void>>(),
}));

vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router")>();
  return {
    ...actual,
    useNavigate: () => {
      const navigate = actual.useNavigate();
      return mockNavigation.enabled ? mockNavigation.navigate : navigate;
    },
  };
});

afterEach(() => {
  mockNavigation.enabled = false;
  mockNavigation.navigate.mockReset();
  vi.restoreAllMocks();
});

function createWrapper(
  initialEntries: string[] = ["/"],
): FC<{ children: ReactNode }> {
  const Wrapper: FC<{ children: ReactNode }> = ({ children }) => (
    <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
  );
  Wrapper.displayName = "TestWrapper";
  return Wrapper;
}

describe("useSimpleSearch", () => {
  describe("query value", () => {
    test("should return undefined when no query in URL", () => {
      const { result } = renderHook(() => useSimpleSearch(), {
        wrapper: createWrapper(["/"]),
      });

      const [query] = result.current;
      expect(query).toBeUndefined();
    });

    test("should return query value from URL", () => {
      const { result } = renderHook(() => useSimpleSearch(), {
        wrapper: createWrapper(["/?simple_search_query=test"]),
      });

      const [query] = result.current;
      expect(query).toBe("test");
    });

    test("should return query value when other params present", () => {
      const { result } = renderHook(() => useSimpleSearch(), {
        wrapper: createWrapper([
          "/?page=1&simple_search_query=search&other=value",
        ]),
      });

      const [query] = result.current;
      expect(query).toBe("search");
    });

    test("should handle empty query string", () => {
      const { result } = renderHook(() => useSimpleSearch(), {
        wrapper: createWrapper(["/?simple_search_query="]),
      });

      const [query] = result.current;
      expect(query).toBe("");
    });
  });

  describe("submitQuery function", () => {
    test("should return submitQuery function", () => {
      const { result } = renderHook(() => useSimpleSearch(), {
        wrapper: createWrapper(["/"]),
      });

      const [, , submitQuery] = result.current;
      expect(typeof submitQuery).toBe("function");
    });

    test("should update query when submitQuery is called", () => {
      const { result } = renderHook(() => useSimpleSearch(), {
        wrapper: createWrapper(["/"]),
      });

      act(() => {
        const [, , submitQuery] = result.current;
        submitQuery("newquery");
      });

      const [query] = result.current;
      expect(query).toBe("newquery");
    });

    test("should clear query when submitQuery is called with undefined", () => {
      const { result } = renderHook(() => useSimpleSearch(), {
        wrapper: createWrapper(["/?simple_search_query=test"]),
      });

      act(() => {
        const [, , submitQuery] = result.current;
        submitQuery(undefined);
      });

      const [query] = result.current;
      expect(query).toBeUndefined();
    });

    test("should handle query with special characters", () => {
      const { result } = renderHook(() => useSimpleSearch(), {
        wrapper: createWrapper(["/"]),
      });

      act(() => {
        const [, , submitQuery] = result.current;
        submitQuery("test query");
      });

      const [query] = result.current;
      expect(query).toBe("test query");
    });
  });

  describe("asynchronous navigation", () => {
    const cases = [
      {
        action: "submitQuery",
        invoke: (search: ReturnType<typeof useSimpleSearch>) =>
          search[2]("new query"),
        expectedSearch: "simple_search_query=new%20query&simple_search_page=1",
      },
      {
        action: "changePage",
        invoke: (search: ReturnType<typeof useSimpleSearch>) => search[3](3),
        expectedSearch: "simple_search_query=existing&simple_search_page=3",
      },
    ];

    test.each(
      cases,
    )("$action accepts a navigation that resolves asynchronously", async ({
      invoke,
      expectedSearch,
    }) => {
      let finishNavigation!: () => void;
      mockNavigation.enabled = true;
      mockNavigation.navigate.mockReturnValue(
        new Promise<void>((resolve) => {
          finishNavigation = resolve;
        }),
      );
      const onError = vi.fn();
      const wrapper: FC<{ children: ReactNode }> = ({ children }) => (
        <MemoryRouter initialEntries={["/?simple_search_query=existing"]}>
          <ErrorBoundary
            fallback={<div role="alert">Navigation failed</div>}
            onError={onError}
          >
            {children}
          </ErrorBoundary>
        </MemoryRouter>
      );
      const { result } = renderHook(() => useSimpleSearch(), { wrapper });

      act(() => invoke(result.current));
      expect(mockNavigation.navigate).toHaveBeenCalledWith({
        pathname: "/ui/",
        search: expectedSearch,
      });
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();

      await act(async () => {
        finishNavigation();
      });

      expect(onError).not.toHaveBeenCalled();
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });

    test.each(
      cases,
    )("$action sends a rejected navigation to the ErrorBoundary", async ({
      invoke,
    }) => {
      vi.spyOn(console, "error").mockImplementation(() => {});
      const error = new Error("Navigation rejected");
      mockNavigation.enabled = true;
      mockNavigation.navigate.mockRejectedValue(error);
      const onError = vi.fn();
      const wrapper: FC<{ children: ReactNode }> = ({ children }) => (
        <MemoryRouter>
          <ErrorBoundary
            fallback={<div role="alert">Navigation failed</div>}
            onError={onError}
          >
            {children}
          </ErrorBoundary>
        </MemoryRouter>
      );
      const { result } = renderHook(() => useSimpleSearch(), { wrapper });

      act(() => invoke(result.current));

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "Navigation failed",
      );
      expect(onError).toHaveBeenCalledWith(error, expect.anything());
    });
  });
});
