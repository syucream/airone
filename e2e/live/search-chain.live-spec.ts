import { expect, Page, test } from "@playwright/test";

import { captureEvidence } from "./liveEvidence";

import {
  DECOY_ENTRY,
  fixture,
  HIDDEN_ENTRY,
  PASSWORD,
  PROTECTED_ENTRY,
  RESTRICTED_PATH_ENTRY,
  REGION_CODE,
  REGION_CODE_OTHER,
  TARGET_ENTITY,
} from "./liveServiceFixture";
import { apiPost, login } from "./liveApi";

interface SearchChainResult {
  id: number;
  name: string;
}

const searchByRegion = (page: Page, code: string) =>
  apiPost<SearchChainResult[]>(page, "/entry/api/v2/advanced_search_chain/", {
    entities: [TARGET_ENTITY],
    attrs: [
      {
        name: "reference",
        attrs: [
          {
            name: "region",
            attrs: [{ name: "code", value: code }],
          },
        ],
      },
    ],
  });

test("searches a two-hop reference graph without crossing ACL boundaries", async ({
  page,
}, testInfo) => {
  await login(page, { username: "e2e-viewer", password: PASSWORD });
  const { target, protectedEntry } = await fixture(page);

  const eastResults = await searchByRegion(page, REGION_CODE);
  expect(eastResults.map((entry) => entry.name)).toContain(PROTECTED_ENTRY);
  expect(eastResults.map((entry) => entry.name)).not.toContain(DECOY_ENTRY);
  expect(eastResults.map((entry) => entry.name)).not.toContain(HIDDEN_ENTRY);
  expect(eastResults.map((entry) => entry.name)).not.toContain(
    RESTRICTED_PATH_ENTRY,
  );

  const westResults = await searchByRegion(page, REGION_CODE_OTHER);
  expect(westResults.map((entry) => entry.name)).toContain(DECOY_ENTRY);
  expect(westResults.map((entry) => entry.name)).not.toContain(PROTECTED_ENTRY);
  expect(westResults.map((entry) => entry.name)).not.toContain(HIDDEN_ENTRY);

  await login(page, { username: "e2e-denied", password: PASSWORD });
  expect(await searchByRegion(page, REGION_CODE)).toEqual([]);

  await login(page, { username: "e2e-viewer", password: PASSWORD });
  await page.goto(
    `/ui/entities/${target.id}/entries/${protectedEntry.id}/details`,
  );
  await expect(
    page.getByRole("heading", { name: PROTECTED_ENTRY }),
  ).toBeVisible();
  await captureEvidence(page, testInfo, {
    name: "search-chain-two-hop-result",
    title: "Two-hop search-chain result",
    note: "A viewer traversed Asset -> Reference -> Region through the real search-chain API and Elasticsearch. East and west branches returned different assets, an unreadable asset on the same path stayed hidden, and the denied user received no results.",
  });
});
