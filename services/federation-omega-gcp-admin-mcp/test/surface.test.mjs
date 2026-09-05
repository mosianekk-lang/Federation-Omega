import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import {TOOL_NAMES, SERVER_VERSION, healthPayload} from "../dist/toolNames.js";

const baseline = JSON.parse(fs.readFileSync(new URL("../BASELINE_CAPABILITIES.json", import.meta.url), "utf8"));
const source = ["config.ts", "operations.ts", "server.ts"]
  .map(name => fs.readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8"))
  .join("\n");

test("preserves every baseline tool and adds lineage tools", () => {
  const tools = Object.values(TOOL_NAMES);
  for (const name of baseline.requiredTools) assert.ok(tools.includes(name), `missing baseline tool ${name}`);
  assert.equal(new Set(tools).size, 17);
  assert.ok(tools.includes("gcp_deployment_lineage_attest"));
});

test("preserves every baseline control", () => {
  for (const control of baseline.requiredControls) assert.match(source, new RegExp(control));
});

test("health explicitly proves transport only", () => {
  assert.equal(SERVER_VERSION, "0.2.2");
  assert.equal(healthPayload(new Date("2026-08-16T00:00:00Z")).proofBoundary, "transport_liveness_only");
});
