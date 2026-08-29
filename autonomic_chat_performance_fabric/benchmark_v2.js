"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const {performance} = require("node:perf_hooks");
const {PerformanceSentinel} = require("./performance_sentinel.js");

const EVIDENCE_CLASS = "MATCHED_SYNTHETIC_LOCAL_NOT_REAL_BROWSER";
const DEFAULT_CASES = [
  {messageCount: 100, rounds: 20, seed: 0x100f},
  {messageCount: 500, rounds: 20, seed: 0x500f},
  {messageCount: 1000, rounds: 20, seed: 0x1000f}
];

function rng(seed) {
  let state = seed >>> 0;
  return () => {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return (state >>> 0) / 4294967296;
  };
}

function median(values) {
  if (!values.length) throw new Error("median requires values");
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
}

function percentile(values, probability) {
  if (!values.length) throw new Error("percentile requires values");
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(
    sorted.length - 1,
    Math.max(0, Math.ceil(probability * sorted.length) - 1)
  );
  return sorted[index];
}

function makeBalancedOrder(samples, seed) {
  if (!Number.isInteger(samples) || samples < 2 || samples % 2 !== 0) {
    throw new Error("samples must be an even integer of at least two");
  }
  const order = Array.from({length: samples}, (_, index) => index < samples / 2);
  const random = rng(seed);
  for (let index = order.length - 1; index > 0; index -= 1) {
    const selected = Math.floor(random() * (index + 1));
    [order[index], order[selected]] = [order[selected], order[index]];
  }
  return order;
}

function bootstrapRatio(baseline, candidate, iterations, seed) {
  if (baseline.length !== candidate.length || !baseline.length) {
    throw new Error("bootstrap inputs must be non-empty matched samples");
  }
  if (!Number.isInteger(iterations) || iterations < 1) {
    throw new Error("bootstrapIterations must be a positive integer");
  }
  const random = rng(seed);
  const ratios = [];
  for (let iteration = 0; iteration < iterations; iteration += 1) {
    const baselineSample = [];
    const candidateSample = [];
    for (let index = 0; index < baseline.length; index += 1) {
      const selected = Math.floor(random() * baseline.length);
      baselineSample.push(baseline[selected]);
      candidateSample.push(candidate[selected]);
    }
    ratios.push(median(baselineSample) / median(candidateSample));
  }
  return {
    lower95: percentile(ratios, 0.025),
    upper95: percentile(ratios, 0.975)
  };
}

function snapshots(messageCount, rounds) {
  if (!Number.isInteger(messageCount) || messageCount < 1 ||
      !Number.isInteger(rounds) || rounds < 1) {
    throw new Error("messageCount and rounds must be positive integers");
  }
  const current = Array.from({length: messageCount}, (_, index) => ({
    id: String(index + 1),
    text: ("synthetic-" + (index % 17) + "-").repeat(12)
  }));
  const result = [];
  for (let round = 0; round < rounds; round += 1) {
    if (round > 0) {
      const index = (round * 37) % messageCount;
      current[index] = {...current[index], text: current[index].text + "x"};
    }
    result.push(Object.freeze(current.map(item => Object.freeze({...item}))));
  }
  return Object.freeze(result);
}

function baselineRun(input) {
  const previous = new Map();
  let ledger = [];
  let changeCount = 0;
  let sink = 0;
  for (const snapshot of input) {
    for (const message of snapshot) {
      if (previous.get(message.id) !== message.text) {
        previous.set(message.id, message.text);
        changeCount += 1;
      }
    }
    ledger = ledger.concat(snapshot.map(item => ({...item})));
    sink ^= JSON.stringify(ledger).length;
  }
  return {changeCount, sink};
}

function candidateRun(input) {
  const sentinel = new PerformanceSentinel({
    minimumIntervalMs: 0,
    maximumCaptureMs: Number.MAX_SAFE_INTEGER,
    maximumPayloadChars: Number.MAX_SAFE_INTEGER,
    maximumQueueItems: input.length + 1
  });
  let changeCount = 0;
  let sink = 0;
  for (let round = 0; round < input.length; round += 1) {
    const result = sentinel.admit(input[round], round + 1);
    if (result.state === "CIRCUIT_OPEN") throw new Error("candidate circuit opened");
    changeCount += result.changeCount || 0;
    sink ^= result.payloadChars || 0;
  }
  sentinel.rollback();
  if (!sentinel.disabled || sentinel.queue.length || sentinel.lastHashes.size) {
    throw new Error("candidate rollback invariant failed");
  }
  return {changeCount, sink};
}

