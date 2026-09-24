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

  function stableHash(value) {
    let hash = 2166136261;
    const text = String(value || "");
    for (let i = 0; i < text.length; i += 1) {
      hash ^= text.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16).padStart(8, "0");
  }

  function elementRole(element) {
    return compactText(element.getAttribute("role"))
      || (element instanceof HTMLButtonElement ? "button"
        : element instanceof HTMLAnchorElement ? "link"
        : element instanceof HTMLTextAreaElement ? "textbox"
        : element instanceof HTMLInputElement ? "textbox"
        : element instanceof HTMLSelectElement ? "combobox"
        : element.getAttribute("contenteditable") === "true" ? "textbox"
        : element.tagName.toLowerCase());
  }

  function accessibleName(element) {
    const labelledBy = compactText(element.getAttribute("aria-labelledby"));
    if (labelledBy) {
      const label = document.getElementById(labelledBy);
      if (label) return compactText(label.textContent);
    }
    return compactText(
      element.getAttribute("aria-label")
      || element.getAttribute("title")
      || element.getAttribute("placeholder")
      || element.getAttribute("name")
      || element.textContent
    );
  }

  function elementVisible(element) {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return rect.width > 0
      && rect.height > 0
      && style.display !== "none"
      && style.visibility !== "hidden";
  }

  function descriptor(element) {
    const role = elementRole(element);
    const name = accessibleName(element);
    const text = compactText(element.textContent);
    const href = element instanceof HTMLAnchorElement && element.href
      ? safeNewChatUrl(element.href)
      : "";
    const testId = compactText(element.getAttribute("data-testid"));
    const identity = [
      element.tagName.toLowerCase(),
      role,
      name,
      text,
      href,
      testId
    ].join("|");
    const rect = element.getBoundingClientRect();
    return {
      stable_id: "sem-" + stableHash(identity),
      role,
      name,
      text,
      href,
      disabled: Boolean(element.disabled) || element.getAttribute("aria-disabled") === "true",
      checked: element.getAttribute("aria-checked") || "",
      expanded: element.getAttribute("aria-expanded") || "",
      test_id: testId,
      rect: {
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height)
      }
    };
  }

  function interactiveElements() {
    return Array.from(document.querySelectorAll(
      'a,button,input,textarea,select,[role],[contenteditable="true"]'
    )).filter((element) => element instanceof Element && elementVisible(element));
  }

  function semanticSnapshot() {
    const controls = interactiveElements().slice(0, 300).map(descriptor);
    return {
      schema: "SOL62_SEMANTIC_BROWSER_SNAPSHOT_V1",
      origin: location.origin,
      pathname: location.pathname,
      title: document.title,
      visibility: document.visibilityState,
      controls,
      control_count: controls.length,
      action_observed: true
    };
  }

  function targetScore(desc, target) {
    let score = 0;
    if (target.stable_id && desc.stable_id === target.stable_id) score += 0.72;
    if (target.role && desc.role.toLowerCase() === String(target.role).toLowerCase()) score += 0.12;
    if (target.name && desc.name.toLowerCase() === String(target.name).trim().toLowerCase()) score += 0.10;
    if (target.text && desc.text.toLowerCase() === String(target.text).trim().toLowerCase()) score += 0.06;
    if (target.href && desc.href === target.href) score += 0.12;
    return Math.min(1, score);
  }

  function resolveSemanticTarget(target) {
    const rows = interactiveElements().map((element) => ({
      element,
      descriptor: descriptor(element)
    }));
    const ranked = rows
      .map((row) => ({ ...row, score: targetScore(row.descriptor, target || {}) }))
      .sort((a, b) => b.score - a.score);
    const best = ranked[0] || null;
    const second = ranked[1] || null;
    if (!best || best.score < 0.60) {
      return { ok: false, reason: "SEMANTIC_TARGET_NOT_FOUND", confidence: best ? best.score : 0 };
    }
    if (second && second.score >= best.score - 0.03 && best.score < 0.95) {
      return { ok: false, reason: "SEMANTIC_TARGET_AMBIGUOUS", confidence: best.score };
    }
    return { ok: true, ...best };
  }

  async function executeSemanticCommand(command) {
    const operation = String(command.operation || "").toUpperCase();
    if (operation === "SEMANTIC_SNAPSHOT") return semanticSnapshot();

    const args = command.args || {};
    const resolved = resolveSemanticTarget(args.target || {});
    if (!resolved.ok) {
      return {
        schema: "SOL62_SEMANTIC_BROWSER_ACTION_V1",
        operation,
        verified: false,
        reason: resolved.reason,
        confidence: resolved.confidence || 0,
        action_observed: false
      };
    }

    const element = resolved.element;
    if (operation === "FOCUS_ELEMENT") {
      element.focus({ preventScroll: true });
    } else if (operation === "SCROLL_ELEMENT") {
      element.scrollIntoView({ block: "center", inline: "nearest", behavior: "auto" });
    } else if (operation === "CLICK_ELEMENT") {
      if (command.effect_class !== "WEBSITE_STATE" || command.authority_bound !== true) {
        return { verified: false, reason: "WEBSITE_STATE_AUTHORITY_NOT_BOUND", action_observed: false };
      }
      if (resolved.descriptor.disabled) {
        return { verified: false, reason: "SEMANTIC_TARGET_DISABLED", action_observed: false };
      }
      element.click();
    } else if (operation === "FILL_ELEMENT") {
      if (command.effect_class !== "WEBSITE_STATE" || command.authority_bound !== true) {
        return { verified: false, reason: "WEBSITE_STATE_AUTHORITY_NOT_BOUND", action_observed: false };
      }
      const value = String(args.value ?? "");
      if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
        const proto = element instanceof HTMLInputElement
          ? HTMLInputElement.prototype
          : HTMLTextAreaElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
        if (setter) setter.call(element, value);
        else element.value = value;
        element.dispatchEvent(new Event("input", { bubbles: true }));
        element.dispatchEvent(new Event("change", { bubbles: true }));
      } else if (element.getAttribute("contenteditable") === "true") {
        element.focus();
        element.textContent = value;
        element.dispatchEvent(new InputEvent("input", {
          bubbles: true,
          inputType: "insertText",
          data: value
        }));
      } else {
        return { verified: false, reason: "SEMANTIC_TARGET_NOT_FILLABLE", action_observed: false };
      }
    } else {
      return { verified: false, reason: "UNSUPPORTED_SEMANTIC_OPERATION", action_observed: false };
    }

    await new Promise((resolve) => setTimeout(resolve, 120));
    const after = descriptor(element);
    return {
      schema: "SOL62_SEMANTIC_BROWSER_ACTION_V1",
      operation,
      verified: true,
      action_observed: true,
      confidence: resolved.score,
      target: after,
      url: location.href,
      fill_length: operation === "FILL_ELEMENT" ? String(args.value ?? "").length : undefined
    };
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

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (!message || message.source !== "SOL62_BROWSER_CONTROL") return;
    if (message.type !== "SOL62_EXECUTE_BROWSER_COMMAND") return;
    executeSemanticCommand(message.command || {})
      .then((result) => sendResponse(result))
      .catch((error) => sendResponse({
        verified: false,
        action_observed: false,
        reason: String((error && error.message) || "SEMANTIC_ACTION_FAILED").slice(0, 128)
      }));
    return true;
  });

  const observer = new MutationObserver(inspect);
  observer.observe(document.documentElement, { subtree: true, childList: true, characterData: true });
  document.addEventListener("visibilitychange", inspect);
  setInterval(inspect, 10000);
  setInterval(() => {
    chrome.runtime.sendMessage({
      source: "SOL62_CHATGPT_OBSERVER",
      type: "SOL62_BROWSER_POLL"
    }).catch(() => {});
  }, 5000);
  inspect();
})();
