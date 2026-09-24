"use strict";

importScripts("bridge-core.js", "edge-egress.js");
const core = globalThis.ChatBridgeCore;
const edgeEgress = globalThis.ChatBridgeEdgeEgress;

const DEFAULTS = Object.freeze({
  autoSend: true,
  maxReplayChars: 28000,
  tokenThreshold: 65000,
  messageThreshold: 80,
  captureIntervalMs: 30000
});

const TRANSFER_KEY = "pendingChatBridgeTransfer";
const LAST_VERIFIED_TRANSFER_KEY = "lastVerifiedChatBridgeTransfer";
const CLIENT_EPOCH_PREFIX = "chatbridgeClientEpoch:";
const RECONCILE_ALARM = "chatbridge-mv3-reconcile";
const DELIVERY_D0 = "D0_RESULT_READY";
const DELIVERY_D1 = "D1_DELIVERY_JOURNALED";
const DELIVERY_D2 = "D2_CURRENT_CLIENT_RENDER_VERIFIED";
const DELIVERY_D3 = "D3_EXPLICIT_OWNER_INTERACTION_CONFIRMED";

chrome.runtime.onInstalled.addListener(() => initialiseRuntime("INSTALLED"));
chrome.runtime.onStartup.addListener(() => initialiseRuntime("STARTUP"));
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm && alarm.name === RECONCILE_ALARM) {
    reconcilePendingTransfer({allowRepair: true, reason: "ALARM_WAKE"}).catch(() => {});
  }
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  handleMessage(request, sender).then(sendResponse).catch((error) => {
    sendResponse({ok: false, error: String(error && error.message || error)});
  });
  return true;
});

async function initialiseRuntime(reason) {
  try {
    const current = await chrome.storage.local.get("chatbridgeSettings");
    if (!current.chatbridgeSettings) {
      await chrome.storage.local.set({chatbridgeSettings: DEFAULTS});
    }
    await ensureReconcileAlarm();
    await reconcilePendingTransfer({allowRepair: true, reason});
  } catch (_) {
    // A wake failure cannot be promoted into mission failure or new effect authority.
  }
}

async function ensureReconcileAlarm() {
  const existing = await chrome.alarms.get(RECONCILE_ALARM);
  if (!existing) chrome.alarms.create(RECONCILE_ALARM, {periodInMinutes: 0.5});
}

function ledgerStorageKey(conversationKey) {
  return `chatbridgeLedger:${String(conversationKey)}`;
}

function clientEpochStorageKey(missionId) {
  return `${CLIENT_EPOCH_PREFIX}${String(missionId)}`;
}

async function loadLedger(conversationKey) {
  const key = ledgerStorageKey(conversationKey);
  const stored = await chrome.storage.local.get(key);
  return stored[key] || null;
}

async function saveLedger(ledger) {
  const key = ledgerStorageKey(ledger.conversationKey);
  await chrome.storage.local.set({[key]: ledger});
  await chrome.storage.local.set({latestChatBridgeSummary: {
    schema: ledger.schema,
    conversationKey: ledger.conversationKey,
    namespaceKey: ledger.namespaceKey,
    title: ledger.source.title,
    updatedAt: ledger.updatedAt,
    manifest: ledger.manifest
  }});
  await chrome.storage.session.set({latestChatBridgeConversationKey: ledger.conversationKey});
}

function newLedger(packet) {
  return {
    schema: core.LEDGER_SCHEMA,
    version: "0.3.0",
    conversationKey: packet.conversationKey,
    namespaceKey: packet.namespaceKey,
    source: packet.source,
    pathRegister: [{
      pathId: packet.source.pathId,
      kind: "RENDERED_DOM",
      sourceProvider: packet.source.provider,
      independentGroup: packet.source.independentGroup,
      state: "AVAILABLE",
      authoritative: false
    }],
    events: [],
    sourceHeads: {},
    lastEventHash: "",
    terminalObserved: false,
    createdAt: packet.capturedAt,
    updatedAt: packet.capturedAt,
    manifest: {
      restoreMode: "NO_ALPHA_OMEGA_CAPTURE",
      integrityState: "EMPTY",
      coverageState: "EMPTY",
      exactContextComplete: false
    }
  };
}

function eventHashPayload(event) {
  const copy = Object.assign({}, event);
  delete copy.eventHash;
  return copy;
}

