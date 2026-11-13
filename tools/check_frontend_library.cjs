const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

// Consumers copy this UMD file without a webpack chunk loader deployment.
// Run after build:lib, which clears the output directory before compiling.
const directory = path.resolve(__dirname, "../frontend/dist");
assert.deepEqual(
  fs
    .readdirSync(directory, { recursive: true })
    .filter((file) => file.endsWith(".js")),
  ["pagoda-core.js"],
  "The library must remain a single JavaScript file",
);
console.log("Library single-file contract passed");
