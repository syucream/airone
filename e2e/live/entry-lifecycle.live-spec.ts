import { expect, test } from "@playwright/test";

import { captureEvidence } from "./liveEvidence";

import {
  attrValue,
  entryDetail,
  fixture,
  listEntries,
  PASSWORD,
  REFERENCE_ENTRY,
  waitForJobStatus,
} from "./liveServiceFixture";
import { apiGet, login } from "./liveApi";

test("editor creates and updates a referenced item, then finds the indexed value", async ({
  page,
}, testInfo) => {
  await login(page, { username: "e2e-editor", password: PASSWORD });
  const { target } = await fixture(page);
  const suffix = `${Date.now()}`;
  const name = `e2e-lifecycle-${suffix}`;
  const initialDescription = `lifecycle initial ${suffix}`;
  const updatedDescription = `lifecycle updated ${suffix}`;

  await page.goto(`/ui/entities/${target.id}/entries/new`);
  await page.locator("#entry-name").fill(name);
  const descriptionRow = page
    .getByRole("row")
    .filter({ has: page.getByText("description", { exact: true }) });
  await descriptionRow.locator("input").fill(initialDescription);
  const referenceRow = page
    .getByRole("row")
    .filter({ has: page.getByText("reference", { exact: true }) });
  await referenceRow.getByRole("combobox").fill(REFERENCE_ENTRY);
  await page.getByRole("option", { name: REFERENCE_ENTRY }).click();
  await page.locator("#entry-name").press("Tab");
  await expect(page.getByRole("button", { name: "保存" })).toBeEnabled();
  await page.getByRole("button", { name: "保存" }).click();

  let createdId = 0;
  await expect
    .poll(
      async () => {
        createdId =
          (await listEntries(page, target.id, true, name)).find(
            (item) => item.name === name,
          )?.id ?? 0;
        return createdId;
      },
      { timeout: 60_000 },
    )
    .toBeGreaterThan(0);
  await waitForJobStatus(page, createdId, 27);

  await page.goto(`/ui/entities/${target.id}/entries/${createdId}/details`);
  await expect(
    page.getByText(initialDescription, { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(REFERENCE_ENTRY, { exact: true })).toBeVisible();

  await page.locator("#entryMenu").click();
  await page.getByText("編集", { exact: true }).click();
  await descriptionRow.locator("input").fill(updatedDescription);
  await descriptionRow.locator("input").press("Tab");
  await page.getByRole("button", { name: "保存" }).click();
  await expect
    .poll(
      async () =>
        attrValue(await entryDetail(page, createdId), "description")?.as_string,
      { timeout: 60_000 },
    )
    .toBe(updatedDescription);
  await waitForJobStatus(page, createdId, 28);

  await page.reload();
  await expect(
    page.getByText(updatedDescription, { exact: true }),
  ).toBeVisible();
  const detail = await entryDetail(page, createdId);
  expect(attrValue(detail, "reference")?.as_object?.name).toBe(REFERENCE_ENTRY);

  await expect
    .poll(
      async () =>
        (
          await apiGet<{ id: number }[]>(
            page,
            `/entry/api/v2/search/?query=${encodeURIComponent(updatedDescription)}`,
          )
        ).map((item) => item.id),
      { timeout: 30_000 },
    )
    .toContain(createdId);
  expect(
    (
      await apiGet<{ id: number }[]>(
        page,
        `/entry/api/v2/search/?query=${encodeURIComponent(initialDescription)}`,
      )
    ).map((item) => item.id),
  ).not.toContain(createdId);

  await captureEvidence(page, testInfo, {
    name: "entry-lifecycle-live-service",
    title: "Referenced item lifecycle",
    note: "A writable user created and updated an item, retained its reference, completed background jobs, and observed the updated value in Elasticsearch.",
  });
});
