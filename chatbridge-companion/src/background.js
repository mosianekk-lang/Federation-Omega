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

chrome.runtime.onInstalled.addListener(async () => {
  const current = await chrome.storage.local.get("chatbridgeSettings");
  if (!current.chatbridgeSettings) await chrome.storage.local.set({chatbridgeSettings: DEFAULTS});
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  handleMessage(request, sender).then(sendResponse).catch((error) => {
    sendResponse({ok: false, error: String(error && error.message || error)});
  });
  return true;
});

function ledgerStorageKey(conversationKey) {
  return `chatbridgeLedger:${String(conversationKey)}`;
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
    return edgeEgress ? edgeEgress.flushLedger(ledger, {reason: "STATUS_OR_CATCHUP"}) : {ok: false, state: "EDGE_EGRESS_MODULE_MISSING"};
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
    const stored = await chrome.storage.local.get("chatbridgeSettings");
    const settings = Object.assign({}, DEFAULTS, stored.chatbridgeSettings || {});
    const prompts = core.buildReplayPrompts(ledger, settings.maxReplayChars);
    const pending = {
      transferId: `CBT-${Date.now()}-${ledger.conversationKey}`,
      conversationKey: ledger.conversationKey,
      targetUrl: ledger.source.successorUrl,
      prompts,
      currentIndex: 0,
      targetTabId: null,
      createdAt: new Date().toISOString()
    };
    await chrome.storage.session.set({pendingChatBridgeTransfer: pending});
    const tab = await chrome.tabs.create({url: pending.targetUrl, active: true});
    pending.targetTabId = tab.id;
    await chrome.storage.session.set({pendingChatBridgeTransfer: pending});
    return {ok: true, transferId: pending.transferId, tabId: tab.id, packetCount: prompts.length};
  }

  if (request.type === "CHATBRIDGE_GET_PENDING") {
    const stored = await chrome.storage.session.get("pendingChatBridgeTransfer");
    const pending = stored.pendingChatBridgeTransfer;
    if (!pending || pending.targetTabId !== sender.tab?.id) return {ok: true, pending: null};
    const prompt = pending.prompts[pending.currentIndex] || null;
    return {ok: true, pending: prompt ? {
      transferId: pending.transferId,
      conversationKey: pending.conversationKey,
      packetIndex: pending.currentIndex + 1,
      packetCount: pending.prompts.length,
      prompt
    } : null};
  }

  if (request.type === "CHATBRIDGE_PACKET_CONSUMED") {
    const stored = await chrome.storage.session.get("pendingChatBridgeTransfer");
    const pending = stored.pendingChatBridgeTransfer;
    if (!pending || pending.transferId !== request.transferId || pending.targetTabId !== sender.tab?.id) {
      return {ok: false, error: "TRANSFER_BINDING_MISMATCH"};
    }
    pending.currentIndex += 1;
    if (pending.currentIndex >= pending.prompts.length) {
      await chrome.storage.session.remove("pendingChatBridgeTransfer");
      return {ok: true, complete: true};
    }
    await chrome.storage.session.set({pendingChatBridgeTransfer: pending});
    return {ok: true, complete: false, nextPacketIndex: pending.currentIndex + 1};
  }

  return {ok: false, error: "UNKNOWN_REQUEST"};
}

function validatePacket(packet) {
  if (!packet || packet.schema !== core.PACKET_SCHEMA || !packet.conversationKey || !packet.namespaceKey || !Array.isArray(packet.observations)) {
    throw new Error("INVALID_CAPTURE_PACKET");
  }
}