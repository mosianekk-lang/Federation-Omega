const DEFAULT_RUNTIME = "http://127.0.0.1:8762";
const HEARTBEAT_ALARM = "sol62-carrier-heartbeat";
const CONTROL_POLL_ALARM = "sol62-browser-control-poll";
const OUTBOX_KEY = "pendingCarrierEvents";
const OUTBOX_LIMIT = 64;
const HYDRATION_KEY = "pendingMissionHydration";
const NEW_CHAT_MENU_ID = "sol62-open-new-chat-tab";
const NEW_CHAT_CONTEXT_KEY = "sol62NewChatContext";
const NEW_CHAT_OPEN_KEY = "sol62NewChatOpen";
const NEW_CHAT_CONTEXT_TTL_MS = 8000;
const NEW_CHAT_DEDUP_MS = 1200;

// Do not turn a relay failure into a mission-state assertion.

function safeChatGptNewChatUrl(candidate) {
  try {
    const url = new URL(candidate || "https://chatgpt.com/");
    if (url.protocol !== "https:" || url.hostname !== "chatgpt.com") {
      return "https://chatgpt.com/";
    }
    if (/^\\/(?:c|share)\\//.test(url.pathname)) {
      return url.origin + "/";
    }
    return url.href;
  } catch (_) {
    return "https://chatgpt.com/";
  }
}

function ensureNewChatContextMenu() {
  chrome.contextMenus.remove(NEW_CHAT_MENU_ID, () => {
    void chrome.runtime.lastError;
    chrome.contextMenus.create({
      id: NEW_CHAT_MENU_ID,
      title: "FUSE — Open New Chat in New Tab",
      contexts: ["all"],
      documentUrlPatterns: ["https://chatgpt.com/*"]
    }, () => void chrome.runtime.lastError);
  });
}

async function rememberNewChatContext(tabId, message) {
  if (typeof tabId !== "number") return;
  const row = await chrome.storage.session.get({ [NEW_CHAT_CONTEXT_KEY]: {} });
  const all = row[NEW_CHAT_CONTEXT_KEY] || {};
  all[String(tabId)] = {
    observedAt: Number(message.observedAt || Date.now()),
    ttlMs: Math.min(Number(message.ttlMs || NEW_CHAT_CONTEXT_TTL_MS), NEW_CHAT_CONTEXT_TTL_MS),
    isNewChat: message.isNewChat === true,
    confidence: Number(message.confidence || 0),
    reasons: Array.isArray(message.reasons) ? message.reasons.slice(0, 8) : [],
    url: safeChatGptNewChatUrl(message.url),
    nativeLink: message.nativeLink === true
  };
  await chrome.storage.session.set({ [NEW_CHAT_CONTEXT_KEY]: all });
}

async function recentNewChatContext(tabId) {
  if (typeof tabId !== "number") return null;
  const row = await chrome.storage.session.get({ [NEW_CHAT_CONTEXT_KEY]: {} });
  const all = row[NEW_CHAT_CONTEXT_KEY] || {};
  const item = all[String(tabId)] || null;
  if (!item) return null;
  const age = Date.now() - Number(item.observedAt || 0);
  if (age < 0 || age > Number(item.ttlMs || NEW_CHAT_CONTEXT_TTL_MS)) return null;
  return item;
}

async function openNewChatTab(candidateUrl, active = true) {
  const url = safeChatGptNewChatUrl(candidateUrl);
  const now = Date.now();
  const row = await chrome.storage.session.get({ [NEW_CHAT_OPEN_KEY]: null });
  const prior = row[NEW_CHAT_OPEN_KEY];
  if (prior && prior.url === url && now - Number(prior.openedAt || 0) < NEW_CHAT_DEDUP_MS) {
    return { ok: true, deduplicated: true, url };
  }
  await chrome.storage.session.set({
    [NEW_CHAT_OPEN_KEY]: { url, openedAt: now }
  });
  const tab = await chrome.tabs.create({ url, active });
  return { ok: true, deduplicated: false, url, tabId: tab && tab.id };
}


