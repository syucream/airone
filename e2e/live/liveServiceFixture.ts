import { expect, Page } from "@playwright/test";

import { apiGet } from "./liveApi";

export const PASSWORD = "e2e-password";
export const TARGET_ENTITY = "E2E Asset Catalog";
export const REFERENCE_ENTITY = "E2E Asset References";
export const REFERENCE_ENTRY = "e2e-reference-alpha";
export const REGION_CODE = "jp-east-1";
export const REGION_CODE_OTHER = "jp-west-1";
export const PROTECTED_ENTRY = "e2e-protected-entry";
export const DECOY_ENTRY = "e2e-decoy-entry";
export const HIDDEN_ENTRY = "e2e-hidden-entry";
export const RESTRICTED_PATH_ENTRY = "e2e-asset-with-restricted-reference";

interface ListItem {
  id: number;
  name: string;
}

interface ListResponse {
  results: ListItem[];
}

interface JobSummary {
  id: number;
  operation: number;
  status: number;
  text: string;
}

interface EntryDetail {
  id: number;
  name: string;
  is_active?: boolean;
  attrs: {
    schema: { name: string };
    value: {
      as_string?: string;
      as_object?: { id: number; name: string } | null;
    };
  }[];
}

export const fixture = async (page: Page) => {
  const findEntity = async (name: string) => {
    const entities = await apiGet<ListResponse>(
      page,
      `/entity/api/v2/?search=${encodeURIComponent(name)}`,
    );
    return entities.results.find((item) => item.name === name);
  };
  const target = await findEntity(TARGET_ENTITY);
  expect(target, "asset catalog fixture entity should exist").toBeDefined();
  if (target == null)
    throw new Error("asset catalog fixture entity is missing");

  const referenceEntity = await findEntity(REFERENCE_ENTITY);
  expect(
    referenceEntity,
    "reference fixture entity should exist",
  ).toBeDefined();
  if (referenceEntity == null)
    throw new Error("reference fixture entity is missing");

  const entries = await listEntries(page, target.id, true, PROTECTED_ENTRY);
  const protectedEntry = entries.find((item) => item.name === PROTECTED_ENTRY);
  expect(protectedEntry, "protected fixture entry should exist").toBeDefined();
  if (protectedEntry == null)
    throw new Error("protected fixture entry is missing");

  const referenceEntries = await listEntries(
    page,
    referenceEntity.id,
    true,
    REFERENCE_ENTRY,
  );
  const referenceEntry = referenceEntries.find(
    (item) => item.name === REFERENCE_ENTRY,
  );
  expect(referenceEntry, "reference fixture entry should exist").toBeDefined();
  if (referenceEntry == null)
    throw new Error("reference fixture entry is missing");

  return { target, protectedEntry, referenceEntity, referenceEntry };
};

export const listEntries = async (
  page: Page,
  entityId: number,
  active = true,
  search?: string,
) =>
  (
    await apiGet<ListResponse>(
      page,
      `/entity/api/v2/${entityId}/entries/?is_active=${active}${
        search == null ? "" : `&search=${encodeURIComponent(search)}`
      }`,
    )
  ).results;

export const entryDetail = (page: Page, entryId: number) =>
  apiGet<EntryDetail>(page, `/entry/api/v2/${entryId}/`);

export const attrValue = (detail: EntryDetail, name: string) =>
  detail.attrs.find((attr) => attr.schema.name === name)?.value;

export const waitForJobStatus = async (
  page: Page,
  targetId: number,
  operation: number,
  afterJobId = 0,
  expectedStatus = 2,
) => {
  await expect
    .poll(
      async () => {
        return (await jobAfter(page, targetId, operation, afterJobId))?.status;
      },
      { timeout: 60_000 },
    )
    .toBe(expectedStatus);
};

export const jobAfter = async (
  page: Page,
  targetId: number,
  operation: number,
  afterJobId = 0,
) => {
  const jobs = await apiGet<{ results: JobSummary[] }>(
    page,
    `/job/api/v2/jobs?target_id=${targetId}`,
  );
  return jobs.results.find(
    (job) => job.operation === operation && job.id > afterJobId,
  );
};

export const latestJobId = async (
  page: Page,
  targetId: number,
  operation: number,
) => {
  const jobs = await apiGet<{ results: JobSummary[] }>(
    page,
    `/job/api/v2/jobs?target_id=${targetId}`,
  );
  return Math.max(
    0,
    ...jobs.results
      .filter((job) => job.operation === operation)
      .map((job) => job.id),
  );
};