async function appendObservation(ledger, observation, capturedAt) {
  const sourceMessageId = String(observation.sourceMessageId || `${observation.role}-${observation.sourceSequence}`);
  const contentPayload = {
    sourceMessageId,
    sourceSequence: Number(observation.sourceSequence),
    role: observation.role,
    stream: observation.stream,
    eventType: observation.eventType || "MESSAGE",
    content: observation.text,
    artifacts: observation.artifacts || []
  };
  const contentHash = await core.sha256(contentPayload);
  const previousHeadId = ledger.sourceHeads[sourceMessageId] || "";
  const previousHead = previousHeadId ? ledger.events.find((event) => event.eventId === previousHeadId) : null;
  if (previousHead && previousHead.contentHash === contentHash) return false;

  const event = {
    eventId: `cbbe-${ledger.conversationKey}-${ledger.events.length + 1}-${contentHash.slice(0, 12)}`,
    appendSequence: ledger.events.length + 1,
    sourceSequence: Number(observation.sourceSequence),
    sourceMessageId,
    role: String(observation.role || "unknown"),
    stream: String(observation.stream || "OTHER"),
    eventType: String(observation.eventType || "MESSAGE"),
    content: String(observation.text || ""),
    occurredAt: observation.occurredAt || "",
    capturedAt,
    executionState: "OBSERVED",
    payloadAvailability: "RAW_GOVERNED",
    sensitivity: "GOVERNED_LOCAL",
    artifacts: observation.artifacts || [],
    contentHash,
    previousEventHash: ledger.lastEventHash || "",
    supersedesEventId: previousHeadId,
    pathId: "rendered-dom-companion",
    providerReadback: "BROWSER_RENDERED_DOM_OBSERVATION"
  };
  event.eventHash = await core.sha256(eventHashPayload(event));
  ledger.events.push(event);
  ledger.sourceHeads[sourceMessageId] = event.eventId;
  ledger.lastEventHash = event.eventHash;
  return true;
}

async function appendTerminalNotice(ledger, notice, capturedAt) {
  if (!notice) return false;
  const contentHash = await core.sha256({eventType: "TERMINAL_WARNING", content: notice});
  if (ledger.events.some((event) => event.eventType === "TERMINAL_WARNING" && event.contentHash === contentHash)) return false;
  const event = {
    eventId: `cbbe-${ledger.conversationKey}-${ledger.events.length + 1}-${contentHash.slice(0, 12)}`,
    appendSequence: ledger.events.length + 1,
    sourceSequence: null,
    sourceMessageId: `terminal-${contentHash.slice(0, 12)}`,
    role: "system",
    stream: "TERMINAL",
    eventType: "TERMINAL_WARNING",
    content: notice,
    occurredAt: capturedAt,
    capturedAt,
    executionState: "OBSERVED",
    payloadAvailability: "RAW_GOVERNED",
    sensitivity: "NON_SENSITIVE_OPERATIONAL",
    artifacts: [],
    contentHash,
    previousEventHash: ledger.lastEventHash || "",
    supersedesEventId: "",
    pathId: "rendered-dom-companion",
    providerReadback: "BROWSER_RENDERED_DOM_OBSERVATION"
  };
  event.eventHash = await core.sha256(eventHashPayload(event));
  ledger.events.push(event);
  ledger.lastEventHash = event.eventHash;
  ledger.terminalObserved = true;
  return true;
}

async function verifyChain(ledger) {
  let previous = "";
  for (const event of ledger.events) {
    if (event.previousEventHash !== previous) return false;
    const expected = await core.sha256(eventHashPayload(event));
    if (expected !== event.eventHash) return false;
    previous = event.eventHash;
  }
  return previous === (ledger.lastEventHash || "");
}

