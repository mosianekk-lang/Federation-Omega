const ENDPOINT = "http://127.0.0.1:8770/v1/events";

async function settings() {
  return await chrome.storage.local.get({enabled: false, pairingToken: "", pending: []});
}

async function postEvents(events) {
  const state = await settings();
  if (!state.enabled || !state.pairingToken || !events.length) return {queued: events.length};
  try {
    const response = await fetch(ENDPOINT, {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-Live-Bible-Token": state.pairingToken},
      body: JSON.stringify(events)
    });
    if (!response.ok) throw new Error(`receiver ${response.status}`);
    const pending = state.pending || [];
    if (pending.length) {
      await chrome.storage.local.set({pending: []});
      await postEvents(pending);
    }
    return await response.json();
  } catch (error) {
    const pending = [...(state.pending || []), ...events].slice(-2000);
    await chrome.storage.local.set({pending, lastError: String(error), lastErrorAt: new Date().toISOString()});
    return {queued: events.length, error: String(error)};
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "LIVE_BIBLE_EVENTS") {
    postEvents(message.events || []).then(sendResponse);
    return true;
  }
  if (message?.type === "LIVE_BIBLE_FLUSH") {
    settings().then(state => postEvents(state.pending || [])).then(sendResponse);
    return true;
  }
  return false;
});
