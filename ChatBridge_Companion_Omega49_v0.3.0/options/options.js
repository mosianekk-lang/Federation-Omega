"use strict";
const defaults = {autoSend: true, maxReplayChars: 28000, tokenThreshold: 65000, messageThreshold: 80, captureIntervalMs: 30000};
async function load() {
  const stored = await chrome.storage.local.get("chatbridgeSettings");
  const settings = Object.assign({}, defaults, stored.chatbridgeSettings || {});
  for (const [key, value] of Object.entries(settings)) {
    const input = document.getElementById(key);
    if (!input) continue;
    if (input.type === "checkbox") input.checked = Boolean(value); else input.value = value;
  }
}
document.getElementById("settings").addEventListener("submit", async (event) => {
  event.preventDefault();
  const settings = {
    autoSend: document.getElementById("autoSend").checked,
    maxReplayChars: Number(document.getElementById("maxReplayChars").value),
    tokenThreshold: Number(document.getElementById("tokenThreshold").value),
    messageThreshold: Number(document.getElementById("messageThreshold").value),
    captureIntervalMs: Number(document.getElementById("captureIntervalMs").value)
  };
  await chrome.storage.local.set({chatbridgeSettings: settings});
  document.getElementById("status").textContent = "Saved";
});
load();
