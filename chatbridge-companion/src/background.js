"use strict";

importScripts("bridge-core.js");

const core = globalThis.ChatBridgeCore;
const DEFAULTS = Object.freeze({
  autoSend: true,
  autoUpload: false,
  connectorUrl: "",
  namespaceKey: "",
  sensitivity: "GOVERNED_LOCAL",
  sourceCompleteClaim: false,
  maxCapsuleChars: 60000,
  tokenThreshold: 65000,
  messageThreshold: 80
});
const DATABASE_NAME = "chatbridge-companion-ffcl";
const DATABASE_VERSION = 1;
const CAPTURE_STORE = "captures";

chrome.runtime.onInstalled.addListener(async () => {
  const current = await chrome.storage.local.get(["chatbridgeSettings", "chatbridgeInstallationId"]);
  if (!current.chatbridgeSettings) await chrome.storage.local.set({chatbridgeSettings: DEFAULTS});
  if (!current.chatbridgeInstallationId) {
    await chrome.storage.local.set({chatbridgeInstallationId: crypto.randomUUID()});
  }
  await openDatabase();
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  handleMessage(request, sender).then(sendResponse).catch((error) => {
    sendResponse({ok: false, error: safeError(error)});
  });
  return true;
});

async function runtimeSettings() {
  const [local, session, managed] = await Promise.all([
    chrome.storage.local.get(["chatbridgeSettings", "chatbridgeInstallationId"]),
    chrome.storage.session.get("chatbridgeConnectorToken"),
    chrome.storage.managed ? chrome.storage.managed.get(["connectorUrl", "connectorToken", "namespaceKey"]).catch(() => ({})) : Promise.resolve({})
  ]);
  const settings = Object.assign({}, DEFAULTS, local.chatbridgeSettings || {}, {
    connectorUrl: managed.connectorUrl || (local.chatbridgeSettings && local.chatbridgeSettings.connectorUrl) || "",
    namespaceKey: managed.namespaceKey || (local.chatbridgeSettings && local.chatbridgeSettings.namespaceKey) || ""
  });
  return {
    settings,
    installationId: local.chatbridgeInstallationId || "",
    connectorToken: managed.connectorToken || session.chatbridgeConnectorToken || ""
  };
}

async function handleMessage(request, sender) {
  if (!request || typeof request.type !== "string") return {ok: false, error: "INVALID_REQUEST"};

  if (request.type === "CHATBRIDGE_SETTINGS") {
    const runtime = await runtimeSettings();
    return {
      ok: true,
      settings: runtime.settings,
      installationId: runtime.installationId,
      connectorTokenPresent: Boolean(runtime.connectorToken)
    };
  }

  if (request.type === "CHATBRIDGE_CAPTURE_ENVELOPE") {
    core.validateCaptureEnvelope(request.envelope);
    return captureEnvelope(request.envelope, request.reason || "UNSPECIFIED");
  }

  if (request.type === "CHATBRIDGE_CHECKPOINT") {
    core.validateCapsule(request.capsule);
    await chrome.storage.session.set({latestChatBridgeCapsule: request.capsule});
    await chrome.storage.local.set({latestChatBridgeSummary: {
      capsuleId: request.capsule.capsuleId,
      capturedAt: request.capsule.capturedAt,
      source: request.capsule.source,
      metrics: request.capsule.metrics,
      continuity: {
        snapshotSha256: request.capsule.continuity && request.capsule.continuity.snapshotSha256 || "",
        captureReceipt: request.capsule.continuity && request.capsule.continuity.captureReceipt || {}
      }
    }});
    return {ok: true, capsuleId: request.capsule.capsuleId};
  }

  if (request.type === "CHATBRIDGE_OPEN") {
    core.validateCapsule(request.capsule);
    const prompt = String(request.prompt || "");
    if (!prompt || prompt.length > 250000) throw new Error("INVALID_RESTORE_PROMPT");
    const targetUrl = String(request.targetUrl || "https://chatgpt.com/");
    const pending = {
      transferId: request.capsule.capsuleId,
      capsule: request.capsule,
      prompt,
      targetUrl,
      targetTabId: null,
      createdAt: new Date().toISOString(),
      consumed: false
    };
    await chrome.storage.session.set({pendingChatBridgeTransfer: pending});
    const tab = await chrome.tabs.create({url: targetUrl, active: true});
    pending.targetTabId = tab.id;
    await chrome.storage.session.set({pendingChatBridgeTransfer: pending});
    return {ok: true, transferId: pending.transferId, tabId: tab.id};
  }

  if (request.type === "CHATBRIDGE_GET_PENDING") {
    const stored = await chrome.storage.session.get("pendingChatBridgeTransfer");
    const pending = stored.pendingChatBridgeTransfer;
    if (!pending || pending.consumed || pending.targetTabId !== sender.tab?.id) return {ok: true, pending: null};
    return {ok: true, pending};
  }

  if (request.type === "CHATBRIDGE_CONSUMED") {
    const stored = await chrome.storage.session.get("pendingChatBridgeTransfer");
    const pending = stored.pendingChatBridgeTransfer;
    if (!pending || pending.transferId !== request.transferId || pending.targetTabId !== sender.tab?.id) {
      return {ok: false, error: "TRANSFER_BINDING_MISMATCH"};
    }
    await chrome.storage.session.remove("pendingChatBridgeTransfer");
    return {ok: true};
  }

  if (request.type === "CHATBRIDGE_STATUS") {
    const stored = await chrome.storage.local.get([
      "latestChatBridgeSummary",
      "latestChatBridgeCaptureReceipt",
      "chatbridgeCaptureStates"
    ]);
    return {ok: true, status: stored};
  }

  return {ok: false, error: "UNKNOWN_REQUEST"};
}

