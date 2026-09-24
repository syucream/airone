/**
 * @jest-environment jsdom
 */

import { render, screen, act, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { createMemoryRouter, RouterProvider } from "react-router";

import { TestWrapperWithoutRoutes } from "TestWrapper";
import i18n from "i18n/config";
import { UserEditPage } from "pages/UserEditPage";

const server = setupServer(
  // getUser
  http.get("http://localhost/role/api/v2/roles/1", () => {
    return HttpResponse.json({
      id: 1,
      username: "user1",
      email: "user1@example.com",
      is_superuser: false,
    });
  }),
);

beforeAll(() => server.listen());

afterEach(() => server.resetHandlers());

afterAll(() => server.close());

describe("EditUserPage", () => {
  Object.defineProperty(window, "django_context", {
    value: {
      user: {
        is_superuser: false,
      },
    },
    writable: false,
  });

  test("should match snapshot", async () => {
    const router = createMemoryRouter([
      {
        path: "/",
        element: <UserEditPage />,
      },
    ]);
    const result = await act(async () => {
      return render(<RouterProvider router={router} />, {
        wrapper: TestWrapperWithoutRoutes,
      });
    });
    await waitFor(() => {
      expect(screen.queryByTestId("loading")).not.toBeInTheDocument();
    });

    expect(result).toMatchSnapshot();
  });

  test("renders in English", async () => {
    await act(async () => {
      await i18n.changeLanguage("en");
    });

    const router = createMemoryRouter([
      {
        path: "/",
        element: <UserEditPage />,
      },
    ]);
    await act(async () => {
      render(<RouterProvider router={router} />, {
        wrapper: TestWrapperWithoutRoutes,
      });
    });
    await waitFor(() => {
      expect(screen.queryByTestId("loading")).not.toBeInTheDocument();
    });

    expect(screen.getByText("User settings")).toBeInTheDocument();
  });
});
