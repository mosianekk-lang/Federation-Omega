(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ChatBridgeCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const SCHEMA = "CHATBRIDGE-HANDOFF-CAPSULE-1";
  const LIMIT_PATTERNS = [
    /reached the maximum length for this conversation/i,
    /maximum (?:conversation|context) length/i,
    /conversation (?:is |has become )?too long/i,
    /keep talking by starting a new chat/i
  ];

  function normalizeText(value) {
    return String(value || "").replace(/\r\n/g, "\n").replace(/[ \t]+\n/g, "\n").trim();
  }

  function isLimitNotice(value) {
    const text = normalizeText(value);
    return LIMIT_PATTERNS.some((pattern) => pattern.test(text));
  }

  function estimateTokens(value) {
    return Math.ceil(normalizeText(value).length / 4);
  }

  function fnv1a(value) {
    let hash = 0x811c9dc5;
    for (const character of String(value)) {
      hash ^= character.charCodeAt(0);
      hash = Math.imul(hash, 0x01000193);
    }
    return (hash >>> 0).toString(16).padStart(8, "0");
  }

  function deriveNewChatUrl(sourceUrl) {
    const url = new URL(sourceUrl);
    const conversationIndex = url.pathname.indexOf("/c/");
    if (conversationIndex >= 0) url.pathname = url.pathname.slice(0, conversationIndex) || "/";
    url.search = "";
    url.hash = "";
    return url.toString();
  }

  function collectMessages(documentRef) {
    if (!documentRef || typeof documentRef.querySelectorAll !== "function") return [];
    const nodes = Array.from(documentRef.querySelectorAll("[data-message-author-role]"));
    const messages = [];
    const seen = new Set();
    for (const node of nodes) {
      const role = node.getAttribute("data-message-author-role") || "unknown";
      const container = node.closest("article") || node;
      const contentNode = container.querySelector(".markdown, [class*='markdown'], [data-message-content]") || container;
      const text = normalizeText(contentNode.innerText || contentNode.textContent || "");
      if (!text) continue;
      const signature = role + ":" + fnv1a(text);
      if (seen.has(signature)) continue;
      seen.add(signature);
      messages.push({index: messages.length + 1, role, text});
    }
    return messages;
  }

  function boundMessages(messages, maxChars) {
    const limit = Math.max(8000, Number(maxChars) || 60000);
    const clean = (messages || []).map((message, index) => ({
      index: Number(message.index) || index + 1,
      role: normalizeText(message.role) || "unknown",
      text: normalizeText(message.text)
    })).filter((message) => message.text);
    const head = clean.slice(0, 4);
    const selected = [];
    let used = JSON.stringify(head).length;
    for (let index = clean.length - 1; index >= head.length; index -= 1) {
      const candidate = clean[index];
      const cost = JSON.stringify(candidate).length + 1;
      if (used + cost > limit) break;
      selected.unshift(candidate);
      used += cost;
    }
    const retained = head.concat(selected.filter((item) => !head.some((first) => first.index === item.index)));
    return {messages: retained, omittedMessageCount: Math.max(0, clean.length - retained.length)};
  }

  function buildCapsule(input) {
    const capturedAt = input.capturedAt || new Date().toISOString();
    const sourceUrl = String(input.sourceUrl || "");
    const packed = boundMessages(input.messages || [], input.maxChars);
    const transcriptText = packed.messages.map((message) => `${message.role}: ${message.text}`).join("\n\n");
    const idSeed = [sourceUrl, input.title || "", capturedAt, fnv1a(transcriptText)].join("|");
    return {
      schema: SCHEMA,
      capsuleId: `CB-${capturedAt.replace(/[-:.TZ]/g, "").slice(0, 14)}-${fnv1a(idSeed)}`,
      capturedAt,
      source: {
        url: sourceUrl,
        title: normalizeText(input.title) || "Untitled ChatGPT conversation",
        successorUrl: sourceUrl ? deriveNewChatUrl(sourceUrl) : "https://chatgpt.com/"
      },
      continuity: {
        mode: "COMPLETE_ACTIONABLE_STATE_PLUS_BOUNDED_TRANSCRIPT",
        canonicalRegistryTitle: "CHATBRIDGE — UNIVERSAL — REGISTRY.md",
        adapterResolution: "RESOLVE_NARROWEST_MATCHING_INSTANCE",
        truthRule: "VERIFY_CANONICAL_SOURCES; LABEL_GAPS_UNVERIFIED; NEVER_GUESS",
        transcriptCapture: "RENDERED_DOM_SNAPSHOT",
        omittedMessageCount: packed.omittedMessageCount
      },
      metrics: {
        renderedMessageCount: (input.messages || []).length,
        retainedMessageCount: packed.messages.length,
        estimatedRenderedTokens: estimateTokens((input.messages || []).map((item) => item.text).join("\n"))
      },
      messages: packed.messages,
      nextAction: "Restore the matching canonical ChatBridge adapter, reconcile this capsule, and continue the latest verified open action without restarting completed work."
    };
  }

  function renderRestorePrompt(capsule) {
    return [
      "CHATBRIDGE RESTORE — SUCCESSOR CHAT",
      "",
      "Restore and continue the exact workstream represented by the capsule below.",
      "Resolve CHATBRIDGE — UNIVERSAL — REGISTRY.md, then load the narrowest matching CURRENT adapter.",
      "Treat native evidence and controlling registers as authoritative. Mark unresolved items UNVERIFIED and never guess.",
      "Reconcile conflicts, preserve corrections and provenance, do not redo completed work, and continue the latest verified next action.",
      "This handoff respects the prior chat limit; it carries complete actionable state plus a bounded rendered transcript, not an unlimited verbatim context window.",
      "",
      "CAPSULE:",
      JSON.stringify(capsule, null, 2)
    ].join("\n");
  }

  function shouldPreempt(metrics, settings) {
    const tokenThreshold = Number(settings && settings.tokenThreshold) || 65000;
    const messageThreshold = Number(settings && settings.messageThreshold) || 80;
    return Number(metrics.estimatedRenderedTokens) >= tokenThreshold || Number(metrics.renderedMessageCount) >= messageThreshold;
  }

  return Object.freeze({
    SCHEMA, normalizeText, isLimitNotice, estimateTokens, deriveNewChatUrl,
    collectMessages, boundMessages, buildCapsule, renderRestorePrompt, shouldPreempt, fnv1a
  });
});
