"use strict";
const assert = require("node:assert/strict");
const {NativeEdgeChatGPTDiagnostic, MAX_AGGREGATE_SAMPLES} = require("./native_edge_chatgpt_diagnostic.js");
const {assertInputRouteMode, deriveRouteHealth, selectPrimary} = require("./route_mode_contract.js");

class FakeObserver {
  static supportedEntryTypes = ["longtask"];
  constructor(callback) { this.callback = callback; this.disconnected = false; }
  observe() { this.callback({getEntries: () => [{duration: 60, name: "secret", attribution: [{containerSrc: "private"}]}]}); }
  disconnect() { this.disconnected = true; }
}
class FakeEvents {
  constructor() { this.listeners = new Map(); }
  addEventListener(type, listener) { this.listeners.set(type, listener); }
  removeEventListener(type, listener) { if (this.listeners.get(type) === listener) this.listeners.delete(type); }
  emit(type) { if (this.listeners.has(type)) this.listeners.get(type)(); }
}
const performanceApi = {getEntriesByType(type) {
  if (type === "navigation") return [{type: "reload", duration: 900, requestStart: 10, responseEnd: 90, domContentLoadedEventEnd: 700, loadEventEnd: 850, name: "private-url"}];
  if (type === "resource") return [{duration: 25, name: "private-resource"}];
  return [];
}};

const inactive = new NativeEdgeChatGPTDiagnostic({config: {enabled: false}});
assert.equal(inactive.start({formationPermitValidated: true, operatorActivationValidated: true}).state, "DISABLED_CONFIG");

const missingEvidence = new NativeEdgeChatGPTDiagnostic({config: {enabled: true, mode: "SHADOW_OBSERVE_ONLY"}});
assert.equal(missingEvidence.start({formationPermitValidated: true}).reason, "AUTHORIZED_EDGE_HOOK_REQUIRED");
assert.equal(missingEvidence.snapshot().state, "INACTIVE");

const events = new FakeEvents();
const diagnostic = new NativeEdgeChatGPTDiagnostic({
  config: {enabled: true, mode: "SHADOW_OBSERVE_ONLY", activation: {authorizedEdgeHookPresent: true}}, performanceApi, ObserverClass: FakeObserver, eventTarget: events
});
assert.equal(diagnostic.start({formationPermitValidated: true}).reason, "EVIDENCE_INCOMPLETE");
assert.equal(diagnostic.start({formationPermitValidated: true, operatorActivationValidated: true}).state, "OBSERVING");
assert.equal(diagnostic.recordHydration("INVALID", 1).state, "REJECTED_ENUM");
assert.equal(diagnostic.recordHydration("READY", 1).state, "REJECTED_SEQUENCE");
assert.equal(diagnostic.recordHydration("START", 100).state, "RECORDED");
assert.equal(diagnostic.recordHydration("READY", 350).state, "RECORDED");
assert.equal(diagnostic.recordTransportState("DEGRADED").state, "REJECTED_ENUM");
assert.equal(diagnostic.recordTransportState("RECONNECTING").state, "RECORDED");
assert.equal(diagnostic.recordTransportState("CONNECTED").state, "RECORDED");
assert.equal(diagnostic.recordMemorySample(90, 100).state, "RECORDED");
assert.equal(diagnostic.recordMemorySample(120, 100).state, "REJECTED_RANGE");
events.emit("pageshow"); events.emit("offline"); events.emit("online"); events.emit("visibilitychange");
const snapshot = diagnostic.snapshot();
assert.equal(snapshot.navigation.reloadCount, 1);
assert.equal(snapshot.hydrationMs.p95, 250);
assert.equal(snapshot.transport.reconnecting, 1);
assert.equal(snapshot.lifecycle.pageShow, 1);
assert.equal(snapshot.memoryPressure.threshold80PercentCount, 1);
assert.equal(snapshot.longTasks.count, 1);
assert.equal(snapshot.runtimeBoundary, "AUTHORIZED_EDGE_HOOK_REQUIRED");
const serialized = JSON.stringify(snapshot);
for (const forbidden of ["private-url", "private-resource", "secret", "containerSrc", "usedBytes", "limitBytes"]) {
  assert.equal(serialized.includes(forbidden), false);
}
for (let index = 0; index <= MAX_AGGREGATE_SAMPLES; index += 1) diagnostic.recordMemorySample(1, 2);
assert.equal(diagnostic.snapshot().memoryPressure.sampleCount, MAX_AGGREGATE_SAMPLES);
assert.ok(diagnostic.snapshot().droppedSamples > 0);
diagnostic.rollback();
assert.equal(events.listeners.size, 0);
assert.equal(diagnostic.snapshot().state, "INACTIVE");
assert.equal(diagnostic.snapshot().hydrationMs.sampleCount, 0);
assert.equal(diagnostic.snapshot().memoryPressure.sampleCount, 0);

assert.equal(assertInputRouteMode("ACTIVE"), "ACTIVE");
assert.throws(() => assertInputRouteMode("DEGRADED"), /ACTIVE or PASSIVE/);
assert.equal(deriveRouteHealth({errorCount: 0, saturation: 0.2, latencyMs: 500}), "HEALTHY");
assert.equal(deriveRouteHealth({errorCount: 1, saturation: 0.2, latencyMs: 500}), "DEGRADED");
assert.equal(deriveRouteHealth({errorCount: 3, saturation: 0.2, latencyMs: 500}), "OPEN");
assert.deepEqual(selectPrimary([
  {key: "primary", mode: "ACTIVE", metrics: {errorCount: 1}},
  {key: "secondary", mode: "PASSIVE", metrics: {errorCount: 0}}
]), {state: "ROUTE_SELECTED", key: "secondary", selectedMode: "PASSIVE", selectedHealth: "HEALTHY"});
assert.deepEqual(selectPrimary([
  {key: "first", mode: "PASSIVE", metrics: {}},
  {key: "active", mode: "ACTIVE", metrics: {}}
]), {state: "ROUTE_SELECTED", key: "active", selectedMode: "ACTIVE", selectedHealth: "HEALTHY"});
assert.throws(() => selectPrimary([{mode: "HEALTHY", metrics: {}}]), /ACTIVE or PASSIVE/);

console.log("native edge diagnostic tests passed");
