(() => {
  const SOURCE_ID = "FUSE-EDGE-CHATGPT-FRONT-STATUS";
  const INTERVAL_MS = 5000;

  const STATUS_PATTERNS = [
    "Connection interrupted. Waiting for the complete answer",
    "Connection interrupted",
    "Waiting for the complete answer",
    "Thinking",
    "Called tool",
    "Generating",
    "Reconnecting",
    "Something went wrong",
    "Error generating",
  ];

  let lastFingerprint = "";
  let lastLength = 0;
  let lastStatus = "";
  let lastMaterialChangeAt = performance.now();
  let timer = null;

  function simpleHash(text) {
    let h1 = 0x811c9dc5;
    for (let i = 0; i < text.length; i += 1) {
      h1 ^= text.charCodeAt(i);
      h1 = Math.imul(h1, 0x01000193);
    }
    return ("00000000" + (h1 >>> 0).toString(16)).slice(-8);
  }

  function shaLikeFingerprint(text) {
    // Privacy-preserving transport identifier only; not a cryptographic proof.
    return "opaque:fnv32:" + simpleHash(text);
  }

  function visibleText(node) {
    if (!node) return "";
    const style = window.getComputedStyle(node);
    if (style && (style.display === "none" || style.visibility === "hidden")) {
      return "";
    }
    return (node.innerText || node.textContent || "").trim();
  }

  function findStatusText() {
    const candidates = document.querySelectorAll(
      '[role="alert"], [aria-live], button, [data-testid], p, span'
    );
    for (const node of candidates) {
      const text = visibleText(node);
      if (!text || text.length > 240) continue;
      const lower = text.toLowerCase();
      for (const pattern of STATUS_PATTERNS) {
        if (lower.includes(pattern.toLowerCase())) {
          return pattern;
        }
      }
    }
    return "";
  }

  function stopButtonVisible() {
    const buttons = document.querySelectorAll("button");
    for (const button of buttons) {
      const label = (
        button.getAttribute("aria-label") ||
        button.getAttribute("title") ||
        visibleText(button)
      ).toLowerCase();
      if (label.includes("stop") && button.offsetParent !== null) {
        return true;
      }
    }
    return false;
  }

  function lastAssistantOutput() {
    const nodes = document.querySelectorAll('[data-message-author-role="assistant"]');
    const node = nodes.length ? nodes[nodes.length - 1] : null;
    const text = visibleText(node);
    return {
      fingerprint: text ? shaLikeFingerprint(text) : "",
      length: text.length,
    };
  }

  function toolActivityVisible() {
    const nodes = document.querySelectorAll('[aria-live], button, [role="status"], span');
    for (const node of nodes) {
      const text = visibleText(node);
      if (!text || text.length > 120) continue;
      const lower = text.toLowerCase();
      if (lower.includes("called tool") || lower.includes("tool call")) {
        return true;
      }
    }
    return false;
  }

  function buildSnapshot() {
    const now = performance.now();
    const statusText = findStatusText();
    const stopVisible = stopButtonVisible();
    const output = lastAssistantOutput();
    const thinkingVisible = statusText.toLowerCase() === "thinking";
    const toolVisible = toolActivityVisible();
    const responseInflight = stopVisible || thinkingVisible || toolVisible;

    const materialChanged =
      output.fingerprint !== lastFingerprint ||
      output.length !== lastLength ||
      statusText !== lastStatus;

    if (materialChanged) {
      lastMaterialChangeAt = now;
    }

    const noProgressMs = Math.max(0, now - lastMaterialChangeAt);
    const ownerVisibleProgress = materialChanged || noProgressMs < 15000;

    lastFingerprint = output.fingerprint;
    lastLength = output.length;
    lastStatus = statusText;

    return {
      source_id: SOURCE_ID,
      observed_monotonic: now / 1000,
      page_family: "chatgpt-web",
      status_text: statusText,
      response_inflight: responseInflight,
      stop_button_visible: stopVisible,
      thinking_visible: thinkingVisible,
      tool_activity_visible: toolVisible,
      connection_interrupted: statusText.toLowerCase().includes("connection interrupted"),
      visible_output_fingerprint: output.fingerprint,
      visible_output_length: output.length,
      owner_visible_progress: ownerVisibleProgress,
      local_no_progress_seconds: noProgressMs / 1000,
      privacy_mode: "STATUS_PLUS_OUTPUT_FINGERPRINT_ONLY",
    };
  }

  function sendSnapshot() {
    const snapshot = buildSnapshot();
    chrome.runtime.sendMessage(
      {kind: "FUSE_FRONT_FACING_STATUS_V1", snapshot},
      () => void chrome.runtime.lastError
    );
  }

  const observer = new MutationObserver(() => {
    window.clearTimeout(timer);
    timer = window.setTimeout(sendSnapshot, 300);
  });

  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["aria-label", "title", "class"],
  });

  window.setInterval(sendSnapshot, INTERVAL_MS);
  sendSnapshot();
})();
