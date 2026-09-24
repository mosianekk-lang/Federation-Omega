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

  const NEW_CHAT_LABELS = [
    /^new chat$/i,
    /^new conversation$/i,
    /^start new chat$/i,
    /^start a new chat$/i
  ];
  const NEW_CHAT_CONTEXT_TTL_MS = 8000;

  let lastFailure = "";
  let lastHealthySignal = 0;

  function bodyText() {
    return document.body ? (document.body.innerText || "") : "";
  }

  function compactText(value) {
    return String(value || "").replace(/\s+/g, " ").trim().slice(0, 120);
  }

  function isNewChatLabel(value) {
    const normalized = compactText(value);
    return NEW_CHAT_LABELS.some((pattern) => pattern.test(normalized));
  }

  function safeNewChatUrl(candidate) {
    try {
      const url = new URL(candidate || "/", location.origin);
      if (url.protocol !== "https:" || url.hostname !== "chatgpt.com") {
        return location.origin + "/";
      }
      if (/^\/(?:c|share)\//.test(url.pathname)) {
        return url.origin + "/";
      }
      return url.href;
    } catch (_) {
      return location.origin + "/";
    }
  }

  function semanticNewChatTarget(start) {
    let node = start instanceof Element ? start : null;
    let depth = 0;
    let score = 0;
    const reasons = [];
    let nativeAnchor = null;
    let candidateUrl = location.origin + "/";

    while (node && depth < 7) {
      const aria = compactText(node.getAttribute("aria-label"));
      const title = compactText(node.getAttribute("title"));
      const testId = compactText(node.getAttribute("data-testid"));
      const text = compactText(node.textContent);
      const role = compactText(node.getAttribute("role")).toLowerCase();

      if (isNewChatLabel(aria)) { score += 7; reasons.push("aria"); }
      if (isNewChatLabel(title)) { score += 6; reasons.push("title"); }
      if (isNewChatLabel(text)) { score += 5; reasons.push("text"); }
      if (/new[-_ ]?chat/i.test(testId)) { score += 5; reasons.push("testid"); }
      if (role === "button" || role === "link") { score += 1; }

      if (node instanceof HTMLAnchorElement && node.href) {
        nativeAnchor = node;
        candidateUrl = safeNewChatUrl(node.href);
        try {
          const parsed = new URL(node.href);
          if (parsed.hostname === "chatgpt.com" && parsed.pathname === "/") {
            score += 3;
            reasons.push("root-href");
          }
        } catch (_) {}
      }

      node = node.parentElement;
      depth += 1;
    }

    return {
      isNewChat: score >= 5,
      confidence: Math.min(1, score / 10),
      reasons,
      url: safeNewChatUrl(candidateUrl),
      nativeLink: Boolean(nativeAnchor && nativeAnchor.href)
    };
  }

  function sendNewChatContext(result) {
    chrome.runtime.sendMessage({
      source: "SOL62_CHATGPT_OBSERVER",
      type: "SOL62_NEW_CHAT_CONTEXT",
      observedAt: Date.now(),
      ttlMs: NEW_CHAT_CONTEXT_TTL_MS,
      isNewChat: result.isNewChat,
      confidence: result.confidence,
      reasons: result.reasons,
      url: result.url,
      nativeLink: result.nativeLink
    }).catch(() => {});
  }

  function openNewChat(result, disposition) {
    chrome.runtime.sendMessage({
      source: "SOL62_CHATGPT_OBSERVER",
      type: "SOL62_OPEN_NEW_CHAT",
      url: result.url,
      disposition
    }).catch(() => {});
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

  document.addEventListener("contextmenu", (event) => {
    sendNewChatContext(semanticNewChatTarget(event.target));
  }, true);

  document.addEventListener("click", (event) => {
    if (!(event.ctrlKey || event.metaKey)) return;
    const result = semanticNewChatTarget(event.target);
    if (!result.isNewChat || result.nativeLink) return;
    event.preventDefault();
    event.stopPropagation();
    openNewChat(result, "background_tab");
  }, true);

  document.addEventListener("auxclick", (event) => {
    if (event.button !== 1) return;
    const result = semanticNewChatTarget(event.target);
    if (!result.isNewChat || result.nativeLink) return;
    event.preventDefault();
    event.stopPropagation();
    openNewChat(result, "background_tab");
  }, true);

  const observer = new MutationObserver(inspect);
  observer.observe(document.documentElement, { subtree: true, childList: true, characterData: true });
  document.addEventListener("visibilitychange", inspect);
  setInterval(inspect, 10000);
  inspect();
})();