function timed(fn) {
  const started = performance.now();
  const result = fn();
  return {durationMs: performance.now() - started, result};
}

function runCase({
  messageCount,
  rounds,
  samples = 16,
  warmups = 3,
  bootstrapIterations = 1200,
  seed
}) {
  if (!Number.isInteger(warmups) || warmups < 0) {
    throw new Error("warmups must be a non-negative integer");
  }
  const input = snapshots(messageCount, rounds);
  const expectedChanges = messageCount + rounds - 1;
  for (let index = 0; index < warmups; index += 1) {
    baselineRun(input);
    candidateRun(input);
  }
  const order = makeBalancedOrder(samples, seed);
  const baselineMs = [];
  const candidateMs = [];
  let semanticEquivalent = true;
  for (const baselineFirst of order) {
    const first = baselineFirst ? baselineRun : candidateRun;
    const second = baselineFirst ? candidateRun : baselineRun;
    const firstResult = timed(() => first(input));
    const secondResult = timed(() => second(input));
    const baselineResult = baselineFirst ? firstResult : secondResult;
    const candidateResult = baselineFirst ? secondResult : firstResult;
    baselineMs.push(baselineResult.durationMs);
    candidateMs.push(candidateResult.durationMs);
    semanticEquivalent &&=
      baselineResult.result.changeCount === candidateResult.result.changeCount &&
      candidateResult.result.changeCount === expectedChanges;
  }
  const confidence = bootstrapRatio(
    baselineMs,
    candidateMs,
    bootstrapIterations,
    seed ^ 0xa5a5a5a5
  );
  return {
    messages: messageCount,
    rounds,
    samples,
    baselineFirstSamples: order.filter(Boolean).length,
    candidateFirstSamples: order.filter(value => !value).length,
    expectedChanges,
    semanticEquivalent,
    baselineMs: {p50: median(baselineMs), p95: percentile(baselineMs, 0.95)},
    candidateMs: {p50: median(candidateMs), p95: percentile(candidateMs, 0.95)},
    medianSpeedup: median(baselineMs) / median(candidateMs),
    medianSpeedupCI95: confidence,
    candidateFasterWithConfidence: confidence.lower95 > 1
  };
}

function round(value) {
  return Number(value.toFixed(3));
}

function roundCase(item) {
  return {
    ...item,
    baselineMs: {p50: round(item.baselineMs.p50), p95: round(item.baselineMs.p95)},
    candidateMs: {p50: round(item.candidateMs.p50), p95: round(item.candidateMs.p95)},
    medianSpeedup: round(item.medianSpeedup),
    medianSpeedupCI95: {
      lower95: round(item.medianSpeedupCI95.lower95),
      upper95: round(item.medianSpeedupCI95.upper95)
    }
  };
}

function createReceipt(options = {}) {
  const samples = options.samples ?? 16;
  const warmups = options.warmups ?? 3;
  const bootstrapIterations = options.bootstrapIterations ?? 1200;
  const cases = (options.cases || DEFAULT_CASES).map(item => roundCase(runCase({
    ...item,
    samples,
    warmups,
    bootstrapIterations
  })));
  const sentinelPath = require.resolve("./performance_sentinel.js");
  return {
    schema: "FACPF-CFBE-SYNTHETIC-STATISTICAL-2",
    evidenceClass: EVIDENCE_CLASS,
    sourceBinding: {
      sentinelSha256: crypto
        .createHash("sha256")
        .update(fs.readFileSync(sentinelPath))
        .digest("hex"),
      runtimeCommit: process.env.GITHUB_SHA || null
    },
    method: {
      warmupsPerPath: warmups,
      pairedSamplesPerCase: samples,
      randomizedBalancedOrder: true,
      bootstrapIterations,
      syntheticOnly: true
    },
    privacy: {
      transcriptRead: false,
      domRead: false,
      urlRead: false,
      contentFieldsEmitted: false,
      identifierFieldsEmitted: false
    },
    cases,
    semanticGatePassed: cases.every(item => item.semanticEquivalent),
    statisticalWin: cases.every(item => item.candidateFasterWithConfidence),
    liveChatClaimAllowed: false
  };
}

function main() {
  const receipt = createReceipt();
  if (!receipt.semanticGatePassed) process.exitCode = 2;
  console.log(JSON.stringify(receipt));
}

if (require.main === module) main();

module.exports = {
  EVIDENCE_CLASS,
  baselineRun,
  bootstrapRatio,
  candidateRun,
  createReceipt,
  makeBalancedOrder,
  median,
  percentile,
  rng,
  runCase,
  snapshots
};
