"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const {
  EVIDENCE_CLASS,
  baselineRun,
  bootstrapRatio,
  candidateRun,
  createReceipt,
  makeBalancedOrder,
  runCase,
  snapshots
} = require("./benchmark_v2.js");

const input = snapshots(8, 4);
assert.equal(Object.isFrozen(input), true);
assert.equal(input.every(snapshot => Object.isFrozen(snapshot)), true);
assert.equal(input.every(snapshot => snapshot.every(Object.isFrozen)), true);
assert.equal(baselineRun(input).changeCount, 11);
assert.equal(candidateRun(input).changeCount, 11);

const order = makeBalancedOrder(8, 0xabc);
assert.deepEqual(order, makeBalancedOrder(8, 0xabc));
assert.equal(order.filter(Boolean).length, 4);
assert.equal(order.filter(value => !value).length, 4);
assert.throws(() => makeBalancedOrder(3, 1), /even integer/);

const confidence = bootstrapRatio([4, 5, 6, 7], [1, 1.1, 1.2, 1.3], 100, 9);
assert.ok(confidence.lower95 > 1);
assert.ok(confidence.upper95 >= confidence.lower95);
assert.throws(
  () => bootstrapRatio([1], [1], 0, 9),
  /bootstrapIterations/
);

const smallCase = runCase({
  messageCount: 8,
  rounds: 4,
  samples: 2,
  warmups: 0,
  bootstrapIterations: 20,
  seed: 7
});
assert.equal(smallCase.semanticEquivalent, true);
assert.equal(smallCase.expectedChanges, 11);
assert.equal(smallCase.baselineFirstSamples, 1);
assert.equal(smallCase.candidateFirstSamples, 1);
assert.throws(
  () => runCase({
    messageCount: 8,
    rounds: 4,
    samples: 2,
    warmups: -1,
    bootstrapIterations: 20,
    seed: 7
  }),
  /warmups/
);

const receipt = createReceipt({
  cases: [{messageCount: 8, rounds: 4, seed: 7}],
  samples: 2,
  warmups: 0,
  bootstrapIterations: 20
});
assert.equal(receipt.schema, "FACPF-CFBE-SYNTHETIC-STATISTICAL-2");
assert.equal(receipt.evidenceClass, EVIDENCE_CLASS);
assert.equal(receipt.semanticGatePassed, true);
assert.equal(receipt.liveChatClaimAllowed, false);
assert.deepEqual(receipt.privacy, {
  transcriptRead: false,
  domRead: false,
  urlRead: false,
  contentFieldsEmitted: false,
  identifierFieldsEmitted: false
});
const sentinelPath = require.resolve("./performance_sentinel.js");
const expectedHash = crypto
  .createHash("sha256")
  .update(fs.readFileSync(sentinelPath))
  .digest("hex");
assert.equal(receipt.sourceBinding.sentinelSha256, expectedHash);
const serialized = JSON.stringify(receipt);
assert.equal(serialized.includes("synthetic-"), false);
assert.equal(serialized.includes("private-message-body"), false);
console.log("statistical benchmark tests passed");
