const DEFAULT_RUNTIME = "http://127.0.0.1:8762";
const HEARTBEAT_ALARM = "sol62-carrier-heartbeat";
const OUTBOX_KEY = "pendingCarrierEvents";
const OUTBOX_LIMIT = 64;

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

async function deliverCarrierEvent(event) {
  if (event.missionId) {
    return api("/v1/missions/" + encodeURIComponent(event.missionId) + "/carrier/failover", {
      method: "POST",
      body: JSON.stringify({
        failed_carrier_id: event.carrierId,
        failure_code: event.code,
        event_id: event.eventId,
      }),
    });
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
        "IDEMPOTENT_REPLAY"
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
  chrome.alarms.create(HEARTBEAT_ALARM, { periodInMinutes: 0.5 });
  try { await registerIfConfigured(); } catch (_) {}
});

chrome.runtime.onStartup.addListener(async () => {
  chrome.alarms.create(HEARTBEAT_ALARM, { periodInMinutes: 0.5 });
  try { await registerIfConfigured(); } catch (_) {}
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === HEARTBEAT_ALARM) heartbeat();
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.source !== "SOL62_CHATGPT_OBSERVER") return;
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
});