async function buildManifest(ledger) {
  const latest = core.latestTranscriptEvents(ledger);
  const sequences = latest.map((event) => event.sourceSequence).filter(Number.isFinite);
  const first = sequences.length ? Math.min(...sequences) : null;
  const last = sequences.length ? Math.max(...sequences) : null;
  const missing = first === null || last === null ? [] : core.missingRanges(sequences, 1, last);
  const unresolvedArtifacts = latest.flatMap((event) => event.artifacts || [])
    .filter((artifact) => artifact.requiredForContext && artifact.availability !== "VERIFIED_AVAILABLE")
    .map((artifact) => ({artifactKey: artifact.artifactKey, filename: artifact.filename, locator: artifact.locator}));
  const chainValid = await verifyChain(ledger);
  const exactRenderedRange = Boolean(latest.length && first === 1 && missing.length === 0 && chainValid && unresolvedArtifacts.length === 0);
  const streamWatermarks = {};
  for (const event of latest) {
    const stream = event.stream || "OTHER";
    const current = streamWatermarks[stream] || {first: event.sourceSequence, last: event.sourceSequence, count: 0};
    current.first = Math.min(current.first, event.sourceSequence);
    current.last = Math.max(current.last, event.sourceSequence);
    current.count += 1;
    streamWatermarks[stream] = current;
  }
  return {
    conversationKey: ledger.conversationKey,
    namespaceKey: ledger.namespaceKey,
    restoreMode: exactRenderedRange ? "EXACT_SINGLE_PATH_TRANSCRIPT_RESTORE" : "BOUNDED_MULTIPATH_MULTISTREAM_RESTORE",
    integrityState: chainValid ? "HASH_CHAIN_VERIFIED" : "REJECT_CONFLICTED",
    coverageState: exactRenderedRange ? "COMPLETE_RENDERED_MESSAGE_RANGE" : "RENDERED_RANGE_WITH_EXPLICIT_GAPS",
    providerCompleteness: "RENDERED_DOM_ONLY_NOT_HIDDEN_NATIVE_EVENTS",
    exactContextComplete: false,
    exactRenderedTranscriptComplete: exactRenderedRange,
    firstSourceSequence: first,
    lastSourceSequence: last,
    capturedEventCount: ledger.events.length,
    latestRenderedMessageCount: latest.length,
    missingRanges: missing,
    unresolvedArtifacts,
    streamWatermarks,
    pathGroups: ["browser-rendered-dom"],
    chainHeadSha256: ledger.lastEventHash || "",
    terminalObserved: Boolean(ledger.terminalObserved),
    truthBoundary: "Rendered browser messages are captured and hash-chained. Hidden provider events and uncaptured legacy content are not inferred."
  };
}

async function capturePacket(packet) {
  validatePacket(packet);
  const ledger = await loadLedger(packet.conversationKey) || newLedger(packet);
  if (ledger.namespaceKey !== packet.namespaceKey) throw new Error("CONVERSATION_NAMESPACE_CONFLICT");
  for (const observation of packet.observations) await appendObservation(ledger, observation, packet.capturedAt);
  await appendTerminalNotice(ledger, packet.terminalNotice, packet.capturedAt);
  ledger.source = packet.source;
  ledger.updatedAt = packet.capturedAt;
  ledger.manifest = await buildManifest(ledger);
  // Full local capture is committed before any egress attempt. Courier failure is isolated.
  await saveLedger(ledger);
  if (edgeEgress) await edgeEgress.flushLedger(ledger, {reason: "CAPTURE"});
  return ledger;
}

async function loadPendingTransfer() {
  const local = await chrome.storage.local.get(TRANSFER_KEY);
  if (local[TRANSFER_KEY]) return local[TRANSFER_KEY];
  const session = await chrome.storage.session.get(TRANSFER_KEY);
  return session[TRANSFER_KEY] || null;
}

async function persistPendingTransfer(pending) {
  const next = Object.assign({}, pending, {updatedAt: new Date().toISOString()});
  await chrome.storage.local.set({[TRANSFER_KEY]: next});
  await chrome.storage.session.set({[TRANSFER_KEY]: next});
  return next;
}

async function persistLastVerifiedTransfer(pending) {
  const receipt = {
    schema: "CHATBRIDGE_LAST_VERIFIED_TRANSFER_V1",
    transferId: pending.transferId,
    missionId: pending.missionId,
    conversationKey: pending.conversationKey,
    clientEpoch: pending.clientEpoch,
    state: pending.state,
    currentIndex: pending.currentIndex,
    packetCount: pending.prompts.length,
    targetTabId: pending.targetTabId,
    deliveryProofTier: pending.deliveryProofTier || DELIVERY_D1,
    completedAt: pending.completedAt || "",
    updatedAt: new Date().toISOString()
  };
  await chrome.storage.local.set({[LAST_VERIFIED_TRANSFER_KEY]: receipt});
  return receipt;
}

async function readClientEpoch(missionId) {
  const key = clientEpochStorageKey(missionId);
  const row = await chrome.storage.local.get(key);
  const value = Number(row[key] || 0);
  return Number.isFinite(value) && value >= 0 ? value : 0;
}

async function allocateClientEpoch(missionId) {
  const key = clientEpochStorageKey(missionId);
  const next = (await readClientEpoch(missionId)) + 1;
  await chrome.storage.local.set({[key]: next});
  return next;
}

