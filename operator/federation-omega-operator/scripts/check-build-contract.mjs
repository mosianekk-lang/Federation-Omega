import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const contract = JSON.parse(
  await readFile(new URL("../BUILD_CONTRACT.json", import.meta.url), "utf8"),
);
assert.equal(contract.contract_version, "3.3");
for (const key of [
  "mission", "classification", "assumptions", "architecture", "testing",
  "delivery", "formation", "watchman", "continuity", "states", "proof",
]) assert.ok(contract[key], "missing BUILD_CONTRACT key: " + key);
assert.equal(contract.formation.gate_decision, "EXECUTE");
assert.equal(contract.formation.single_effectful_path, true);
assert.equal(contract.states.tested, true);
assert.equal(contract.states.deployed, false);
assert.equal(contract.states.proven, false);
assert.ok(contract.proof.test_results.length > 0);
assert.ok(contract.proof.unresolved_defects.length > 0);
console.log("BUILD_CONTRACT_LOCAL_CHECK_PASSED");
