import { readdir } from "node:fs/promises";
import path from "node:path";

import { expect, Page, test } from "@playwright/test";

const chunkName = /^.+\.[a-f0-9]{12}\.ui\.js$/;
const staticDir = path.resolve(process.cwd(), "static/js");

const watchScripts = (page: Page) => {
  const scripts = new Set<string>();
  const failures: string[] = [];
  page.on("response", (response) => {
    if (response.request().resourceType() !== "script") return;
    scripts.add(response.url());
    if (!response.ok()) failures.push(`${response.status()} ${response.url()}`);
  });
  page.on("requestfailed", (request) => {
    if (request.resourceType() === "script") {
      failures.push(`${request.failure()?.errorText} ${request.url()}`);
    }
  });
  return { scripts, failures };
};

const chunks = (scripts: Set<string>) =>
  [...scripts].filter((url) =>
    chunkName.test(path.basename(new URL(url).pathname)),
  );

const expectDetail = async (page: Page) => {
  await expect(page.getByRole("heading", { name: "web-01" })).toBeVisible();
  await expect(page.getByText("web-01.example.test")).toBeVisible();
};

test.use({ locale: "ja-JP" });

test("@bundle cold dashboard defers route chunks until client navigation", async ({
  page,
}) => {
  const delivery = watchScripts(page);
  await page.goto("/ui/");
  await expect(page.getByText("Operations")).toBeVisible();
  const dashboardChunks = chunks(delivery.scripts);
  expect(dashboardChunks.length).toBeGreaterThan(0);
  const emittedChunks = (await readdir(staticDir)).filter((file) =>
    chunkName.test(file),
  );
  expect(dashboardChunks.length).toBeLessThan(emittedChunks.length);

  let documentRequests = 0;
  page.on("request", (request) => {
    if (request.isNavigationRequest() && request.frame() === page.mainFrame()) {
      documentRequests++;
    }
  });
  await page.getByRole("link", { name: "Server", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "web-01", exact: true }),
  ).toBeVisible();
  const listChunks = chunks(delivery.scripts);
  expect(listChunks.length).toBeGreaterThan(dashboardChunks.length);
  await page.getByRole("link", { name: "web-01", exact: true }).click();
  await expectDetail(page);
  expect(chunks(delivery.scripts).length).toBeGreaterThan(listChunks.length);
  expect(documentRequests).toBe(0);
  expect(delivery.failures).toEqual([]);
});

for (const route of ["/ui/entities/1/entries/1/details", "/auth/login"]) {
  test(`@bundle direct route ${route} resolves its chunks`, async ({
    page,
  }) => {
    const delivery = watchScripts(page);
    await page.goto(route);
    if (route === "/auth/login") {
      await expect(
        page.getByRole("button", { name: "Login", exact: true }),
      ).toBeVisible();
    } else {
      await expectDetail(page);
    }
    expect(chunks(delivery.scripts).length).toBeGreaterThan(0);
    for (const script of delivery.scripts) {
      expect(new URL(script).pathname).toMatch(/^\/static\/js\//);
    }
    expect(delivery.failures).toEqual([]);
  });
}

test("@bundle chunks follow the entry script's CDN base on a nested route", async ({
  page,
}) => {
  const assetBase = "https://assets.example.test/pagoda/js/";
  const delivery = watchScripts(page);
  await page.route(`${assetBase}*`, async (route) => {
    const file = path.basename(new URL(route.request().url()).pathname);
    await route.fulfill({
      path: path.join(staticDir, file),
      contentType: "application/javascript",
      headers: { "access-control-allow-origin": "*" },
    });
  });
  await page.route("**/ui/entities/1/entries/1/details", async (route) => {
    const response = await route.fetch();
    const body = (await response.text()).replace(
      'src="/static/js/ui.js"',
      `src="${assetBase}ui.js"`,
    );
    await route.fulfill({ response, body });
  });
  await page.goto("/ui/entities/1/entries/1/details");
  await expectDetail(page);
  expect(chunks(delivery.scripts).length).toBeGreaterThan(0);
  for (const script of delivery.scripts) expect(script).toContain(assetBase);
  expect(delivery.failures).toEqual([]);
});

test("@bundle a missing chunk offers explicit reload and recovers", async ({
  page,
}) => {
  let failedChunk: string | undefined;
  let documentRequests = 0;
  page.on("request", (request) => {
    if (request.isNavigationRequest() && request.frame() === page.mainFrame()) {
      documentRequests++;
    }
  });
  await page.route("**/static/js/*.ui.js", async (route) => {
    if (!failedChunk) {
      failedChunk = route.request().url();
      await route.fulfill({ status: 404, body: "Missing deployment chunk" });
    } else {
      await route.continue();
    }
  });
  await page.goto("/ui/");
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("ChunkLoadError");
  expect(failedChunk).toBeDefined();
  expect(documentRequests).toBe(1);
  await page.unroute("**/static/js/*.ui.js");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "リロードする" }).click();
  await expect(page.getByText("Operations")).toBeVisible();
  await expect(dialog).toBeHidden();
  expect(documentRequests).toBe(2);
});
