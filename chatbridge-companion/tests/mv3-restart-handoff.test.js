"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const crypto = require("node:crypto");

const root = path.resolve(__dirname, "..");
const backgroundSource = fs.readFileSync(path.join(root, "src", "background.js"), "utf8");
const manifest = JSON.parse(fs.readFileSync(path.join(root, "manifest.json"), "utf8"));

function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

function createSharedState() {
  return {
    local: Object.create(null),
    session: Object.create(null),
    tabs: new Map(),
    nextTabId: 100,
    createCount: 0,
    updateCount: 0,
    failAfterUpdateOnce: false,
    alarms: new Map()
  };
}

function storageArea(bucket) {
  return {
    async get(keys) {
      if (keys == null) return clone(bucket);
      if (typeof keys === "string") return Object.prototype.hasOwnProperty.call(bucket, keys) ? {[keys]: clone(bucket[keys])} : {};
      if (Array.isArray(keys)) {
        const out = {};
        for (const key of keys) if (Object.prototype.hasOwnProperty.call(bucket, key)) out[key] = clone(bucket[key]);
        return out;
      }
      const out = {};
      for (const [key, fallback] of Object.entries(keys)) {
        out[key] = Object.prototype.hasOwnProperty.call(bucket, key) ? clone(bucket[key]) : clone(fallback);
      }
      return out;
    },
    async set(values) {
      for (const [key, value] of Object.entries(values)) bucket[key] = clone(value);
    },
    async remove(keys) {
      for (const key of Array.isArray(keys) ? keys : [keys]) delete bucket[key];
    }
  };
}

function eventSink() {
  const listeners = [];
  return {
    listeners,
    addListener(fn) { listeners.push(fn); }
  };
}

function createWorker(shared) {
  const onInstalled = eventSink();
  const onStartup = eventSink();
  const onMessage = eventSink();
  const onAlarm = eventSink();

  const chrome = {
    runtime: {onInstalled, onStartup, onMessage},
    alarms: {
      onAlarm,
      async get(name) { return shared.alarms.get(name) || null; },
      create(name, spec) { shared.alarms.set(name, {name, ...clone(spec)}); }
    },
    storage: {
      local: storageArea(shared.local),
      session: storageArea(shared.session)
    },
    tabs: {
      async create(spec) {
        const id = shared.nextTabId++;
        shared.createCount += 1;
        const tab = {id, url: spec.url || "about:blank", pendingUrl: spec.url || "about:blank", active: spec.active !== false};
        shared.tabs.set(id, tab);
        return clone(tab);
      },
      async get(id) {
        if (!shared.tabs.has(id)) throw new Error("TAB_NOT_FOUND");
        return clone(shared.tabs.get(id));
      },
      async update(id, spec) {
        if (!shared.tabs.has(id)) throw new Error("TAB_NOT_FOUND");
        shared.updateCount += 1;
        const tab = shared.tabs.get(id);
        if (spec.url) {
          tab.url = spec.url;
          tab.pendingUrl = spec.url;
        }
        if (Object.prototype.hasOwnProperty.call(spec, "active")) tab.active = spec.active;
        shared.tabs.set(id, tab);
        if (shared.failAfterUpdateOnce) {
          shared.failAfterUpdateOnce = false;
          throw new Error("SERVICE_WORKER_RESTART_SIMULATED_AFTER_NAVIGATION_EFFECT");
        }
        return clone(tab);
      }
    },
    downloads: {async download() { return 1; }}
  };

  const core = {
    LEDGER_SCHEMA: "CHATBRIDGE_LEDGER_TEST",
    PACKET_SCHEMA: "CHATBRIDGE_PACKET_TEST",
    async sha256(value) { return crypto.createHash("sha256").update(JSON.stringify(value)).digest("hex"); },
    latestTranscriptEvents(ledger) { return ledger.events || []; },
    missingRanges() { return []; },
    buildWorkingSetPrompts() { return [{kind: "FINAL", text: "restore exactly this compact working set"}]; },
    buildReplayPrompts() { return [{kind: "FINAL", text: "restore exactly this full replay"}]; }
  };

  const context = vm.createContext({
    console,
    Date,
    Math,
    URL,
    Promise,
    setTimeout,
    clearTimeout,
    crypto,
    btoa: (value) => Buffer.from(String(value), "binary").toString("base64"),
    unescape,
    encodeURIComponent,
    chrome,
    ChatBridgeCore: core,
    ChatBridgeEdgeEgress: {async flushLedger() { return {ok: true}; }},
    importScripts() {}
  });
  context.globalThis = context;
  vm.runInContext(backgroundSource, context, {filename: "background.js"});

  async function send(message, tabId) {
    assert.equal(onMessage.listeners.length, 1, "one message receiver per worker instance");
    return new Promise((resolve, reject) => {
      let settled = false;
      const timeout = setTimeout(() => {
        if (!settled) reject(new Error(`MESSAGE_TIMEOUT:${message.type}`));
      }, 2000);
      const sendResponse = (response) => {
        if (settled) return;
        settled = true;
        clearTimeout(timeout);
        resolve(response);
      };
      onMessage.listeners[0](message, tabId == null ? {} : {tab: {id: tabId}}, sendResponse);
    });
  }

  return {send, onInstalled, onStartup, onAlarm};
}

