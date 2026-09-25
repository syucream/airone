import { expect, test } from "@playwright/test";

import { captureEvidence } from "./liveEvidence";

import { fixture, PASSWORD, PROTECTED_ENTRY } from "./liveServiceFixture";
import { apiGet, apiStatus, login } from "./liveApi";

const users = [
  {
    username: "admin",
    password: "admin",
    list: 200,
    detail: 200,
    edit: true,
    acl: true,
  },
  {
    username: "e2e-editor",
    password: PASSWORD,
    list: 200,
    detail: 200,
    edit: true,
    acl: false,
  },
  {
    username: "e2e-viewer",
    password: PASSWORD,
    list: 200,
    detail: 200,
    edit: false,
    acl: false,
  },
  {
    username: "e2e-denied",
    password: PASSWORD,
    list: 403,
    detail: 403,
    edit: false,
    acl: false,
  },
] as const;

test("admin, editor, viewer, and denied users keep the ACL boundary", async ({
  page,
}, testInfo) => {
  await login(page);
  const { target, protectedEntry } = await fixture(page);

  for (const expected of users) {
    await login(page, expected);
    expect(await apiStatus(page, `/entity/api/v2/${target.id}/entries/`)).toBe(
      expected.list,
    );
    expect(await apiStatus(page, `/entry/api/v2/${protectedEntry.id}/`)).toBe(
      expected.detail,
    );

    const search = await apiGet<{ id: number }[]>(
      page,
      `/entry/api/v2/search/?query=${encodeURIComponent(PROTECTED_ENTRY)}`,
    );
    expect(search.some((item) => item.id === protectedEntry.id)).toBe(
      expected.detail === 200,
    );

    const editStatus = await apiStatus(
      page,
      `/entry/api/v2/${protectedEntry.id}/`,
      { method: "PUT", body: {} },
    );
    expect(editStatus).toBe(expected.edit ? 202 : 403);

    const aclUrl = `/acl/api/v2/acls/${protectedEntry.id}`;
    if (expected.acl) {
      const current = await apiGet<{
        is_public: boolean;
        default_permission: number;
        roles: { id: number; current_permission: number }[];
      }>(page, aclUrl);
      expect(
        await apiStatus(page, aclUrl, {
          method: "PUT",
          body: {
            is_public: current.is_public,
            default_permission: current.default_permission,
            acl_settings: current.roles
              .filter((role) => role.current_permission > 1)
              .map((role) => ({
                member_id: role.id,
                value: role.current_permission,
              })),
          },
        }),
      ).toBe(200);
    } else {
      expect(await apiStatus(page, aclUrl, { method: "PUT", body: {} })).toBe(
        403,
      );
    }

    if (expected.detail === 200) {
      await page.goto(
        `/ui/entities/${target.id}/entries/${protectedEntry.id}/details`,
      );
      await expect(
        page.getByRole("heading", { name: PROTECTED_ENTRY }),
      ).toBeVisible();
      await page.locator("#entryMenu").click();
      await expect(page.getByText("編集", { exact: true })).toHaveCount(
        expected.edit ? 1 : 0,
      );
      await expect(page.getByText("ACL 設定", { exact: true })).toHaveCount(
        expected.acl ? 1 : 0,
      );
    } else {
      await page.goto(`/ui/entities/${target.id}/entries`);
      await expect(
        page.getByRole("heading", { name: /権限がありません/ }),
      ).toBeVisible();
    }
  }

  await captureEvidence(page, testInfo, {
    name: "acl-role-matrix",
    title: "ACL role matrix",
    note: "List, detail, simple search, update, ACL update, and visible controls were checked for full, writable, readable, and no-access users.",
  });
});