function transferIsTerminal(pending) {
  return !pending || ["COMPLETED", "STALE_REJECTED", "USER_INTERRUPTION"].includes(pending.state);
}

function transferBindingMatches(pending, request, sender) {
  return Boolean(
    pending &&
    pending.transferId === request.transferId &&
    Number(pending.clientEpoch) === Number(request.clientEpoch) &&
    pending.targetTabId === sender.tab?.id
  );
}

async function reserveTargetTab(pending) {
  if (pending.targetTabId != null) return pending;
  const tab = await chrome.tabs.create({url: "about:blank", active: true});
  pending.targetTabId = tab.id;
  pending.state = "TAB_RESERVED";
  pending.pendingAtomicActionId = "";
  pending.effectState = "NO_EFFECT_PROVEN";
  pending.successorBound = false;
  return persistPendingTransfer(pending);
}

function isChatGptUrl(value) {
  try {
    const parsed = new URL(value || "");
    return parsed.protocol === "https:" && parsed.hostname === "chatgpt.com";
  } catch (_) {
    return false;
  }
}

async function navigateReservedTab(pending) {
  pending.state = "NAVIGATING_SUCCESSOR";
  pending.pendingAtomicActionId = "NAVIGATE_SUCCESSOR";
  pending.effectIdentity = `${pending.transferId}:navigate-successor`;
  pending.effectState = "EFFECT_UNKNOWN";
  pending = await persistPendingTransfer(pending);
  try {
    await chrome.tabs.update(pending.targetTabId, {url: pending.targetUrl, active: true});
  } catch (error) {
    pending.lastRecoveryError = String(error && error.message || error);
    pending.retryMetadata = {
      reason: "NAVIGATION_CALL_FAILED_EFFECT_UNKNOWN",
      at: new Date().toISOString()
    };
    await persistPendingTransfer(pending);
    throw error;
  }
  pending.state = "IN_FLIGHT";
  pending.pendingAtomicActionId = "";
  pending.effectState = "RESPONSE_ONLY";
  pending.successorBound = true;
  pending.lastVerifiedTransferState = "SUCCESSOR_TAB_BOUND";
  return persistPendingTransfer(pending);
}

