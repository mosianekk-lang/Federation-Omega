"use strict";
const defaults = {
  autoSend: true,
  autoUpload: false,
  connectorUrl: "",
  namespaceKey: "",
  sensitivity: "GOVERNED_LOCAL",
  sourceCompleteClaim: false,
  maxCapsuleChars: 60000,
  tokenThreshold: 65000,
  messageThreshold: 80
};

async function load() {
  const [local, session] = await Promise.all([
    chrome.storage.local.get("chatbridgeSettings"),
    chrome.storage.session.get("chatbridgeConnectorToken")
  ]);
  const settings = Object.assign({}, defaults, local.chatbridgeSettings || {});
  for (const [key, value] of Object.entries(settings)) {
    const input = document.getElementById(key);
    if (!input) continue;
    if (input.type === "checkbox") input.checked = Boolean(value); else input.value = value;
  }
  document.getElementById("connectorToken").value = session.chatbridgeConnectorToken || "";
}

async function requestConnectorPermission(connectorUrl) {
  if (!connectorUrl) return true;
  const url = new URL(connectorUrl);
  const origin = `${url.protocol}//${url.host}/*`;
  return chrome.permissions.request({origins: [origin]});
}

document.getElementById("settings").addEventListener("submit", async (event) => {
  event.preventDefault();
  const connectorUrl = document.getElementById("connectorUrl").value.trim().replace(/\/$/, "");
  const autoUpload = document.getElementById("autoUpload").checked;
  if (autoUpload && !(await requestConnectorPermission(connectorUrl))) {
    document.getElementById("status").textContent = "Connector origin permission was not granted";
    return;
  }
  const settings = {
    autoSend: document.getElementById("autoSend").checked,
    autoUpload,
    connectorUrl,
    namespaceKey: document.getElementById("namespaceKey").value.trim().toLowerCase(),
    sensitivity: document.getElementById("sensitivity").value.trim() || "GOVERNED_LOCAL",
    sourceCompleteClaim: document.getElementById("sourceCompleteClaim").checked,
    maxCapsuleChars: Number(document.getElementById("maxCapsuleChars").value),
    tokenThreshold: Number(document.getElementById("tokenThreshold").value),
    messageThreshold: Number(document.getElementById("messageThreshold").value)
  };
  await Promise.all([
    chrome.storage.local.set({chatbridgeSettings: settings}),
    chrome.storage.session.set({chatbridgeConnectorToken: document.getElementById("connectorToken").value})
  ]);
  document.getElementById("status").textContent = "Saved";
});
load();
