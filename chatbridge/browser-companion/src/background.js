"use strict";

const DEFAULTS = Object.freeze({
  autoSend: true,
  maxCapsuleChars: 60000,
  tokenThreshold: 65000,
  messageThreshold: 80
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

async function handleMessage(request, sender) {
  if (!request || typeof request.type !== "string") return {ok: false, error: "INVALID_REQUEST"};

  if (request.type === "CHATBRIDGE_SETTINGS") {
    const stored = await chrome.storage.local.get("chatbridgeSettings");
    return {ok: true, settings: Object.assign({}, DEFAULTS, stored.chatbridgeSettings || {})};
  }

  if (request.type === "CHATBRIDGE_CHECKPOINT") {
    validateCapsule(request.capsule);
    await chrome.storage.session.set({latestChatBridgeCapsule: request.capsule});
    await chrome.storage.local.set({latestChatBridgeSummary: {
      capsuleId: request.capsule.capsuleId,
      capturedAt: request.capsule.capturedAt,
      source: request.capsule.source,
      metrics: request.capsule.metrics
    }});
    return {ok: true, capsuleId: request.capsule.capsuleId};
  }

  if (request.type === "CHATBRIDGE_OPEN") {
    validateCapsule(request.capsule);
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

  return {ok: false, error: "UNKNOWN_REQUEST"};
}

function validateCapsule(capsule) {
  if (!capsule || capsule.schema !== "CHATBRIDGE-HANDOFF-CAPSULE-1" || !capsule.capsuleId) {
    throw new Error("INVALID_CAPSULE");
  }
}
