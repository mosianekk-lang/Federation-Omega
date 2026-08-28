"use strict";
const {performance} = require("perf_hooks");
const {PerformanceSentinel} = require("./performance_sentinel.js");

function messages(count, changed) {
  return Array.from({length: count}, (_, index) => ({
    id: String(index),
    role: index % 2 ? "assistant" : "user",
    text: ("message-" + index + "-").repeat(20) + (changed === index ? "delta" : "")
  }));
}

function baseline(workload, rounds) {
  let ledger = [];
  const started = performance.now();
  for (let round = 0; round < rounds; round += 1) {
    const packet = workload.map(item => ({...item}));
    ledger = ledger.concat(packet);
    JSON.stringify(ledger);
  }
  return performance.now() - started;
}

function candidate(workload, rounds) {
  const sentinel = new PerformanceSentinel({
    minimumIntervalMs: 0,
    maximumCaptureMs: 100000,
    maximumPayloadChars: 10000000,
    maximumQueueItems: 100000
  });
  const started = performance.now();
  for (let round = 0; round < rounds; round += 1) sentinel.admit(workload, round + 1);
  return performance.now() - started;
}

const cases = [100, 250, 500, 750, 1000].map(count => {
  const workload = messages(count, count - 1);
  const baselineMs = baseline(workload, 20);
  const candidateMs = candidate(workload, 20);
  return {
    messages: count,
    rounds: 20,
    baselineMs: Number(baselineMs.toFixed(3)),
    candidateMs: Number(candidateMs.toFixed(3)),
    factor: Number((baselineMs / candidateMs).toFixed(2))
  };
});
const result = {
  schema: "FACPF-CFBE-SYNTHETIC-1",
  evidenceClass: "SYNTHETIC_LOCAL_NOT_REAL_BROWSER",
  cases,
  allCandidateFaster: cases.every(item => item.factor > 1)
};
console.log(JSON.stringify(result, null, 2));