async function captureEnvelope(envelope, reason) {
  const runtime = await runtimeSettings();
  const conversationKey = envelope.source.conversation_key;
  const stateStore = await chrome.storage.local.get("chatbridgeCaptureStates");
  const states = stateStore.chatbridgeCaptureStates || {};
  const previousState = states[conversationKey] || null;
  const deltaEnvelope = core.diffCaptureEnvelope(previousState, envelope);
  const recordSha256 = await core.sha256(deltaEnvelope);
  const captureRecord = {
    captureId: deltaEnvelope.capture_id,
    conversationKey,
    namespaceKey: deltaEnvelope.namespace_key,
    pathId: deltaEnvelope.capture_path.path_id,
    capturedAt: deltaEnvelope.captured_at,
    reason,
    recordSha256,
    deltaEnvelope,
    providerReceipt: null,
    providerState: "NOT_ATTEMPTED"
  };

  const hasMaterialDelta = Boolean(
    (deltaEnvelope.observations || []).length ||
    (deltaEnvelope.delta && deltaEnvelope.delta.removed_from_rendered_dom_count)
  );
  if (hasMaterialDelta || envelope.snapshot.terminal_observed) {
    await putCapture(captureRecord);
  }

  states[conversationKey] = core.snapshotState(envelope);
  await chrome.storage.local.set({chatbridgeCaptureStates: states});

  let upload = {state: "LOCAL_DURABLE_CAPTURED", providerReceipt: null};
  if (runtime.settings.autoUpload && hasMaterialDelta) {
    upload = await uploadCapture(deltaEnvelope, runtime.settings.connectorUrl, runtime.connectorToken);
    captureRecord.providerState = upload.state;
    captureRecord.providerReceipt = upload.providerReceipt;
    await putCapture(captureRecord);
  }

  const receipt = {
    schema: "CHATBRIDGE-COMPANION-CAPTURE-RECEIPT-1",
    state: upload.state,
    captureId: deltaEnvelope.capture_id,
    conversationKey,
    namespaceKey: deltaEnvelope.namespace_key,
    pathId: deltaEnvelope.capture_path.path_id,
    snapshotSha256: envelope.snapshot.sha256,
    recordSha256,
    addedCount: deltaEnvelope.delta.added_count,
    correctionCount: deltaEnvelope.delta.correction_count,
    removedFromRenderedDomCount: deltaEnvelope.delta.removed_from_rendered_dom_count,
    materialDelta: hasMaterialDelta,
    locallyDurable: hasMaterialDelta || envelope.snapshot.terminal_observed,
    providerReceipt: upload.providerReceipt,
    providerReadbackVerified: upload.state === "PROVIDER_CAPTURE_ACKNOWLEDGED",
    exactSourceCompletenessClaimed: envelope.snapshot.exact_source_completeness_claimed,
    truthBoundary: envelope.truth_boundary,
    capturedAt: envelope.captured_at
  };
  await chrome.storage.local.set({latestChatBridgeCaptureReceipt: receipt});
  return {ok: true, receipt};
}

function validateConnectorUrl(value) {
  if (!value) throw new Error("CONNECTOR_URL_MISSING");
  const url = new URL(value);
  const local = ["localhost", "127.0.0.1", "::1"].includes(url.hostname);
  if (url.protocol !== "https:" && !(local && url.protocol === "http:")) {
    throw new Error("CONNECTOR_URL_REQUIRES_HTTPS_OR_LOCALHOST");
  }
  return url.toString().replace(/\/$/, "");
}

async function uploadCapture(deltaEnvelope, connectorUrl, connectorToken) {
  try {
    const base = validateConnectorUrl(connectorUrl);
    const headers = {"content-type": "application/json"};
    if (connectorToken) headers["x-chatbridge-token"] = connectorToken;
    const response = await fetch(`${base}/v1/chatbridge/alpha-omega/capture`, {
      method: "POST",
      headers,
      body: JSON.stringify(deltaEnvelope),
      cache: "no-store",
      credentials: "omit"
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(`CONNECTOR_HTTP_${response.status}`);
    if (!body || body.ok !== true || !body.receipt) throw new Error("CONNECTOR_RECEIPT_MISSING");
    return {state: "PROVIDER_CAPTURE_ACKNOWLEDGED", providerReceipt: body.receipt};
  } catch (error) {
    return {
      state: "PROVIDER_UPLOAD_FAILED_LOCAL_DURABLE",
      providerReceipt: {error: safeError(error), retryable: true}
    };
  }
}

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(CAPTURE_STORE)) {
        const store = database.createObjectStore(CAPTURE_STORE, {keyPath: "captureId"});
        store.createIndex("conversationKey", "conversationKey", {unique: false});
        store.createIndex("capturedAt", "capturedAt", {unique: false});
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("INDEXEDDB_OPEN_FAILED"));
  });
}

async function putCapture(record) {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(CAPTURE_STORE, "readwrite");
    transaction.objectStore(CAPTURE_STORE).put(record);
    transaction.oncomplete = () => {
      database.close();
      resolve(record.captureId);
    };
    transaction.onerror = () => {
      database.close();
      reject(transaction.error || new Error("INDEXEDDB_WRITE_FAILED"));
    };
  });
}

function safeError(error) {
  const message = String(error && error.message || error || "UNKNOWN_ERROR");
  return message.replace(/(x-chatbridge-token|authorization|bearer)\s*[:=]?\s*[^\s,;]+/ig, "$1:[REDACTED]").slice(0, 500);
}
