import { expect, Page, test } from "@playwright/test";

import { apiGet, postJson, username } from "./liveApi";

// Run against a disposable Django database with legacy UI enabled.
const quotedName = "quotes-'\"-[]#.:&-日本語";
const names = [
  "ordinary attribute",
  "advanced-search-hint-attrs",
  quotedName,
  "cell onmouseover=window.xssExecuted=true",
  "'></option><script>window.xssExecuted=true</script>",
];
let entityId: number;

const loginLegacy = async (page: Page) => {
  await page.goto("/auth/login/?next=/dashboard/advanced_search");
  await page.locator('input[name="username"]').fill(username);
  await page
    .locator('input[name="password"]')
    .fill(process.env.E2E_PASSWORD ?? "admin");
  await page.getByRole("button", { name: "Login", exact: true }).click();
  await page.waitForURL("**/dashboard/advanced_search");
};

const expectInert = async (page: Page) => {
  expect(
    await page.evaluate(
      () => (window as Window & { xssExecuted?: boolean }).xssExecuted,
    ),
  ).not.toBe(true);
  await expect(page.locator("#main_table td[onmouseover]")).toHaveCount(0);
};

test.beforeAll(async ({ browser }) => {
  const page = await browser.newPage();
  await loginLegacy(page);
  const name = `e2e-legacy-search-${Date.now()}`;
  await postJson(page, "/entity/api/v2/", {
    name,
    attrs: names.map((name, index) => ({ name, type: 2, index })),
  });
  await expect
    .poll(async () => {
      const response = await apiGet<{
        results: { id: number; name: string }[];
      }>(page, `/entity/api/v2/?search=${encodeURIComponent(name)}`);
      entityId =
        response.results.find((entity) => entity.name === name)?.id ?? 0;
      if (!entityId) return 0;
      const entity = await apiGet<{ attrs: unknown[] }>(
        page,
        `/entity/api/v2/${entityId}/`,
      );
      return entity.attrs.length;
    })
    .toBe(names.length);
  await page.close();
});

test.beforeEach(async ({ page }) => {
  await loginLegacy(page);
});

