"use strict";
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const {PerformanceSentinel} = require("./performance_sentinel.js");
const {AggregateBrowserProbe, MAX_LONG_TASK_SAMPLES} = require("./aggregate_browser_probe.js");

const sentinel = new PerformanceSentinel({minimumIntervalMs: 0, maximumCaptureMs: 1000});
let result = sentinel.admit([{id: "1", role: "user", text: "hello"}], 1);
assert.equal(result.state, "DELTA_READY");
assert.equal(result.deltas.length, 0);
assert.equal(result.changeCount, 1);
assert.equal(JSON.stringify(result).includes("hello"), false);
assert.deepEqual(Object.keys(sentinel.drain()[0]).sort(), ["changeCount", "elapsedMs", "observedAt", "payloadChars"]);
result = sentinel.admit([{id: "1", role: "user", text: "hello"}], 2);
assert.equal(result.state, "NO_CHANGE");
sentinel.setStreaming(true);
assert.equal(sentinel.admit([{id: "2", text: "stream"}], 3).state, "DEFERRED");
sentinel.setStreaming(false);
const bounded = new PerformanceSentinel({minimumIntervalMs: 0, maximumPayloadChars: 2});
assert.equal(bounded.admit([{id: "x", text: "large"}], 1).state, "CIRCUIT_OPEN");
bounded.options.maximumPayloadChars = 100;
bounded.resetCircuit();
assert.equal(bounded.admit([{id: "x", text: "large"}], 2).changeCount, 1);

const privateSentinel = new PerformanceSentinel({minimumIntervalMs: 0});
const privateResult = privateSentinel.admit([{id: "private-id", role: "user", text: "private-message-body"}], 1);
const serializedTelemetry = JSON.stringify([privateResult, privateSentinel.drain()]);
for (const forbidden of ["private-id", "private-message-body", "user"]) {
  assert.equal(serializedTelemetry.includes(forbidden), false);
}
privateSentinel.admit([{id: "second", text: "secret"}], 2);
privateSentinel.rollback();
assert.equal(privateSentinel.queue.length, 0);
assert.equal(privateSentinel.lastHashes.size, 0);
assert.equal(privateSentinel.admit([{id: "third", text: "ignored"}], 3).state, "DISABLED");

class FakeObserver {
  static supportedEntryTypes = ["longtask"];
  constructor(callback) { this.callback = callback; this.disconnected = false; }
  observe(options) {
    assert.deepEqual(options, {type: "longtask", buffered: true});
    this.callback({getEntries: () => [
      {duration: 55, name: "private-name", attribution: [{containerSrc: "https://private.example/chat"}]},
      {duration: 120, name: "self"}
    ]});
  }
  disconnect() { this.disconnected = true; }
}
const fakePerformance = {
  getEntriesByType(type) {
    if (type === "navigation") return [{duration: 800, requestStart: 20, responseEnd: 100, domContentLoadedEventEnd: 600, loadEventEnd: 750, name: "https://private.example/chat"}];
    if (type === "resource") return [{duration: 10, name: "https://private.example/a"}, {duration: 30, name: "https://private.example/b"}];
    return [];
  }
};
const probe = new AggregateBrowserProbe(fakePerformance, FakeObserver);
assert.equal(probe.start().state, "OBSERVING");
const aggregate = probe.snapshot();
assert.equal(aggregate.longTasks.count, 2);
assert.equal(aggregate.longTasks.p95DurationMs, 120);
assert.equal(aggregate.resources.count, 2);
const serializedAggregate = JSON.stringify(aggregate);
for (const forbidden of ["private.example", "private-name", "containerSrc", "attribution\":"]) {
  assert.equal(serializedAggregate.includes(forbidden), false);
}
probe.rollback();
assert.equal(probe.snapshot().longTasks.count, 0);
assert.equal(MAX_LONG_TASK_SAMPLES, 256);

class UnsupportedObserver {}
UnsupportedObserver.supportedEntryTypes = [];
assert.equal(new AggregateBrowserProbe(fakePerformance, UnsupportedObserver).start().state, "UNSUPPORTED");
const canary = JSON.parse(fs.readFileSync(path.join(__dirname, "browser_canary_config.json"), "utf8"));
assert.equal(canary.enabled, false);
assert.equal(canary.mode, "SHADOW_OBSERVE_ONLY");
assert.equal(canary.privacy.captureMessageText, false);
assert.equal(canary.implementationContracts.messageTextReturned, false);
assert.equal(canary.implementationContracts.perMessageIdentifiersReturned, false);
assert.equal(canary.implementationContracts.rawPerformanceEntryNamesReturned, false);
assert.equal(canary.implementationContracts.rollbackClearsMemory, true);
assert.equal(canary.implementationContracts.maximumAggregateSamples, 256);
assert.equal(canary.promotionGates.formationPermitRequired, true);
assert.ok(canary.promotionGates.minimumP95ImprovementPercent > 0);
assert.ok(canary.scope.maximumChats <= 1);
console.log("sentinel tests passed");