function safeChatGptTab(tab) {
  if (!tab || typeof tab.id !== "number") return null;
  try {
    const url = new URL(tab.url || tab.pendingUrl || "https://chatgpt.com/");
    if (url.protocol !== "https:" || url.hostname !== "chatgpt.com") return null;
    return {
      tab_id: tab.id,
      window_id: tab.windowId,
      active: tab.active === true,
      pinned: tab.pinned === true,
      status: tab.status || "",
      url: url.href
    };
  } catch (_) {
    return null;
  }
}

async function chatGptTabs() {
  const tabs = await chrome.tabs.query({});
  return tabs.map(safeChatGptTab).filter(Boolean);
}

async function resolveCommandTab(args = {}) {
  if (Number.isInteger(args.tab_id)) {
    const tab = await chrome.tabs.get(args.tab_id);
    const safe = safeChatGptTab(tab);
    if (!safe) throw new Error("CHATGPT_TAB_REQUIRED");
    return safe;
  }
  const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  const active = tabs.map(safeChatGptTab).find(Boolean);
  if (active) return active;
  const all = await chatGptTabs();
  if (!all.length) throw new Error("NO_CHATGPT_TAB");
  return all[0];
}

async function sendSemanticCommand(tabId, command) {
  return chrome.tabs.sendMessage(tabId, {
    source: "SOL62_BROWSER_CONTROL",
    type: "SOL62_EXECUTE_BROWSER_COMMAND",
    command
  });
}

async function executeBrowserCommand(command) {
  const operation = String(command.operation || "").toUpperCase();
  const args = command.args || {};
  const websiteState = command.effect_class === "WEBSITE_STATE";
  if (websiteState && command.authority_bound !== true) {
    throw new Error("WEBSITE_STATE_AUTHORITY_NOT_BOUND");
  }

  if (operation === "LIST_TABS") {
    const tabs = await chatGptTabs();
    return { tabs, count: tabs.length };
  }
  if (operation === "READ_ACTIVE_TAB") {
    const tab = await resolveCommandTab(args);
    return { tab };
  }
  if (operation === "CREATE_TAB" || operation === "OPEN_NEW_CHAT") {
    const result = await openNewChatTab(args.url || "https://chatgpt.com/", args.active !== false);
    return { ...result, operation, action_observed: true };
  }
  if (operation === "ACTIVATE_TAB") {
    const tab = await resolveCommandTab(args);
    const updated = await chrome.tabs.update(tab.tab_id, { active: true });
    if (updated && Number.isInteger(updated.windowId)) {
      try { await chrome.windows.update(updated.windowId, { focused: true }); } catch (_) {}
    }
    return { tab: safeChatGptTab(updated), active: true, action_observed: true };
  }
  if (operation === "CLOSE_TAB") {
    const tab = await resolveCommandTab(args);
    await chrome.tabs.remove(tab.tab_id);
    return { tab_id: tab.tab_id, closed: true, action_observed: true };
  }
  if (operation === "RELOAD_TAB") {
    const tab = await resolveCommandTab(args);
    await chrome.tabs.reload(tab.tab_id);
    return { tab_id: tab.tab_id, reload_requested: true, action_observed: true };
  }
  if (operation === "GO_BACK") {
    const tab = await resolveCommandTab(args);
    await chrome.tabs.goBack(tab.tab_id);
    return { tab_id: tab.tab_id, history_action: "BACK", action_observed: true };
  }
  if (operation === "GO_FORWARD") {
    const tab = await resolveCommandTab(args);
    await chrome.tabs.goForward(tab.tab_id);
    return { tab_id: tab.tab_id, history_action: "FORWARD", action_observed: true };
  }
  if (operation === "NAVIGATE_CHATGPT") {
    const tab = await resolveCommandTab(args);
    const url = safeChatGptNewChatUrl(args.url || "https://chatgpt.com/");
    const updated = await chrome.tabs.update(tab.tab_id, { url });
    return { tab: safeChatGptTab(updated), navigated: true, url, action_observed: true };
  }

  if (
    operation === "SEMANTIC_SNAPSHOT"
    || operation === "FOCUS_ELEMENT"
    || operation === "SCROLL_ELEMENT"
    || operation === "CLICK_ELEMENT"
    || operation === "FILL_ELEMENT"
  ) {
    const tab = await resolveCommandTab(args);
    const result = await sendSemanticCommand(tab.tab_id, command);
    return {
      tab_id: tab.tab_id,
      semantic: result || {},
      action_observed: Boolean(result && result.action_observed === true)
    };
  }

  throw new Error("UNSUPPORTED_BROWSER_OPERATION");
}

