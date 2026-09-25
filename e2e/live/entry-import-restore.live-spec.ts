import { expect, test } from "@playwright/test";

import { captureEvidence } from "./liveEvidence";

import {
  attrValue,
  entryDetail,
  fixture,
  jobAfter,
  latestJobId,
  listEntries,
  PASSWORD,
  REFERENCE_ENTRY,
  REFERENCE_ENTITY,
  TARGET_ENTITY,
  waitForJobStatus,
} from "./liveServiceFixture";
import { apiGet, login } from "./liveApi";

test("previews and applies an item import, then preserves values across delete and restore", async ({
  browser,
  page,
}, testInfo) => {
  await login(page);
  const { target, protectedEntry, referenceEntity, referenceEntry } =
    await fixture(page);
  const suffix = `${Date.now()}`;
  const importedName = `e2e-imported-${suffix}`;
  const protectedValue = `previewed update ${suffix}`;
  const concurrentValue = `concurrent update ${suffix}`;
  const importedValue = `imported and restored ${suffix}`;
  const referenceValue = `reference updated ${suffix}`;
  const protectedValueBeforePreview = attrValue(
    await entryDetail(page, protectedEntry.id),
    "description",
  )?.as_string;
  const referenceValueBeforePreview = attrValue(
    await entryDetail(page, referenceEntry.id),
    "label",
  )?.as_string;
  const yaml = [
    `- entity: ${TARGET_ENTITY}`,
    "  entries:",
    `  - name: ${protectedEntry.name}`,
    "    attrs:",
    "    - name: description",
    `      value: ${protectedValue}`,
    `  - name: ${importedName}`,
    "    attrs:",
    "    - name: description",
    `      value: ${importedValue}`,
    "    - name: reference",
    `      value: {name: ${REFERENCE_ENTRY}, entity: ${REFERENCE_ENTITY}}`,
    `- entity: ${REFERENCE_ENTITY}`,
    "  entries:",
    `  - name: ${referenceEntry.name}`,
    "    attrs:",
    "    - name: label",
    `      value: ${referenceValue}`,
  ].join("\n");

  await page.goto(`/ui/entities/${target.id}/entries`);
  await page.locator("#entity_menu").click();
  await page.getByRole("menuitem", { name: "インポート" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "entry-import-restore.yaml",
    mimeType: "application/yaml",
    buffer: Buffer.from(yaml, "utf-8"),
  });
  await page.getByTestId("preview-import-file").click();
  const preview = page.getByTestId("import-preview");
  await expect(preview).toBeVisible({ timeout: 60_000 });
  await expect(preview.getByText("新規作成 1")).toBeVisible();
  await expect(preview.getByText("更新 2")).toBeVisible();
  await expect(preview.getByText(importedName, { exact: true })).toBeVisible();

  expect(
    (await listEntries(page, target.id, true, importedName)).some(
      (item) => item.name === importedName,
    ),
  ).toBe(false);
  expect(
    attrValue(await entryDetail(page, protectedEntry.id), "description")
      ?.as_string,
  ).toBe(protectedValueBeforePreview);
  expect(
    attrValue(await entryDetail(page, referenceEntry.id), "label")?.as_string,
  ).toBe(referenceValueBeforePreview);
  await captureEvidence(page, testInfo, {
    name: "entry-import-preview",
    title: "Entry import preview",
    note: "The real multi-entity preview reported one creation and two updates while the database remained unchanged.",
  });

  const concurrentContext = await browser.newContext();
  const concurrentPage = await concurrentContext.newPage();
  await login(concurrentPage, {
    username: "e2e-editor",
    password: PASSWORD,
  });
  const editJobWatermark = await latestJobId(
    concurrentPage,
    protectedEntry.id,
    28,
  );
  await concurrentPage.goto(
    `/ui/entities/${target.id}/entries/${protectedEntry.id}/details`,
  );
  await concurrentPage.locator("#entryMenu").click();
  await concurrentPage.getByText("編集", { exact: true }).click();
  const descriptionRow = concurrentPage
    .getByRole("row")
    .filter({ has: concurrentPage.getByText("description", { exact: true }) });
  await descriptionRow.locator("input").fill(concurrentValue);
  await descriptionRow.locator("input").press("Tab");
  await concurrentPage.getByRole("button", { name: "保存" }).click();
  await expect
    .poll(
      async () =>
        attrValue(
          await entryDetail(concurrentPage, protectedEntry.id),
          "description",
        )?.as_string,
      { timeout: 60_000 },
    )
    .toBe(concurrentValue);
  await waitForJobStatus(
    concurrentPage,
    protectedEntry.id,
    28,
    editJobWatermark,
  );
  await concurrentContext.close();

  const importJobWatermark = await latestJobId(page, target.id, 17);
  const referenceImportJobWatermark = await latestJobId(
    page,
    referenceEntity.id,
    17,
  );
  await page.getByRole("checkbox", { name: "強制インポート" }).check();
  await page.getByRole("button", { name: "インポート" }).last().click();
  let importedId = 0;
  await expect
    .poll(
      async () => {
        importedId =
          (await listEntries(page, target.id, true, importedName)).find(
            (item) => item.name === importedName,
          )?.id ?? 0;
        return importedId;
      },
      { timeout: 60_000 },
    )
    .toBeGreaterThan(0);
  await waitForJobStatus(page, target.id, 17, importJobWatermark, 7);
  const targetImportJob = await jobAfter(
    page,
    target.id,
    17,
    importJobWatermark,
  );
  expect(targetImportJob?.text).toContain(
    `Skipped stale Entry: [${protectedEntry.name}]`,
  );
  expect(targetImportJob?.text).not.toContain("Failed import Entry");
  await waitForJobStatus(
    page,
    referenceEntity.id,
    17,
    referenceImportJobWatermark,
  );

  let detail = await entryDetail(page, importedId);
  expect(attrValue(detail, "description")?.as_string).toBe(importedValue);
  const importedReference = attrValue(detail, "reference")?.as_object;
  expect(importedReference?.name).toBe(REFERENCE_ENTRY);
  expect(importedReference?.id).toBeGreaterThan(0);
  expect(
    attrValue(await entryDetail(page, protectedEntry.id), "description")
      ?.as_string,
  ).toBe(concurrentValue);
  expect(
    attrValue(await entryDetail(page, referenceEntry.id), "label")?.as_string,
  ).toBe(referenceValue);

  await page.goto(`/ui/entities/${target.id}/entries/${importedId}/details`);
  await page.locator("#entryMenu").click();
  await page.getByText("削除", { exact: true }).click();
  await page.getByRole("button", { name: "Yes" }).click();
  await expect
    .poll(
      async () =>
        (await listEntries(page, target.id, true, importedName)).some(
          (item) => item.id === importedId,
        ),
      { timeout: 60_000 },
    )
    .toBe(false);
  await waitForJobStatus(page, importedId, 29);
  await expect
    .poll(
      async () =>
        (
          await apiGet<{ id: number }[]>(
            page,
            `/entry/api/v2/search/?query=${encodeURIComponent(importedValue)}`,
          )
        ).map((item) => item.id),
      { timeout: 30_000 },
    )
    .not.toContain(importedId);

  await page.goto(
    `/ui/entities/${target.id}/restore?query=${encodeURIComponent(importedName)}`,
  );
  await page.getByText(importedName, { exact: true }).click();
  await expect(page.getByText(importedValue, { exact: true })).toBeVisible();
  await expect(page.getByText(REFERENCE_ENTRY, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "復旧" }).click();
  await page.getByRole("button", { name: "Yes" }).click();
  await expect
    .poll(
      async () =>
        (await listEntries(page, target.id, true, importedName)).find(
          (item) => item.name === importedName,
        )?.id,
      { timeout: 30_000 },
    )
    .toBe(importedId);

  detail = await entryDetail(page, importedId);
  expect(attrValue(detail, "description")?.as_string).toBe(importedValue);
  expect(attrValue(detail, "reference")?.as_object?.name).toBe(REFERENCE_ENTRY);
  expect(attrValue(detail, "reference")?.as_object?.id).toBe(
    importedReference?.id,
  );
  await expect
    .poll(
      async () =>
        (
          await apiGet<{ id: number }[]>(
            page,
            `/entry/api/v2/search/?query=${encodeURIComponent(importedValue)}`,
          )
        ).map((item) => item.id),
      { timeout: 30_000 },
    )
    .toContain(importedId);

  await page.goto(`/ui/entities/${target.id}/entries/${importedId}/details`);
  await captureEvidence(page, testInfo, {
    name: "entry-import-restored",
    title: "Imported entry restored",
    note: "The imported item kept its identity, scalar value, reference, and search visibility after UI delete and restore.",
  });
});
