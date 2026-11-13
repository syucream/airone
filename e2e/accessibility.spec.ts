import { AxeBuilder } from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { expectAccessibility } from "./browserQuality";

test("header menus support keyboard activation and restore focus", async ({
  page,
}, testInfo) => {
  await page.goto("/ui/");
  await expect(page.getByText("Operations")).toBeVisible();
  for (const name of ["Open user menu", "Open job menu"]) {
    // MUI hides the page from assistive technology while its modal is open.
    const button = page.getByRole("button", { name, includeHidden: true });
    await button.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("menu")).toBeVisible();
    await expect(button).toHaveAttribute("aria-expanded", "true");
    await expectAccessibility(page, testInfo);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("menu")).toBeHidden();
    await expect(button).toBeFocused();
    await expect(button).toHaveAttribute("aria-expanded", "false");
  }
  await expectAccessibility(page, testInfo);
});

// These probes exercise the same assertion as the application tests. A green
// suite must mean that the gate rejects regressions, not just that axe runs.
const regressions = [
  {
    rule: "button-name",
    html: '<button><span aria-hidden="true">+</span></button>',
  },
  { rule: "label", html: '<input type="text">' },
  {
    rule: "color-contrast",
    html: '<p style="color:#aaa;background:#fff">Low contrast text</p>',
  },
  { rule: "list", html: "<ul><div>Not a list item</div></ul>" },
];

for (const { rule, html } of regressions) {
  test(`accessibility gate rejects ${rule} previously hidden by global exclusions`, async ({
    page,
  }, testInfo) => {
    await page.route("**/a11y-probe", (route) =>
      route.fulfill({
        contentType: "text/html",
        body: '<!doctype html><html lang="en"><head><title>Gate probe</title></head><body><main><h1>Gate probe</h1></main></body></html>',
      }),
    );
    await page.goto("/a11y-probe");
    await expectAccessibility(page, testInfo);
    await page.locator("main").evaluate((element, markup) => {
      element.insertAdjacentHTML("beforeend", markup);
    }, html);

    const oldResults = await new AxeBuilder({ page })
      .disableRules(["button-name", "color-contrast", "label", "list"])
      .analyze();
    expect(
      oldResults.violations.filter(
        ({ impact }) => impact === "critical" || impact === "serious",
      ),
    ).toEqual([]);
    await expect(expectAccessibility(page, testInfo)).rejects.toThrow(rule);
  });
}