async function authorizeBrowserCommand(command) {
  if (command.effect_class !== "WEBSITE_STATE") return command;
  const state = await getState();
  if (!state.carrierId) throw new Error("NO_BROWSER_CARRIER");
  const envelope = await api(
    "/v1/browser/commands/"
      + encodeURIComponent(state.carrierId)
      + "/"
      + encodeURIComponent(command.command_id)
      + "/authorize",
    { method: "POST", body: "{}" }
  );
  const row = envelope && envelope.value ? envelope.value : envelope;
  if (!row || row.authority_bound !== true) {
    throw new Error("WEBSITE_STATE_AUTHORITY_NOT_BOUND");
  }
  return row;
}

async function acknowledgeBrowserCommand(command, status, readback = {}, errorCode = "") {
  const state = await getState();
  if (!state.carrierId) return null;
  return api(
    "/v1/browser/commands/"
      + encodeURIComponent(state.carrierId)
      + "/"
      + encodeURIComponent(command.command_id)
      + "/ack",
    {
      method: "POST",
      body: JSON.stringify({
        status,
        readback,
        error_code: errorCode
      })
    }
  );
}

let browserCommandPollInFlight = false;

async function pullAndExecuteBrowserCommand() {
  if (browserCommandPollInFlight) return { skipped: true, reason: "POLL_IN_FLIGHT" };
  browserCommandPollInFlight = true;
  try {
    const state = await getState();
    if (!state.enabled || !state.carrierId || !state.fuseAccessToken) {
      return { skipped: true, reason: "CONTROL_NOT_CONFIGURED" };
    }
    const envelope = await api(
      "/v1/browser/commands/" + encodeURIComponent(state.carrierId) + "/next"
    );
    const command = envelope && envelope.command ? envelope.command : null;
    if (!command) return { command: null };
    try {
      const authorizedCommand = await authorizeBrowserCommand(command);
      const readback = await executeBrowserCommand(authorizedCommand);
      await acknowledgeBrowserCommand(command, "VERIFIED", readback, "");
      return { command_id: command.command_id, status: "VERIFIED", readback };
    } catch (error) {
      const code = String((error && error.message) || "BROWSER_COMMAND_FAILED").slice(0, 128);
      try { await acknowledgeBrowserCommand(command, "FAILED", {}, code); } catch (_) {}
      return { command_id: command.command_id, status: "FAILED", error_code: code };
    }
  } catch (_) {
    return { skipped: true, reason: "RUNTIME_UNREACHABLE" };
  } finally {
    browserCommandPollInFlight = false;
  }
}

async function getState() {
  const local = await chrome.storage.local.get({
    runtimeBase: DEFAULT_RUNTIME,
    carrierId: "",
    sessionId: "",
    missionId: "",
    enabled: true,
    [OUTBOX_KEY]: [],
  });
  const session = await chrome.storage.session.get({ fuseAccessToken: "" });
  return { ...local, ...session };
}

function newEventId(carrierId, code) {
  const suffix = (globalThis.crypto && crypto.randomUUID)
    ? crypto.randomUUID()
    : String(Date.now()) + "-" + Math.random().toString(16).slice(2);
  return "sol62-browser:" + carrierId + ":" + code + ":" + suffix;
}

