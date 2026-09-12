import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import {TOOL_NAMES} from "../dist/toolNames.js";

const spec = JSON.parse(fs.readFileSync(new URL("../ALPHA_OMEGA_EXECUTION_SPEC.json", import.meta.url)));

test("Alpha-Omega stream graph is acyclic with one effectful lane", () => {
  const byId = new Map(spec.streams.map(stream => [stream.id, stream]));
  const visiting = new Set();
  const visited = new Set();
  const walk = id => {
    assert.ok(byId.has(id), `unknown stream ${id}`);
    if (visited.has(id)) return;
    assert.ok(!visiting.has(id), `cycle at ${id}`);
    visiting.add(id);
    for (const dependency of byId.get(id).dependsOn) walk(dependency);
    visiting.delete(id);
    visited.add(id);
  };
  for (const id of byId.keys()) walk(id);
  assert.equal(spec.streams.filter(stream => stream.mode === "SERIALIZED_EFFECTFUL").length, 1);
  assert.equal(spec.singleEffectfulPath, "S5-RELEASE");
});

test("Alpha-Omega freezes the complete 17-tool capability surface", () => {
  assert.deepEqual([...spec.capabilitySurface].sort(), Object.values(TOOL_NAMES).sort());
  assert.equal(spec.capabilitySurface.length, 17);
});

test("Alpha-Omega keeps autonomy and provider truth bounded", () => {
  assert.equal(spec.operatingLevel, "ON_DEMAND_GOVERNED");
  assert.equal(spec.durableAutonomyProven, false);
  assert.equal(spec.truthBoundary.sourceAndLocalTestsProveLiveCloud, false);
  assert.equal(spec.truthBoundary.authenticatedRequestProvesPrivateIam, false);
  assert.ok(spec.promotionGates.includes("UNAUTHENTICATED_401_OR_403"));
  assert.ok(spec.promotionGates.includes("EXACT_ROLLBACK_OR_ABSENCE_READBACK"));
});
