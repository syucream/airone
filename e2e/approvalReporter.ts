import fs from "node:fs";
import path from "node:path";

import type {
  FullConfig,
  FullResult,
  Reporter,
  TestCase,
  TestResult,
} from "@playwright/test/reporter";

type ApprovalTest = {
  artifacts: Array<{ contentType: string; name: string; path: string }>;
  durationMs: number;
  error?: string;
  file: string;
  status: TestResult["status"];
  title: string;
};

type ApprovalManifest = {
  artifacts: {
    htmlReport: string;
    jsonReport: string;
    markdownReport: string;
  };
  checks: {
    browserMock: "passed" | "failed";
  };
  commit: string | null;
  coverage: {
    attributeTypes: number;
    scenarios: number;
    tags: Record<string, number>;
  };
  decision: "approve" | "reject";
  durationMs: number;
  generatedAt: string;
  tests: ApprovalTest[];
  waivers: string[];
};

class ApprovalReporter implements Reporter {
  private readonly tests: ApprovalTest[] = [];
  private outputDir = "";
  private startedAt = 0;

  onBegin(config: FullConfig): void {
    this.startedAt = Date.now();
    this.outputDir = path.resolve(config.rootDir, "test-results", "approval");
    fs.mkdirSync(this.outputDir, { recursive: true });
    for (const file of ["approval-manifest.json", "report.md"]) {
      fs.rmSync(path.join(this.outputDir, file), { force: true });
    }
  }

  onTestEnd(test: TestCase, result: TestResult): void {
    this.tests.push({
      artifacts: result.attachments
        .filter((attachment) => attachment.path != null)
        .map((attachment) => ({
          contentType: attachment.contentType,
          name: attachment.name,
          path: path.relative(process.cwd(), attachment.path!),
        })),
      durationMs: result.duration,
      error: result.error?.message,
      file: path.relative(process.cwd(), test.location.file),
      status: result.status,
      title: test.title,
    });
  }

  onEnd(result: FullResult): void {
    const passed = result.status === "passed";
    const tags: Record<string, number> = {};
    for (const test of this.tests) {
      for (const tag of test.title.match(/@[\w-]+/g) ?? []) {
        tags[tag] = (tags[tag] ?? 0) + 1;
      }
    }

    const manifest: ApprovalManifest = {
      artifacts: {
        htmlReport: "../html/index.html",
        jsonReport: "../results.json",
        markdownReport: "report.md",
      },
      checks: { browserMock: passed ? "passed" : "failed" },
      commit: process.env.GITHUB_SHA ?? process.env.E2E_COMMIT ?? null,
      coverage: {
        attributeTypes: 18,
        scenarios: this.tests.length,
        tags,
      },
      decision: passed ? "approve" : "reject",
      durationMs: Date.now() - this.startedAt,
      generatedAt: new Date().toISOString(),
      tests: this.tests,
      waivers: [],
    };
    fs.writeFileSync(
      path.join(this.outputDir, "approval-manifest.json"),
      `${JSON.stringify(manifest, null, 2)}\n`,
    );
    fs.writeFileSync(path.join(this.outputDir, "report.md"), this.toMarkdown(manifest));
  }

  private toMarkdown(manifest: ApprovalManifest): string {
    const lines = [
      "# Pagoda Browser Approval Report",
      "",
      `- Decision: **${manifest.decision.toUpperCase()}**`,
      `- Scenarios: ${manifest.coverage.scenarios}`,
      `- Duration: ${manifest.durationMs} ms`,
      `- Generated: ${manifest.generatedAt}`,
      "",
      "## Results",
      "",
      "| Status | Scenario | Duration | Artifacts |",
      "| --- | --- | ---: | ---: |",
    ];
    for (const test of manifest.tests) {
      lines.push(
        `| ${test.status} | ${test.title.replaceAll("|", "\\|")} | ${test.durationMs} ms | ${test.artifacts.length} |`,
      );
      if (test.error != null) lines.push(`\n> ${test.error.replaceAll("\n", " ")}\n`);
    }
    lines.push("", "## Coverage tags", "");
    for (const [tag, count] of Object.entries(manifest.coverage.tags).sort()) {
      lines.push(`- ${tag}: ${count}`);
    }
    lines.push("");
    return lines.join("\n");
  }
}

export default ApprovalReporter;