async function api(path, options = {}) {
  const state = await getState();
  if (!state.enabled || !state.fuseAccessToken) throw new Error("NO_FUSE_SESSION");
  const response = await fetch(state.runtimeBase.replace(/\/$/, "") + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + state.fuseAccessToken,
      ...(options.headers || {}),
    },
  });
  const text = await response.text();
  let body;
  try { body = text ? JSON.parse(text) : {}; } catch { body = { raw: text }; }
  if (!response.ok) throw new Error("SOL62_HTTP_" + response.status);
  return body;
}

async function readOutbox() {
  const row = await chrome.storage.local.get({ [OUTBOX_KEY]: [] });
  return Array.isArray(row[OUTBOX_KEY]) ? row[OUTBOX_KEY] : [];
}

async function writeOutbox(events) {
  await chrome.storage.local.set({ [OUTBOX_KEY]: events.slice(-OUTBOX_LIMIT) });
}

async function enqueueCarrierEvent(event) {
  const events = await readOutbox();
  if (!events.some((row) => row.eventId === event.eventId)) {
    events.push(event);
    await writeOutbox(events);
  }
}

function hydrationReceipt(event, result) {
  const hydration = result && result.hydration ? result.hydration : null;
  const resume = hydration && hydration.resume_packet
    ? hydration.resume_packet
    : (result && result.resume_packet ? result.resume_packet : null);
  if (!resume) return null;
  return {
    schema: "SOL62_BROWSER_HYDRATION_RECEIPT_V1",
    eventId: event.eventId,
    missionId: event.missionId || resume.mission_id || "",
    failedCarrierId: event.carrierId,
    replacementCarrierId: (result && result.replacement_carrier_id) || "",
    failoverState: (result && result.state) || "",
    hydrationPacketSha256: hydration ? (hydration.packet_sha256 || "") : "",
    durabilityCheckpointKey: resume.durability_checkpoint_key || "",
    durabilityCheckpointSha256: resume.durability_checkpoint_sha256 || "",
    eventHistoryHead: resume.event_history_head || "",
    replayGuardVerified: resume.replay_guard_verified === true,
    replayGuardHistorySha256: resume.replay_guard_history_sha256 || "",
    openInterruptionIds: Array.isArray(resume.open_interruption_ids) ? resume.open_interruption_ids : [],
    inflightEffectIds: Array.isArray(resume.inflight_effect_ids) ? resume.inflight_effect_ids : [],
    durableWakeStatus: result && result.durable_wake ? (result.durable_wake.status || "") : "",
    durableWakeTaskId: result && result.durable_wake && result.durable_wake.receipt
      ? (result.durable_wake.receipt.task_id || "")
      : "",
    ownerRetryRequired: result ? result.owner_retry_required === true : false,
    uiRetryRequired: result ? result.ui_retry_required === true : false,
    receivedAt: Date.now(),
    providerCredentialsIncluded: false,
    transcriptIncluded: false,
    acknowledged: false,
  };
}

async function persistHydration(event, result) {
  const receipt = hydrationReceipt(event, result);
  if (!receipt) return null;
  const prior = await chrome.storage.local.get({ [HYDRATION_KEY]: null });
  const existing = prior[HYDRATION_KEY];
  if (
    existing
    && existing.eventId === receipt.eventId
    && existing.durabilityCheckpointSha256 === receipt.durabilityCheckpointSha256
  ) {
    return existing;
  }
  await chrome.storage.local.set({ [HYDRATION_KEY]: receipt });
  return receipt;
}

async function readHydration() {
  const row = await chrome.storage.local.get({ [HYDRATION_KEY]: null });
  return row[HYDRATION_KEY] || null;
}

