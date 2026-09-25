import type { Page, TestInfo } from "@playwright/test";

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
  const screenshotPath = testInfo.outputPath(`${name}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await testInfo.attach(title, {
    path: screenshotPath,
    contentType: "image/png",
  });
  await testInfo.attach(`${title} notes`, {
    body: note,
    contentType: "text/plain",
  });
};
