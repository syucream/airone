import fs from "node:fs";
import path from "node:path";

import type {
  FullResult,
  Reporter,
  TestCase,
  TestResult,
} from "@playwright/test/reporter";

const reportDir = path.join(__dirname, "test-results", "report");
const evidenceDir = path.join(reportDir, "evidence");

type TestRow = {
  status: "PASS" | "FAIL";
  title: string;
  duration: number;
};

type Evidence = {
  name: string;
  title: string;
  note: string;
  testTitle: string;
  screenshot: string;
};

/**
 * Writes `e2e/test-results/report/report.md`, the human-readable, screenshot
 * backed summary a developer attaches to a change. Test results come from the
 * reporter itself; screenshots are contributed by `captureEvidence` in
 * `reportEvidence.ts`.
 */
class E2eReportReporter implements Reporter {
  private rows: TestRow[] = [];

  onBegin() {
    fs.rmSync(reportDir, { recursive: true, force: true });
  }

  onTestEnd(test: TestCase, result: TestResult) {
    this.rows.push({
      status: result.status === test.expectedStatus ? "PASS" : "FAIL",
      title: test.titlePath().slice(1).join(" › ") || test.title,
      duration: result.duration,
    });
  }

  onEnd(result: FullResult) {
    fs.mkdirSync(reportDir, { recursive: true });
    const evidence = this.readEvidence();
    const lines = [
      "# Pagoda E2E Report",
      "",
      `Generated: ${new Date().toISOString()}`,
      `Overall result: ${result.status}`,
      "",
      "## Test Results",
      "",
      "| Result | Test case | Duration |",
      "| --- | --- | ---: |",
      ...this.rows.map(
        (row) =>
          `| ${row.status} | ${row.title.replaceAll("|", "\\|")} | ${row.duration} ms |`,
      ),
      "",
      "## Evidence",
      "",
    ];

    for (const item of evidence) {
      lines.push(`### ${item.title}`);
      lines.push("");
      if (item.note) {
        lines.push(item.note);
        lines.push("");
      }
      lines.push(`![${item.title}](${item.screenshot})`);
      lines.push("");
    }

    fs.writeFileSync(path.join(reportDir, "report.md"), lines.join("\n"));
  }

  private readEvidence(): Evidence[] {
    if (!fs.existsSync(evidenceDir)) return [];
    return fs
      .readdirSync(evidenceDir)
      .filter((file) => file.endsWith(".json"))
      .sort()
      .map((file) =>
        JSON.parse(fs.readFileSync(path.join(evidenceDir, file), "utf8")),
      );
  }
}

export default E2eReportReporter;