async function acknowledgeHydration(expectedCheckpointSha256) {
  const receipt = await readHydration();
  if (!receipt) return { ok: false, reason: "NO_PENDING_HYDRATION" };
  if (
    expectedCheckpointSha256
    && receipt.durabilityCheckpointSha256 !== expectedCheckpointSha256
  ) {
    return { ok: false, reason: "HYDRATION_CHECKPOINT_MISMATCH" };
  }
  const acknowledged = { ...receipt, acknowledged: true, acknowledgedAt: Date.now() };
  await chrome.storage.local.set({ [HYDRATION_KEY]: acknowledged });
  return { ok: true, receipt: acknowledged };
}

async function enqueueDurableWake(event, result) {
  if (!event.missionId || !result || result.replacement_carrier_id) return null;
  if (result.durable_continuation_required !== true) return null;
  const resume = result.resume_packet
    || (result.hydration && result.hydration.resume_packet)
    || null;
  if (!resume) return null;
  return api("/v1/missions/" + encodeURIComponent(event.missionId) + "/wake", {
    method: "POST",
    body: JSON.stringify({ inline: false }),
  });
}

async function deliverCarrierEvent(event) {
  let result;
  if (event.missionId) {
    result = await api("/v1/missions/" + encodeURIComponent(event.missionId) + "/carrier/failover", {
      method: "POST",
      body: JSON.stringify({
        failed_carrier_id: event.carrierId,
        failure_code: event.code,
        event_id: event.eventId,
      }),
    });
    const durableWake = await enqueueDurableWake(event, result);
    if (durableWake) result = { ...result, durable_wake: durableWake };
    await persistHydration(event, result);
    return result;
  }
  return api("/v1/carriers/" + encodeURIComponent(event.carrierId) + "/failure", {
    method: "POST",
    body: JSON.stringify({
      code: event.code,
      event_id: event.eventId,
    }),
  });
}

async function flushOutbox() {
  const events = await readOutbox();
  if (!events.length) return { delivered: 0, pending: 0 };

  const pending = [];
  let delivered = 0;
  for (const event of events) {
    try {
      await deliverCarrierEvent(event);
      delivered += 1;
    } catch (_) {
      pending.push(event);
    }
  }
  await writeOutbox(pending);
  return { delivered, pending: pending.length };
}

async function registerIfConfigured() {
  const state = await getState();
  if (!state.enabled || !state.carrierId || !state.sessionId) return;
  await api("/v1/carriers/register", {
    method: "POST",
    body: JSON.stringify({
      carrier_id: state.carrierId,
      session_id: state.sessionId,
      client_kind: "CHATGPT_BROWSER_COMPANION",
      route_id: "CHATGPT_BROWSER",
      priority: 50,
      capabilities: [
        "CHATGPT_UI_OBSERVATION",
        "CARRIER_HEARTBEAT",
        "FAILURE_RELAY",
        "DURABLE_LOCAL_OUTBOX",
        "IDEMPOTENT_REPLAY",
        "STREAM_CACHE_FAILURE_RECOVERY",
        "AUTO_DURABLE_MISSION_WAKE",
        "SEMANTIC_NEW_CHAT_TARGETING",
        "CONTEXT_MENU_NEW_CHAT_TAB",
        "MODIFIED_CLICK_NEW_CHAT_TAB",
        "TAB_QUERY",
        "TAB_CREATE",
        "TAB_ACTIVATE",
        "TAB_CLOSE",
        "TAB_RELOAD",
        "HISTORY_BACK_FORWARD",
        "SAFE_CHATGPT_NAVIGATION",
        "SEMANTIC_DOM_SNAPSHOT",
        "SEMANTIC_FOCUS_SCROLL",
        "SEMANTIC_CLICK_GATED",
        "SEMANTIC_FILL_GATED",
        "TYPED_BROWSER_COMMAND_QUEUE",
        "SEMANTIC_READBACK"
      ],
      failure_domain: "CHATGPT_BROWSER"
    }),
  });
  await flushOutbox();
}

