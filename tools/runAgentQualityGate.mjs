#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { closeSync, mkdirSync, openSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const output = path.join(root, "e2e", "test-results", "approval");
mkdirSync(output, { recursive: true });

const runCheck = (name, command) => {
  const started = Date.now();
  const log = path.join(output, `${name}.log`);
  const descriptor = openSync(log, "w");
  const result = spawnSync(command[0], command.slice(1), {
    cwd: root,
    env: process.env,
    stdio: ["ignore", descriptor, descriptor],
  });
  closeSync(descriptor);
  return {
    command,
    durationMs: Date.now() - started,
    log: path.relative(root, log),
    status: result.status === 0 ? "passed" : "failed",
  };
};

const checks = [runCheck("browser-mock", ["npm", "run", "e2e:mock:full"])];
if (checks.at(-1).status === "passed") {
  checks.push(runCheck("live-stack", ["npm", "run", "e2e:live"]));
}

const passed = checks.length === 2 && checks.every(({ status }) => status === "passed");
const manifest = {
  decision: passed ? "approve" : "reject",
  generatedAt: new Date().toISOString(),
  checks,
  coverage: {
    attributeTypes: 18,
    browser: "mocked deterministic UI and API",
    liveStack: ["Django", "MySQL", "Elasticsearch"],
    riskAreas: [
      "create-retrieve-update",
      "readonly permissions",
      "delete constraints",
      "advanced search filter",
      "advanced search join",
      "advanced search sort",
      "advanced search paging",
      "advanced search permissions",
    ],
  },
  waivers: [],
};
const manifestPath = path.join(output, "gate-manifest.json");
writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`${manifest.decision.toUpperCase()}: ${path.relative(root, manifestPath)}`);
for (const check of checks) {
  console.log(`- ${check.status}: ${check.log} (${check.durationMs} ms)`);
}
process.exitCode = passed ? 0 : 1;