async function reconcilePendingTransfer(options) {
  const settings = Object.assign({allowRepair: false, reason: "UNSPECIFIED"}, options || {});
  let pending = await loadPendingTransfer();
  if (!pending) return {ok: true, state: "NO_PENDING_TRANSFER", pending: null};

  const currentEpoch = await readClientEpoch(pending.missionId);
  if (Number(pending.clientEpoch) < currentEpoch) {
    pending.state = "STALE_REJECTED";
    pending.staleWriterAuthority = true;
    pending.autosendAllowed = false;
    pending.retryMetadata = {reason: "NEWER_CLIENT_EPOCH_TAKEOVER", at: new Date().toISOString()};
    await persistPendingTransfer(pending);
    return {ok: false, state: "STALE_PERSISTED_TRANSFER_REJECTED", pending};
  }
  if (Number(pending.clientEpoch) > currentEpoch) {
    pending.autosendAllowed = false;
    pending.retryMetadata = {reason: "CLIENT_EPOCH_READBACK_BEHIND", at: new Date().toISOString()};
    await persistPendingTransfer(pending);
    return {ok: false, state: "CLIENT_EPOCH_READBACK_BEHIND", pending};
  }
  if (pending.userInterruption || pending.state === "USER_INTERRUPTION") {
    pending.state = "USER_INTERRUPTION";
    pending.autosendAllowed = false;
    await persistPendingTransfer(pending);
    return {ok: false, state: "USER_INTERRUPTION_NON_RESUME", pending};
  }
  if (pending.state === "COMPLETED") {
    await persistLastVerifiedTransfer(pending);
    return {ok: true, state: "TRANSFER_ALREADY_COMPLETED", pending};
  }

  if (pending.targetTabId == null) {
    if (!settings.allowRepair) return {ok: false, state: "TARGET_TAB_RESERVATION_REQUIRED", pending};
    pending = await reserveTargetTab(pending);
  }

  let tab = null;
  try {
    tab = await chrome.tabs.get(pending.targetTabId);
  } catch (_) {
    tab = null;
  }

  if (!tab) {
    if (pending.effectState === "EFFECT_UNKNOWN" && String(pending.pendingAtomicActionId || "").startsWith("SEND_PACKET:")) {
      pending.autosendAllowed = false;
      pending.retryMetadata = {reason: "POSSIBLE_PROVIDER_EFFECT_REQUIRES_READBACK", at: new Date().toISOString()};
      await persistPendingTransfer(pending);
      return {ok: false, state: "POSSIBLE_EFFECT_PENDING_READBACK", pending};
    }
    if (!settings.allowRepair) return {ok: false, state: "TARGET_TAB_MISSING", pending};
    pending.targetTabId = null;
    pending.successorBound = false;
    pending.effectState = "NO_EFFECT_PROVEN";
    pending.pendingAtomicActionId = "";
    pending = await reserveTargetTab(pending);
    tab = await chrome.tabs.get(pending.targetTabId);
  }

  const tabUrl = String(tab.url || tab.pendingUrl || "");
  if (pending.effectState === "EFFECT_UNKNOWN" && String(pending.pendingAtomicActionId || "").startsWith("SEND_PACKET:")) {
    pending.autosendAllowed = false;
    await persistPendingTransfer(pending);
    return {ok: false, state: "POSSIBLE_EFFECT_PENDING_READBACK", pending};
  }

  if (tabUrl === "about:blank" || pending.state === "TAB_RESERVED") {
    if (!settings.allowRepair) return {ok: false, state: "SUCCESSOR_NAVIGATION_REQUIRED", pending};
    pending.effectState = "NO_EFFECT_PROVEN";
    pending.pendingAtomicActionId = "";
    pending = await persistPendingTransfer(pending);
    pending = await navigateReservedTab(pending);
    return {ok: true, state: "RECOVERED_SAME_TRANSFER", pending};
  }

  if (isChatGptUrl(tabUrl)) {
    if (pending.pendingAtomicActionId === "NAVIGATE_SUCCESSOR") {
      pending.pendingAtomicActionId = "";
      pending.effectState = "RESPONSE_ONLY";
    }
    pending.state = "IN_FLIGHT";
    pending.successorBound = true;
    pending.autosendAllowed = pending.effectState !== "EFFECT_UNKNOWN";
    pending.lastVerifiedTransferState = "SUCCESSOR_TAB_BOUND";
    pending = await persistPendingTransfer(pending);
    return {ok: true, state: "RECOVER_BOUND_SUCCESSOR", pending};
  }

  pending.autosendAllowed = false;
  pending.retryMetadata = {reason: "TARGET_TAB_DIVERGED", at: new Date().toISOString(), observedUrl: tabUrl};
  await persistPendingTransfer(pending);
  return {ok: false, state: "TARGET_TAB_DIVERGED", pending};
}

async function buildPendingTransfer(ledger, request) {
  const stored = await chrome.storage.local.get("chatbridgeSettings");
  const settings = Object.assign({}, DEFAULTS, stored.chatbridgeSettings || {});
  const reason = String(request.reason || "UNSPECIFIED");
  const capacitySafe = /CAPACITY|LIMIT|PRE_LIMIT|TERMINAL/i.test(reason);
  const prompts = capacitySafe
    ? core.buildWorkingSetPrompts(ledger, {
        maxChars: Math.min(Number(settings.maxReplayChars) || 28000, 16000),
        maxEvents: 12
      })
    : core.buildReplayPrompts(ledger, settings.maxReplayChars);
  const missionId = String(request.missionId || ledger.namespaceKey || `CHATBRIDGE:${ledger.conversationKey}`);
  const clientEpoch = await allocateClientEpoch(missionId);
  const entropy = globalThis.crypto && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return {
    schema: "CHATBRIDGE_MV3_TRANSFER_V1",
    transferId: `CBT-${ledger.conversationKey}-E${clientEpoch}-${entropy}`,
    missionId,
    conversationKey: ledger.conversationKey,
    clientEpoch,
    targetUrl: ledger.source.successorUrl,
    prompts,
    currentIndex: 0,
    targetTabId: null,
    reason,
    restoreMode: capacitySafe ? "CAPACITY_SAFE_WORKING_SET" : "FULL_TRANSCRIPT_REPLAY",
    state: "CHECKPOINTED",
    handoffState: "CHECKPOINTED",
    pendingAtomicActionId: "",
    effectIdentity: "",
    effectState: "NO_EFFECT_PROVEN",
    successorBound: false,
    autosendAllowed: false,
    userInterruption: false,
    deliveryProofTier: DELIVERY_D0,
    retryMetadata: {reason: "INITIAL_CHECKPOINT", at: new Date().toISOString()},
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  };
}

