"use strict";
const assert = require("assert");
const {PerformanceSentinel} = require("./performance_sentinel.js");

const sentinel = new PerformanceSentinel({minimumIntervalMs: 0, maximumCaptureMs: 1000});
let result = sentinel.admit([{id: "1", role: "user", text: "hello"}], 1);
assert.equal(result.state, "DELTA_READY");
assert.equal(result.deltas.length, 1);
result = sentinel.admit([{id: "1", role: "user", text: "hello"}], 2);
assert.equal(result.state, "NO_CHANGE");
sentinel.setStreaming(true);
assert.equal(sentinel.admit([{id: "2", text: "stream"}], 3).state, "DEFERRED");
sentinel.setStreaming(false);
const bounded = new PerformanceSentinel({minimumIntervalMs: 0, maximumPayloadChars: 2});
assert.equal(bounded.admit([{id: "x", text: "large"}], 1).state, "CIRCUIT_OPEN");
console.log("sentinel tests passed");
