const enabled = document.getElementById("enabled");
const token = document.getElementById("token");
const status = document.getElementById("status");

chrome.storage.local.get({enabled:false,pairingToken:"",pending:[],lastError:""}, state => {
  enabled.checked = state.enabled;
  token.value = state.pairingToken;
  status.textContent = `Queued: ${state.pending.length}${state.lastError ? `\nLast error: ${state.lastError}` : ""}`;
});

document.getElementById("save").onclick = () => {
  chrome.storage.local.set({enabled:enabled.checked,pairingToken:token.value.trim()}, () => {
    status.textContent = "Saved. Capture is local and opt-in.";
  });
};

document.getElementById("flush").onclick = () => {
  chrome.runtime.sendMessage({type:"LIVE_BIBLE_FLUSH"}, result => {
    status.textContent = JSON.stringify(result || {}, null, 2);
  });
};
