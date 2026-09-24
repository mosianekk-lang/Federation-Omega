(() => {
  const FAILURE_MARKERS = [
    ["Stream cache expired", "STREAM_CACHE_EXPIRED"],
    ["Connection interrupted. Waiting for the complete answer", "CHATGPT_STREAM_INTERRUPTED"],
    ["You've hit max weighted tokens for this chat", "CONTEXT_LIMIT"],
    ["You’ve hit max weighted tokens for this chat", "CONTEXT_LIMIT"],
    ["Could not load this ChatGPT conversation", "CHATGPT_CONVERSATION_LOAD_FAILED"],
    ["Unable to load conversation", "CHATGPT_CONVERSATION_LOAD_FAILED"],
    ["Something went wrong", "CHATGPT_UI_UNAVAILABLE"]
  ];

  let lastFailure = "";
  let lastHealthySignal = 0;

  function bodyText() {
    return document.body ? (document.body.innerText || "") : "";
  }

  function inspect() {
    const text = bodyText();
    for (const [marker, code] of FAILURE_MARKERS) {
      if (text.includes(marker)) {
        if (lastFailure !== code) {
          lastFailure = code;
          chrome.runtime.sendMessage({
            source: "SOL62_CHATGPT_OBSERVER",
            type: "CHATGPT_CARRIER_FAILURE",
            code
          });
        }
        return;
      }
    }
    lastFailure = "";
    const now = Date.now();
    if (document.visibilityState === "visible" && now - lastHealthySignal > 15000) {
      lastHealthySignal = now;
      chrome.runtime.sendMessage({
        source: "SOL62_CHATGPT_OBSERVER",
        type: "CHATGPT_CARRIER_HEALTHY"
      });
    }
  }

  const observer = new MutationObserver(inspect);
  observer.observe(document.documentElement, { subtree: true, childList: true, characterData: true });
  document.addEventListener("visibilitychange", inspect);
  setInterval(inspect, 10000);
  inspect();
})();