function seedLedger(shared, conversationKey = "conv-1", missionId = "MISSION-FUSE-WORKSPACE-20260923-001") {
  shared.local[`chatbridgeLedger:${conversationKey}`] = {
    schema: "CHATBRIDGE_LEDGER_TEST",
    version: "0.3.0",
    conversationKey,
    namespaceKey: missionId,
    source: {
      title: "Capacity canary",
      successorUrl: "https://chatgpt.com/",
      pathId: "rendered-dom-companion",
      provider: "CHATGPT",
      independentGroup: "browser-rendered-dom"
    },
    events: [],
    sourceHeads: {},
    lastEventHash: "",
    terminalObserved: false,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    manifest: {}
  };
}

test("manifest uses chrome.alarms for MV3 durable wake without broadening host access", () => {
  assert.ok(manifest.permissions.includes("alarms"));
  assert.deepEqual(manifest.host_permissions, ["https://chatgpt.com/*"]);
  assert.doesNotMatch(backgroundSource, /setInterval\s*\(/);
  assert.match(backgroundSource, /chrome\.alarms\.create\(RECONCILE_ALARM/);
  assert.match(backgroundSource, /chrome\.storage\.local\.set\(\{\[TRANSFER_KEY\]/);
});

test("MV3_RESTART_DURING_CAPACITY_HANDOFF recovers one persisted transfer and at most one successor", async () => {
  const shared = createSharedState();
  seedLedger(shared);
  shared.failAfterUpdateOnce = true;

  const worker1 = createWorker(shared);
  const first = await worker1.send({
    type: "CHATBRIDGE_OPEN",
    conversationKey: "conv-1",
    reason: "PRE_LIMIT_PRESSURE"
  });
  assert.equal(first.ok, false, "simulated worker loss leaves effect unknown instead of claiming success");

  const checkpointed = clone(shared.local.pendingChatBridgeTransfer);
  assert.ok(checkpointed.transferId);
  assert.equal(checkpointed.clientEpoch, 1);
  assert.equal(checkpointed.state, "NAVIGATING_SUCCESSOR");
  assert.equal(checkpointed.effectState, "EFFECT_UNKNOWN");
  assert.equal(shared.createCount, 1, "one reserved target tab exists before restart");

  const worker2 = createWorker(shared);
  const recovered = await worker2.send({type: "CHATBRIDGE_RECONCILE", reason: "MV3_RESTART_CANARY"});
  assert.equal(recovered.ok, true);
  assert.equal(recovered.transferId, checkpointed.transferId);
  assert.equal(recovered.clientEpoch, checkpointed.clientEpoch);
  assert.equal(shared.createCount, 1, "restart reuses the reserved target tab; no duplicate successor");

  const active = clone(shared.local.pendingChatBridgeTransfer);
  assert.equal(active.state, "IN_FLIGHT");
  assert.equal(active.transferId, checkpointed.transferId);
  assert.equal(active.clientEpoch, checkpointed.clientEpoch);
  assert.equal(active.successorBound, true);
  assert.match(shared.tabs.get(active.targetTabId).url, /^https:\/\/chatgpt\.com\//);

  const pending = await worker2.send({type: "CHATBRIDGE_GET_PENDING"}, active.targetTabId);
  assert.equal(pending.ok, true);
  assert.equal(pending.pending.transferId, checkpointed.transferId);
  assert.equal(pending.pending.clientEpoch, checkpointed.clientEpoch);
  assert.equal(pending.pending.packetCount, 1);

  const started = await worker2.send({
    type: "CHATBRIDGE_PACKET_EFFECT_STARTED",
    transferId: active.transferId,
    clientEpoch: active.clientEpoch,
    packetIndex: 1
  }, active.targetTabId);
  assert.equal(started.ok, true);

  const worker3 = createWorker(shared);
  const afterPacketRestart = await worker3.send({type: "CHATBRIDGE_GET_PENDING"}, active.targetTabId);
  assert.equal(afterPacketRestart.pending.effectReadbackRequired, true);
  assert.equal(afterPacketRestart.pending.autosendAllowed, false, "restart cannot blindly replay an uncertain provider send");

  const committed = await worker3.send({
    type: "CHATBRIDGE_PACKET_EFFECT_READBACK",
    transferId: active.transferId,
    clientEpoch: active.clientEpoch,
    packetIndex: 1,
    observed: "COMMITTED"
  }, active.targetTabId);
  assert.equal(committed.ok, true);
  assert.equal(committed.complete, true);
  assert.equal(shared.createCount, 1);

  const finalState = clone(shared.local.pendingChatBridgeTransfer);
  assert.equal(finalState.state, "COMPLETED");
  assert.equal(finalState.deliveryProofTier, "D1_DELIVERY_JOURNALED");
  assert.equal(finalState.currentIndex, 1);
});

test("stale persisted transfer is rejected after a newer client_epoch takeover", async () => {
  const shared = createSharedState();
  const missionId = "MISSION-FUSE-WORKSPACE-20260923-001";
  seedLedger(shared, "conv-stale", missionId);
  const worker1 = createWorker(shared);
  const opened = await worker1.send({type: "CHATBRIDGE_OPEN", conversationKey: "conv-stale", reason: "PRE_LIMIT_PRESSURE"});
  assert.equal(opened.ok, true);
  assert.equal(shared.createCount, 1);

  shared.local[`chatbridgeClientEpoch:${missionId}`] = opened.clientEpoch + 1;
  const worker2 = createWorker(shared);
  const rejected = await worker2.send({type: "CHATBRIDGE_RECONCILE", reason: "NEWER_EPOCH_TAKEOVER_CANARY"});
  assert.equal(rejected.ok, false);
  assert.equal(rejected.state, "STALE_PERSISTED_TRANSFER_REJECTED");
  assert.equal(shared.local.pendingChatBridgeTransfer.state, "STALE_REJECTED");
  assert.equal(shared.local.pendingChatBridgeTransfer.autosendAllowed, false);
  assert.equal(shared.createCount, 1, "stale writer authority cannot create a successor");
});

test("explicit USER_INTERRUPTION survives restart and never auto-resumes", async () => {
  const shared = createSharedState();
  seedLedger(shared, "conv-interrupt");
  const worker1 = createWorker(shared);
  const opened = await worker1.send({type: "CHATBRIDGE_OPEN", conversationKey: "conv-interrupt", reason: "PRE_LIMIT_PRESSURE"});
  assert.equal(opened.ok, true);

  const interrupted = await worker1.send({type: "CHATBRIDGE_USER_INTERRUPTION"}, opened.tabId);
  assert.equal(interrupted.ok, true);
  assert.equal(interrupted.state, "USER_INTERRUPTION_NON_RESUME");

  const worker2 = createWorker(shared);
  const pending = await worker2.send({type: "CHATBRIDGE_GET_PENDING"}, opened.tabId);
  assert.equal(pending.ok, true);
  assert.equal(pending.pending, null);
  assert.equal(pending.recoveryState, "USER_INTERRUPTION_NON_RESUME");
  assert.equal(shared.local.pendingChatBridgeTransfer.autosendAllowed, false);
});
