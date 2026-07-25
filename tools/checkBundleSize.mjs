import { gzipSync } from "node:zlib";
import { readFile } from "node:fs/promises";

const packageConfig = JSON.parse(
  await readFile(new URL("../package.json", import.meta.url), "utf8"),
);
const budget = packageConfig.qualityBudgets.frontendBundle;
const bundleUrl = new URL(`../${budget.path}`, import.meta.url);
const bundle = await readFile(bundleUrl);
const gzipBytes = gzipSync(bundle, { level: 9 }).byteLength;

const measurements = [
  ["raw", bundle.byteLength, budget.maxBytes],
  ["gzip", gzipBytes, budget.maxGzipBytes],
];
let failed = false;

for (const [kind, actual, maximum] of measurements) {
  const remaining = maximum - actual;
  const percent = ((actual / maximum) * 100).toFixed(1);
  console.log(
    `${kind}: ${actual.toLocaleString()} / ${maximum.toLocaleString()} bytes (${percent}% of budget)`,
  );
  if (remaining < 0) {
    failed = true;
    console.error(
      `${kind} bundle exceeds its budget by ${Math.abs(remaining).toLocaleString()} bytes`,
    );
  }
}

if (failed) {
  process.exitCode = 1;
}
