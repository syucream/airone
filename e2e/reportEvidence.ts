import fs from "node:fs";
import path from "node:path";

import type { Page, TestInfo } from "@playwright/test";

type Evidence = {
  name: string;
  title: string;
  note: string;
  screenshotPath: string;
};

type TestResult = {
  duration: number;
  expectedStatus: TestInfo["expectedStatus"];
  status: TestInfo["status"];
  title: string;
};

const reportDir = path.join(__dirname, "test-results", "report");
const screenshotDir = path.join(reportDir, "screenshots");
const evidenceDir = path.join(reportDir, "evidence");
const evidence: Evidence[] = [];
const testResults: TestResult[] = [];

export const resetE2eReport = () => {
  fs.rmSync(reportDir, { recursive: true, force: true });
  evidence.length = 0;
  testResults.length = 0;
};

export const recordTestResult = (testInfo: TestInfo) => {
  testResults.push({
    duration: testInfo.duration,
    expectedStatus: testInfo.expectedStatus,
    status: testInfo.status,
    title: testInfo.title,
  });
};

/**
 * Capture a full-page screenshot for the run report.
 *
 * The mock-server suite aggregates every screenshot and result through
 * `reportReporter.ts`, which reads the JSON descriptor written here. The live
 * suite, which has no reporter, still collects into the in-memory arrays and
 * writes `report.md` with `writeE2eReport`.
 */
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
  fs.mkdirSync(evidenceDir, { recursive: true });
  const screenshotPath = path.join(screenshotDir, `${name}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await testInfo.attach(title, {
    path: screenshotPath,
    contentType: "image/png",
  });
  evidence.push({
    name,
    title,
    note,
    screenshotPath: path.relative(reportDir, screenshotPath),
  });
  fs.writeFileSync(
    path.join(evidenceDir, `${name}.json`),
    JSON.stringify({
      name,
      title,
      note,
      testTitle: testInfo.title,
      screenshot: path.relative(reportDir, screenshotPath),
    }),
  );
};

const defaultSummary = [
  "The real frontend bundle booted in Chromium headless mode.",
  "Dashboard, model list, entry list, and entry detail routes were exercised.",
  "Object, array-object, named-object, and array-named-object values were verified as entry links.",
  "Browser console errors, page errors, failed requests, critical axe violations, horizontal overflow, and off-screen interactive controls were checked.",
];

export const writeE2eReport = ({
  title = "Pagoda E2E Report",
  summary = defaultSummary,
}: {
  title?: string;
  summary?: string[];
} = {}) => {
  fs.mkdirSync(reportDir, { recursive: true });
  const lines = [
    `# ${title}`,
    "",
    `Generated: ${new Date().toISOString()}`,
    "",
    "## Summary",
    "",
    ...summary.map((line) => `- ${line}`),
    "",
    "## Test Results",
    "",
    "| Result | Test case | Duration |",
    "| --- | --- | ---: |",
    ...testResults.map((result) => {
      const status = result.status === result.expectedStatus ? "PASS" : "FAIL";
      const testTitle = result.title.replaceAll("|", "\\|");
      return `| ${status} | ${testTitle} | ${result.duration} ms |`;
    }),
    "",
    "## Evidence",
    "",
  ];

  for (const item of evidence) {
    lines.push(`### ${item.title}`);
    lines.push("");
    lines.push(item.note);
    lines.push("");
    lines.push(`![${item.title}](${item.screenshotPath})`);
    lines.push("");
  }

  fs.writeFileSync(path.join(reportDir, "report.md"), lines.join("\n"));
};