async function heartbeat() {
  const state = await getState();
  if (!state.enabled || !state.carrierId) return;
  try {
    await api("/v1/carriers/" + encodeURIComponent(state.carrierId) + "/heartbeat", {
      method: "POST",
      body: JSON.stringify({ observed_state: "HEALTHY" }),
    });
    await flushOutbox();
  } catch (_) {
    // Runtime reachability failure is not proof that the owner mission failed.
  }
}

async function reportFailure(code) {
  const state = await getState();
  if (!state.enabled || !state.carrierId) return;

  const event = {
    schema: "SOL62_BROWSER_CARRIER_EVENT_V1",
    eventId: newEventId(state.carrierId, code),
    carrierId: state.carrierId,
    missionId: state.missionId || "",
    code,
    createdAt: Date.now(),
    providerCredentialsIncluded: false,
  };

  // Durably record before attempting transport so tab/runtime loss cannot erase it.
  await enqueueCarrierEvent(event);
  await flushOutbox();
}

chrome.runtime.onInstalled.addListener(async () => {
  ensureNewChatContextMenu();
  chrome.alarms.create(HEARTBEAT_ALARM, { periodInMinutes: 0.5 });
  chrome.alarms.create(CONTROL_POLL_ALARM, { periodInMinutes: 0.5 });
  try { await registerIfConfigured(); } catch (_) {}
});

chrome.runtime.onStartup.addListener(async () => {
  ensureNewChatContextMenu();
  chrome.alarms.create(HEARTBEAT_ALARM, { periodInMinutes: 0.5 });
  chrome.alarms.create(CONTROL_POLL_ALARM, { periodInMinutes: 0.5 });
  try { await registerIfConfigured(); } catch (_) {}
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === HEARTBEAT_ALARM) heartbeat();
  if (alarm.name === CONTROL_POLL_ALARM) pullAndExecuteBrowserCommand();
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== NEW_CHAT_MENU_ID) return;
  recentNewChatContext(tab && tab.id)
    .then((context) => openNewChatTab(
      context && context.isNewChat ? context.url : "https://chatgpt.com/",
      true
    ))
    .catch(() => {});
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.source !== "SOL62_CHATGPT_OBSERVER") return;
  if (message.type === "SOL62_NEW_CHAT_CONTEXT") {
    rememberNewChatContext(sender && sender.tab ? sender.tab.id : undefined, message)
      .then(() => sendResponse({ ok: true }))
      .catch(() => sendResponse({ ok: false }));
    return true;
  }
  if (message.type === "SOL62_OPEN_NEW_CHAT") {
    openNewChatTab(message.url, message.disposition !== "background_tab")
      .then((result) => sendResponse(result))
      .catch(() => sendResponse({ ok: false }));
    return true;
  }
  if (message.type === "CHATGPT_CARRIER_FAILURE") {
    reportFailure(message.code || "CHATGPT_UI_UNAVAILABLE")
      .then(() => sendResponse({ ok: true }))
      .catch(() => sendResponse({ ok: false }));
    return true;
  }
  if (message.type === "CHATGPT_CARRIER_HEALTHY") {
    heartbeat()
      .then(() => sendResponse({ ok: true }))
      .catch(() => sendResponse({ ok: false }));
    return true;
  }
  if (message.type === "SOL62_BROWSER_POLL") {
    pullAndExecuteBrowserCommand()
      .then((result) => sendResponse({ ok: true, result }))
      .catch(() => sendResponse({ ok: false }));
    return true;
  }
  if (message.type === "SOL62_GET_PENDING_HYDRATION") {
    readHydration()
      .then((receipt) => sendResponse({ ok: true, receipt }))
      .catch(() => sendResponse({ ok: false }));
    return true;
  }
  if (message.type === "SOL62_ACK_PENDING_HYDRATION") {
    acknowledgeHydration(message.durabilityCheckpointSha256 || "")
      .then((result) => sendResponse(result))
      .catch(() => sendResponse({ ok: false }));
    return true;
  }
});