test.afterAll(async ({ browser }) => {
  if (!entityId) return;
  const page = await browser.newPage();
  await loginLegacy(page);
  const status = await page.evaluate(async (id) => {
    const csrfToken =
      document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/)?.[1] ?? "";
    return (
      await fetch(`/entity/api/v2/${id}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": decodeURIComponent(csrfToken) },
      })
    ).status;
  }, entityId);
  expect(status).toBe(202);
  await page.close();
});

for (const parameter of ["attr[]", "attrinfo"]) {
  test(`${parameter} names stay inert through page load and AJAX rendering`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const breakout =
      "]));}}}window.xssExecuted=true;function injected(){if(1){if(1){//\\";
    const exploitQuery = new URLSearchParams({ "entity[]": String(entityId) });
    exploitQuery.set(
      parameter,
      parameter === "attr[]" ? breakout : JSON.stringify([{ name: breakout }]),
    );
    await page.goto(`/dashboard/advanced_search_result?${exploitQuery}`);
    await expectInert(page);
    expect(errors).toEqual([]);
    const hintNames = [
      ...names,
      "trailing-backslash\\",
      breakout,
      "line\nbreak\u2028\u2029",
    ];
    const query = new URLSearchParams({ "entity[]": String(entityId) });
    if (parameter === "attr[]") {
      for (const name of hintNames) query.append(parameter, name);
    } else {
      query.set(parameter, JSON.stringify(hintNames.map((name) => ({ name }))));
    }
    await page.goto(`/dashboard/advanced_search_result?${query}`);
    await expect(page.locator(".hint_attr_value")).toHaveCount(
      hintNames.length,
    );
    await expectInert(page);
    let searches = 0;
    await page.route("**/api/v1/entry/search", async (route) => {
      const value = ++searches === 1 ? "value" : "updated";
      expect(route.request().postDataJSON().attrinfo).toEqual(
        hintNames.map((name) => ({ name })),
      );
      await route.fulfill({
        json: {
          result: {
            ret_count: 2,
            ret_values: [true, false].map((is_readable) => ({
              is_readable,
              entry: { id: 1, name: "entry" },
              entity: { id: entityId, name: "entity" },
              attrs: Object.fromEntries(
                hintNames.map((name) => [name, { type: 2, value }]),
              ),
            })),
          },
        },
      });
    });
    await page.locator(".hint_entry_name").press("Enter");
    await expect(page.locator("#main_table tr")).toHaveCount(2);
    for (const row of await page.locator("#main_table tr").all()) {
      expect(
        await row
          .locator("td")
          .evaluateAll((cells) => cells.map((cell) => cell.id)),
      ).toEqual(hintNames);
    }
    await expect(
      page.locator("#main_table tr").first().locator("td"),
    ).toHaveText(hintNames.map(() => "value"));
    await expect(
      page.locator("#main_table tr").last().locator("td"),
    ).toHaveText(hintNames.map(() => "Permission denied."));
    await page.locator(".hint_entry_name").press("Enter");
    await expect(
      page.locator("#main_table tr").first().locator("td"),
    ).toHaveText(hintNames.map(() => "updated"));
    await expectInert(page);
    expect(errors).toEqual([]);
  });
}

test("stored attribute names remain text in both selectors and preserve filters", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.locator("#all_entity").selectOption(String(entityId));
  await page.locator("#append_target_entity").click();
  await expect(page.locator("#all_attr option")).toHaveCount(names.length);
  await expectInert(page);
  for (const name of names) {
    const option = page.locator("#all_attr option").filter({ hasText: name });
    await expect(option).toHaveAttribute("value", name);
    await expect(option).toHaveText(name);
  }
  await expectInert(page);
  await page.locator("#all_attr").selectOption(names);
  await page.locator("#append_target_attr").click();
  await page.locator("#append_target_attr").click();
  await expect(page.locator("#selected_attr option")).toHaveCount(names.length);
  await page.locator("#do_search").click();
  await page.waitForURL("**/dashboard/advanced_search_result?**");
  const keywordIndex = [...names].sort().indexOf(quotedName);
  await page
    .locator(".hint_attr_value")
    .nth(keywordIndex)
    .fill("preserved keyword");
  await page.locator("#show_renew_search_attr_condition").click();
  await expect(page.locator("#modal_condition_all_attr option")).toHaveCount(
    names.length,
  );
  await expectInert(page);
  expect(
    await page
      .locator("#modal_condition_all_attr option")
      .evaluateAll((options) =>
        options.map((option) => ({
          value: (option as HTMLOptionElement).value,
          text: option.textContent,
        })),
      ),
  ).toEqual(
    names
      .map((name) => ({ value: name, text: name }))
      .sort((a, b) => (a.value < b.value ? -1 : a.value > b.value ? 1 : 0)),
  );
  await page.locator("#modal_condition_all_attr").selectOption(names);
  await page.locator(".append_attr").click();
  await expect(
    page.locator("#modal_condition_selected_attr option"),
  ).toHaveCount(names.length);
  await expectInert(page);
  await page.locator("#commit_condition_change").click();
  await page.waitForURL(
    (url) =>
      url.searchParams.get("attrinfo")?.includes("preserved keyword") ?? false,
  );
  const hints = JSON.parse(
    new URL(page.url()).searchParams.get("attrinfo") ?? "[]",
  );
  expect(hints).toContainEqual({
    name: quotedName,
    keyword: "preserved keyword",
  });
  await expect(page.locator(".hint_attr_value").nth(keywordIndex)).toHaveValue(
    "preserved keyword",
  );
  await expectInert(page);
  expect(errors).toEqual([]);
});
