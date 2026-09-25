import { Page } from "@playwright/test";

/**
 * Helpers for talking to the real server from the live suite.
 *
 * Requests share the browser context's session cookies. Read requests use its
 * API request context so polling survives page navigation; writes run in the
 * page to use the same CSRF cookie handling as the UI.
 */

export const username = process.env.E2E_USERNAME ?? "admin";
const password = process.env.E2E_PASSWORD ?? "admin";

export const login = async (
  page: Page,
  credentials: { username: string; password: string } = {
    username,
    password,
  },
) => {
  await page.context().clearCookies();
  await page.goto("/auth/login/");
  await page.fill('input[name="username"]', credentials.username);
  await page.fill('input[name="password"]', credentials.password);
  await page.getByRole("button", { name: "Login" }).click();
  await page.waitForURL(/\/ui\//);
};

export const apiStatus = async (
  page: Page,
  url: string,
  init: { method?: string; body?: unknown } = {},
): Promise<number> =>
  page.evaluate(
    async ({ target, request }) => {
      const headers: Record<string, string> = { Accept: "application/json" };
      if (request.body !== undefined) {
        const token =
          document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/)?.[1] ?? "";
        headers["Content-Type"] = "application/json";
        headers["X-CSRFToken"] = decodeURIComponent(token);
      }
      const response = await fetch(target, {
        method: request.method ?? "GET",
        headers,
        body:
          request.body === undefined ? undefined : JSON.stringify(request.body),
      });
      return response.status;
    },
    { target: url, request: init },
  );

export const apiGet = async <T>(page: Page, url: string): Promise<T> => {
  const cookieHeader = (await page.context().cookies())
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");
  const response = await page.context().request.get(url, {
    headers: { Accept: "application/json", Cookie: cookieHeader },
  });
  if (!response.ok()) {
    throw new Error(`GET ${url} failed with ${response.status()}`);
  }
  return response.json();
};

export const apiPost = async <T>(
  page: Page,
  url: string,
  body: unknown,
): Promise<T> =>
  page.evaluate(
    async ({ target, payload }) => {
      const token =
        document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/)?.[1] ?? "";
      const response = await fetch(target, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": decodeURIComponent(token),
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(
          `POST ${target} failed with ${response.status}: ${await response.text()}`,
        );
      }
      return response.json();
    },
    { target: url, payload: body },
  );

export const postYaml = async (
  page: Page,
  url: string,
  body: string,
): Promise<void> =>
  page.evaluate(
    async ({ target, payload }) => {
      const csrfToken =
        document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/)?.[1] ?? "";
      const response = await fetch(target, {
        method: "POST",
        headers: {
          "Content-Type": "application/yaml",
          "X-CSRFToken": decodeURIComponent(csrfToken),
        },
        body: payload,
      });
      if (!response.ok) {
        throw new Error(
          `POST ${target} failed with ${response.status}: ${await response.text()}`,
        );
      }
    },
    { target: url, payload: body },
  );