async function advancePacket(pending, evidenceKind) {
  pending.currentIndex += 1;
  pending.pendingAtomicActionId = "";
  pending.effectState = "RESPONSE_ONLY";
  pending.effectIdentity = "";
  pending.lastPacketCommitEvidence = String(evidenceKind || "EXPLICIT_CONSUMED");
  pending.lastPacketCommitAt = new Date().toISOString();
  if (pending.currentIndex >= pending.prompts.length) {
    pending.state = "COMPLETED";
    pending.handoffState = "COMPLETED";
    pending.completedAt = new Date().toISOString();
    pending.autosendAllowed = false;
    pending.deliveryProofTier = DELIVERY_D1;
    pending = await persistPendingTransfer(pending);
    await persistLastVerifiedTransfer(pending);
    await chrome.storage.session.remove(TRANSFER_KEY);
    return {ok: true, complete: true, deliveryProofTier: pending.deliveryProofTier};
  }
  pending.autosendAllowed = true;
  pending = await persistPendingTransfer(pending);
  return {ok: true, complete: false, nextPacketIndex: pending.currentIndex + 1};
}

async function handleMessage(request, sender) {
  if (!request || typeof request.type !== "string") return {ok: false, error: "INVALID_REQUEST"};

  if (request.type === "CHATBRIDGE_SETTINGS") {
    const stored = await chrome.storage.local.get("chatbridgeSettings");
    return {ok: true, settings: Object.assign({}, DEFAULTS, stored.chatbridgeSettings || {})};
  }

  if (request.type === "CHATBRIDGE_CAPTURE") {
    const ledger = await capturePacket(request.packet);
    return {ok: true, conversationKey: ledger.conversationKey, manifest: ledger.manifest};
  }

  if (request.type === "CHATBRIDGE_GET_LEDGER") {
    const ledger = await loadLedger(request.conversationKey);
    return {ok: true, ledger};
  }

  if (request.type === "CHATBRIDGE_EDGE_EGRESS_STATUS") {
    const ledger = await loadLedger(request.conversationKey);
    if (!ledger) throw new Error("LEDGER_NOT_FOUND");
    return edgeEgress
      ? edgeEgress.flushLedger(ledger, {reason: String(request.reason || "STATUS_OR_CATCHUP")})
      : {ok: false, state: "EDGE_EGRESS_MODULE_MISSING"};
  }

  if (request.type === "CHATBRIDGE_EXPORT_LEDGER") {
    const ledger = await loadLedger(request.conversationKey);
    if (!ledger) throw new Error("LEDGER_NOT_FOUND");
    const text = JSON.stringify(ledger, null, 2);
    const dataUrl = `data:application/json;base64,${btoa(unescape(encodeURIComponent(text)))}`;
    const downloadId = await chrome.downloads.download({
      url: dataUrl,
      filename: `ChatBridge-${ledger.conversationKey}-omega49-ledger.json`,
      saveAs: true
    });
    return {ok: true, downloadId, manifest: ledger.manifest};
  }

  if (request.type === "CHATBRIDGE_OPEN") {
    const ledger = await loadLedger(request.conversationKey);
    if (!ledger) throw new Error("LEDGER_NOT_FOUND");

    const prior = await loadPendingTransfer();
    if (prior && !transferIsTerminal(prior) && prior.conversationKey === ledger.conversationKey) {
      const recovered = await reconcilePendingTransfer({allowRepair: true, reason: "OPEN_REUSE"});
      if (recovered.pending && !transferIsTerminal(recovered.pending)) {
        const active = recovered.pending;
        return {
          ok: recovered.state !== "STALE_PERSISTED_TRANSFER_REJECTED",
          reused: true,
          transferId: active.transferId,
          clientEpoch: active.clientEpoch,
          tabId: active.targetTabId,
          packetCount: active.prompts.length,
          restoreMode: active.restoreMode,
          recoveryState: recovered.state
        };
      }
    }
    if (prior && !transferIsTerminal(prior) && prior.conversationKey !== ledger.conversationKey) {
      return {ok: false, error: "ACTIVE_TRANSFER_CONFLICT", transferId: prior.transferId};
    }

    let pending = await buildPendingTransfer(ledger, request);
    pending = await persistPendingTransfer(pending);
    const recovered = await reconcilePendingTransfer({allowRepair: true, reason: "NEW_TRANSFER"});
    pending = recovered.pending || pending;
    if (!recovered.ok) return {ok: false, error: recovered.state, transferId: pending.transferId, clientEpoch: pending.clientEpoch};
    return {
      ok: true,
      reused: false,
      transferId: pending.transferId,
      clientEpoch: pending.clientEpoch,
      tabId: pending.targetTabId,
      packetCount: pending.prompts.length,
      restoreMode: pending.restoreMode,
      recoveryState: recovered.state
    };
  }

  if (request.type === "CHATBRIDGE_RECONCILE") {
    const receipt = await reconcilePendingTransfer({allowRepair: true, reason: String(request.reason || "EXPLICIT_RECONCILE")});
    return {ok: receipt.ok, state: receipt.state, transferId: receipt.pending?.transferId || "", clientEpoch: receipt.pending?.clientEpoch || 0};
  }

  if (request.type === "CHATBRIDGE_GET_PENDING") {
    const receipt = await reconcilePendingTransfer({allowRepair: true, reason: "GET_PENDING"});
    const pending = receipt.pending;
    if (!pending || pending.targetTabId !== sender.tab?.id) return {ok: true, pending: null, recoveryState: receipt.state};
    const currentEpoch = await readClientEpoch(pending.missionId);
    if (Number(pending.clientEpoch) !== currentEpoch) {
      return {ok: false, pending: null, recoveryState: "STALE_CLIENT_EPOCH"};
    }
    if (pending.userInterruption || pending.state === "USER_INTERRUPTION") {
      return {ok: true, pending: null, recoveryState: "USER_INTERRUPTION_NON_RESUME"};
    }
    if (pending.state === "COMPLETED") {
      return {ok: true, pending: null, recoveryState: "TRANSFER_ALREADY_COMPLETED", deliveryProofTier: pending.deliveryProofTier};
    }
    const prompt = pending.prompts[pending.currentIndex] || null;
    if (!prompt) return {ok: true, pending: null, recoveryState: "NO_PACKET"};
    const effectReadbackRequired = pending.effectState === "EFFECT_UNKNOWN" && String(pending.pendingAtomicActionId || "").startsWith("SEND_PACKET:");
    return {ok: true, pending: {
      transferId: pending.transferId,
      clientEpoch: pending.clientEpoch,
      missionId: pending.missionId,
      conversationKey: pending.conversationKey,
      packetIndex: pending.currentIndex + 1,
      packetCount: pending.prompts.length,
      prompt,
      autosendAllowed: !effectReadbackRequired && pending.autosendAllowed !== false,
      effectReadbackRequired,
      pendingAtomicActionId: pending.pendingAtomicActionId || "",
      effectIdentity: pending.effectIdentity || ""
    }, recoveryState: effectReadbackRequired ? "POSSIBLE_EFFECT_PENDING_READBACK" : receipt.state};
  }

  if (request.type === "CHATBRIDGE_PACKET_EFFECT_STARTED") {
    let pending = await loadPendingTransfer();
    if (!transferBindingMatches(pending, request, sender)) return {ok: false, error: "TRANSFER_BINDING_MISMATCH"};
    if (pending.state !== "IN_FLIGHT") return {ok: false, error: "TRANSFER_NOT_IN_FLIGHT"};
    if (Number(request.packetIndex) !== pending.currentIndex + 1) return {ok: false, error: "PACKET_INDEX_MISMATCH"};
    pending.pendingAtomicActionId = `SEND_PACKET:${pending.currentIndex + 1}`;
    pending.effectIdentity = `${pending.transferId}:packet:${pending.currentIndex + 1}`;
    pending.effectState = "EFFECT_UNKNOWN";
    pending.autosendAllowed = false;
    pending.retryMetadata = {reason: "PROVIDER_SEND_STARTED_AWAITING_SEMANTIC_READBACK", at: new Date().toISOString()};
    pending = await persistPendingTransfer(pending);
    return {ok: true, effectIdentity: pending.effectIdentity};
  }

  if (request.type === "CHATBRIDGE_PACKET_EFFECT_READBACK") {
    let pending = await loadPendingTransfer();
    if (!transferBindingMatches(pending, request, sender)) return {ok: false, error: "TRANSFER_BINDING_MISMATCH"};
    if (Number(request.packetIndex) !== pending.currentIndex + 1) return {ok: false, error: "PACKET_INDEX_MISMATCH"};
    const observed = String(request.observed || "").toUpperCase();
    if (observed === "COMMITTED") return advancePacket(pending, "RENDERED_USER_MESSAGE_READBACK");
    if (observed === "NO_EFFECT_PROVEN") {
      pending.effectState = "NO_EFFECT_PROVEN";
      pending.pendingAtomicActionId = "";
      pending.effectIdentity = "";
      pending.autosendAllowed = true;
      pending.retryMetadata = {reason: "NO_EFFECT_PROVEN_BY_CURRENT_CLIENT_READBACK", at: new Date().toISOString()};
      await persistPendingTransfer(pending);
      return {ok: true, complete: false, replayAllowed: true};
    }
    return {ok: false, error: "EFFECT_READBACK_REQUIRED"};
  }

  if (request.type === "CHATBRIDGE_PACKET_CONSUMED") {
    const pending = await loadPendingTransfer();
    if (!transferBindingMatches(pending, request, sender)) return {ok: false, error: "TRANSFER_BINDING_MISMATCH"};
    if (Number(request.packetIndex || (pending.currentIndex + 1)) !== pending.currentIndex + 1) return {ok: false, error: "PACKET_INDEX_MISMATCH"};
    return advancePacket(pending, String(request.evidenceKind || "EXPLICIT_CONSUMED"));
  }

  if (request.type === "CHATBRIDGE_RESULT_RENDER_VERIFIED") {
    let pending = await loadPendingTransfer();
    if (!transferBindingMatches(pending, request, sender)) return {ok: false, error: "TRANSFER_BINDING_MISMATCH"};
    if (pending.state !== "COMPLETED") return {ok: false, error: "RESULT_NOT_TERMINAL"};
    pending.deliveryProofTier = DELIVERY_D2;
    pending.currentClientRenderVerifiedAt = new Date().toISOString();
    pending.humanReadInferred = false;
    pending = await persistPendingTransfer(pending);
    await persistLastVerifiedTransfer(pending);
    return {ok: true, deliveryProofTier: pending.deliveryProofTier};
  }

  if (request.type === "CHATBRIDGE_OWNER_INTERACTION") {
    let pending = await loadPendingTransfer();
    if (!transferBindingMatches(pending, request, sender)) return {ok: false, error: "TRANSFER_BINDING_MISMATCH"};
    if (pending.deliveryProofTier !== DELIVERY_D2 || request.explicit !== true) return {ok: false, error: "D3_EXPLICIT_INTERACTION_REQUIRED"};
    pending.deliveryProofTier = DELIVERY_D3;
    pending.ownerInteractionConfirmedAt = new Date().toISOString();
    pending = await persistPendingTransfer(pending);
    await persistLastVerifiedTransfer(pending);
    return {ok: true, deliveryProofTier: pending.deliveryProofTier};
  }

  if (request.type === "CHATBRIDGE_USER_INTERRUPTION") {
    let pending = await loadPendingTransfer();
    if (!pending || pending.targetTabId !== sender.tab?.id || pending.state === "COMPLETED") return {ok: true, state: "NO_ACTIVE_TARGET_TRANSFER"};
    pending.userInterruption = true;
    pending.state = "USER_INTERRUPTION";
    pending.autosendAllowed = false;
    pending.pendingAtomicActionId = "";
    pending.retryMetadata = {reason: "EXPLICIT_USER_INTERRUPTION", at: new Date().toISOString()};
    pending = await persistPendingTransfer(pending);
    return {ok: true, state: "USER_INTERRUPTION_NON_RESUME", transferId: pending.transferId, clientEpoch: pending.clientEpoch};
  }

  if (request.type === "CHATBRIDGE_DELIVERY_STATUS") {
    const pending = await loadPendingTransfer();
    const verified = (await chrome.storage.local.get(LAST_VERIFIED_TRANSFER_KEY))[LAST_VERIFIED_TRANSFER_KEY] || null;
    return {
      ok: true,
      pending: pending ? {
        transferId: pending.transferId,
        clientEpoch: pending.clientEpoch,
        state: pending.state,
        deliveryProofTier: pending.deliveryProofTier || DELIVERY_D0,
        humanReadInferred: false
      } : null,
      lastVerified: verified
    };
  }

  return {ok: false, error: "UNKNOWN_REQUEST"};
}

function validatePacket(packet) {
  if (!packet || packet.schema !== core.PACKET_SCHEMA || !packet.conversationKey || !packet.namespaceKey || !Array.isArray(packet.observations)) {
    throw new Error("INVALID_CAPTURE_PACKET");
  }
}
