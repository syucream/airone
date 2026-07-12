import fs from "node:fs";
import path from "node:path";

import type { Page, TestInfo } from "@playwright/test";

const reportDir = path.join(__dirname, "test-results", "report");
const screenshotDir = path.join(reportDir, "screenshots");

export const captureEvidence = async (
  page: Page,
  testInfo: TestInfo,
  {
    name,
    title,
    note,
  }: {
    name: string;
    title: string;
    note: string;
  },
) => {
  fs.mkdirSync(screenshotDir, { recursive: true });
  const screenshotPath = path.join(screenshotDir, `${name}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await testInfo.attach(title, {
    path: screenshotPath,
    contentType: "image/png",
  });
  await testInfo.attach(`${title} metadata`, {
    body: JSON.stringify({ name, note }, null, 2),
    contentType: "application/json",
  });
};
