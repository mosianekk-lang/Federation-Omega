const DEFAULT_RUNTIME = "http://127.0.0.1:8762";
const HEARTBEAT_ALARM = "sol62-carrier-heartbeat";

async function getState() {
  const local = await chrome.storage.local.get({
    runtimeBase: DEFAULT_RUNTIME,
    carrierId: "",
    sessionId: "",
    missionId: "",
    enabled: true,
  });
  const session = await chrome.storage.session.get({ fuseAccessToken: "" });
  return { ...local, ...session };
}

async function api(path, options = {}) {
  const state = await getState();
  if (!state.enabled || !state.fuseAccessToken) return { skipped: "NO_FUSE_SESSION" };
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
      capabilities: ["CHATGPT_UI_OBSERVATION", "CARRIER_HEARTBEAT", "FAILURE_RELAY"],
      failure_domain: "CHATGPT_BROWSER"
    }),
  });
}

async function heartbeat() {
  const state = await getState();
  if (!state.enabled || !state.carrierId) return;
  try {
    await api("/v1/carriers/" + encodeURIComponent(state.carrierId) + "/heartbeat", {
      method: "POST",
      body: JSON.stringify({ observed_state: "HEALTHY" }),
    });
  } catch (_) {
    // Runtime reachability failure is not proof that the owner mission failed.
  }
}

async function reportFailure(code) {
  const state = await getState();
  if (!state.enabled || !state.carrierId) return;
  try {
    await api("/v1/carriers/" + encodeURIComponent(state.carrierId) + "/failure", {
      method: "POST",
      body: JSON.stringify({ code }),
    });
    if (state.missionId) {
      await api("/v1/missions/" + encodeURIComponent(state.missionId) + "/carrier/failover", {
        method: "POST",
        body: JSON.stringify({
          failed_carrier_id: state.carrierId,
          failure_code: code,
        }),
      });
    }
  } catch (_) {
    // Do not turn a relay failure into a mission-state assertion.
  }
}

chrome.runtime.onInstalled.addListener(async () => {
  chrome.alarms.create(HEARTBEAT_ALARM, { periodInMinutes: 0.25 });
  await registerIfConfigured();
});

chrome.runtime.onStartup.addListener(async () => {
  chrome.alarms.create(HEARTBEAT_ALARM, { periodInMinutes: 0.25 });
  await registerIfConfigured();
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
