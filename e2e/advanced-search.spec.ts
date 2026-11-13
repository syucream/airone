import { expect, test } from "@playwright/test";

import {
  collectBrowserFailures,
  expectAccessibility,
  expectNoBrowserFailures,
  expectUiQualityGate,
} from "./browserQuality";
import { captureEvidence } from "./reportEvidence";

// Controls are located by their Japanese labels.
test.use({ locale: "ja-JP" });

const failureMap = new WeakMap<object, string[]>();

test.beforeEach(async ({ page, request }, testInfo) => {
  expect((await request.post("/__e2e/reset")).status()).toBe(204);
  failureMap.set(testInfo, collectBrowserFailures(page));
});

test.afterEach(async ({ page }, testInfo) => {
  await expectUiQualityGate(page, testInfo);
  expectNoBrowserFailures(failureMap.get(testInfo) ?? []);
});

test("@advanced-search creates, reads, updates, and clears search criteria", async ({
  page,
}, testInfo) => {
  await page.goto("/ui/advanced_search");

  const entitySelector = page.getByPlaceholder("モデルを選択");
  await entitySelector.click();
  await page.getByRole("option", { name: "Server" }).click();

  const attrSelector = page.getByPlaceholder("属性を選択");
  await attrSelector.click();
  await page.getByRole("option", { name: "すべて選択" }).click();
  await page.getByText("参照アイテムも含める").getByRole("checkbox").check();

  const search = page.getByRole("link", { name: "検索", exact: true });
  await expect(search).toBeEnabled();
  await search.click();
  await expect(page).toHaveURL(/\/ui\/advanced_search_result\?/);
  await expect(page.getByText("web-01", { exact: true })).toBeVisible();
  await expect(page.getByText("db-01", { exact: true })).toBeVisible();
  await expectAccessibility(page, testInfo);

  let releaseReferrals = () => {};
  const referralsReady = new Promise<void>((resolve) => {
    releaseReferrals = resolve;
  });
  await page.route(
    /\/entry\/api\/v2\/\d+\/referral\/?(?:\?.*)?$/,
    async (route) => {
      await referralsReady;
      await route.continue();
    },
  );
  try {
    await page
      .getByRole("columnheader", { name: /hostname/ })
      .getByRole("button", { name: "属性値でフィルタ" })
      .click();
    await page.getByText("一括更新", { exact: true }).click();
    await expect(
      page.getByRole("progressbar", { name: "対象アイテムの確認中" }).first(),
    ).toBeVisible();
    await expectAccessibility(page, testInfo);
  } finally {
    releaseReferrals();
  }
  await expect(
    page.getByRole("button", { name: "更新", exact: true }),
  ).toBeEnabled();
  await expect(page.getByRole("textbox", { name: /hostname/ })).toBeVisible();
  await expectAccessibility(page, testInfo);
  await page.keyboard.press("Escape");

  await page.goto("/ui/advanced_search");
  await entitySelector.click();
  await page.getByRole("option", { name: "Switch" }).click();
  await expect(page.getByRole("button", { name: "Switch" })).toBeVisible();

  await page
    .getByRole("button", { name: "Switch" })
    .getByTestId("CancelIcon")
    .click();
  await expect(
    page.getByRole("link", { name: "検索", exact: true }),
  ).toHaveAttribute("aria-disabled", "true");

  await captureEvidence(page, testInfo, {
    name: "advanced-search-lifecycle",
    title: "Advanced Search Lifecycle",
    note: "Created, executed, updated, and cleared exhaustive search criteria.",
  });
});
