(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ChatBridgeCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const PACKET_SCHEMA = "CHATBRIDGE-OMEGA49-CAPTURE-PACKET-1";
  const LEDGER_SCHEMA = "CHATBRIDGE-OMEGA49-BROWSER-LEDGER-1";
  const LIMIT_PATTERNS = [
    /reached the maximum length for this conversation/i,
    /maximum (?:conversation|context) length/i,
    /conversation (?:is |has become )?too long/i,
    /keep talking by starting a new chat/i,
    /you(?:'|’)ve hit max weighted tokens for this chat/i,
    /max(?:imum)? weighted tokens(?: for this chat)?/i,
    /weighted token(?:s)? (?:limit|maximum|cap)/i
  ];

  function normalizeText(value) {
    return String(value || "")
      .replace(/\r\n/g, "\n")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function canonicalize(value) {
    if (Array.isArray(value)) return value.map(canonicalize);
    if (value && typeof value === "object") {
      const output = {};
      for (const key of Object.keys(value).sort()) output[key] = canonicalize(value[key]);
      return output;
    }
    return value;
  }

  function canonicalJson(value) {
    return JSON.stringify(canonicalize(value));
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

  async function sha256(value) {
    const text = typeof value === "string" ? value : canonicalJson(value);
    if (globalThis.crypto && globalThis.crypto.subtle) {
      const bytes = new TextEncoder().encode(text);
      const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
      return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
    }
    if (typeof require === "function") {
      return require("node:crypto").createHash("sha256").update(text, "utf8").digest("hex");
    }
    throw new Error("SHA256_UNAVAILABLE");
  }

  function deriveConversationKey(sourceUrl) {
    try {
      const url = new URL(sourceUrl);
      const match = url.pathname.match(/\/c\/([^/?#]+)/i);
      return match ? decodeURIComponent(match[1]) : `route:${url.pathname || "/"}`;
    } catch (_) {
      return `unknown:${fnv1a(sourceUrl)}`;
    }
  }

  function deriveNewChatUrl(sourceUrl) {
    const url = new URL(sourceUrl);
    const conversationIndex = url.pathname.indexOf("/c/");
    if (conversationIndex >= 0) url.pathname = url.pathname.slice(0, conversationIndex) || "/";
    url.search = "";
    url.hash = "";
    return url.toString();
  }

  function namespaceHint(sourceUrl, title) {
    try {
      const url = new URL(sourceUrl);
      const project = url.pathname.match(/\/g\/([^/]+)/i);
      if (project) return project[1].toLowerCase();
    } catch (_) {}
    return normalizeText(title).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 80) || "unbound-chat";
  }

  function classifyStream(role) {
    const normalized = String(role || "").toLowerCase();
    if (normalized === "user") return "USER";
    if (normalized === "assistant") return "ASSISTANT";
    if (normalized === "system") return "SYSTEM";
    if (normalized === "developer") return "DEVELOPER";
    if (normalized === "tool") return "TOOL_RESULT";
    return "OTHER";
  }

  function collectArtifacts(container) {
    if (!container || typeof container.querySelectorAll !== "function") return [];
    const artifacts = [];
    const seen = new Set();
    const nodes = Array.from(container.querySelectorAll("a[href], img[src], [data-testid*='file'], [data-testid*='attachment']"));
    for (const node of nodes) {
      const locator = node.href || node.src || node.getAttribute("data-testid") || "";
      const filename = normalizeText(node.download || node.getAttribute("aria-label") || node.getAttribute("alt") || node.textContent || "artifact").slice(0, 240);
      const signature = `${filename}|${locator}`;
      if (!locator || seen.has(signature)) continue;
      seen.add(signature);
      const testId = String(node.getAttribute("data-testid") || "");
      const required = Boolean(node.download || /file|attachment/i.test(testId) || /files?|attachments?/i.test(locator));
      artifacts.push({
        artifactKey: `dom-${fnv1a(signature)}`,
        filename: filename || "artifact",
        mimeType: node.tagName === "IMG" ? "image/*" : "application/octet-stream",
        locator,
        availability: "POINTER_ONLY",
        requiredForContext: required,
        sourceProvider: "CHATGPT_RENDERED_DOM"
      });
    }
    return artifacts;
  }

  function collectMessages(documentRef) {
    if (!documentRef || typeof documentRef.querySelectorAll !== "function") return [];
    const nodes = Array.from(documentRef.querySelectorAll("[data-message-author-role]"));
    return nodes.map((node, index) => {
      const role = node.getAttribute("data-message-author-role") || "unknown";
      const container = node.closest("article") || node;
      const contentNode = container.querySelector(".markdown, [class*='markdown'], [data-message-content]") || container;
      const text = normalizeText(contentNode.innerText || contentNode.textContent || "");
      const sourceMessageId =
        node.getAttribute("data-message-id") ||
        container.getAttribute("data-message-id") ||
        container.id ||
        `${role}-${index + 1}`;
      return {
        sourceSequence: index + 1,
        sourceMessageId,
        role,
        stream: classifyStream(role),
        eventType: "MESSAGE",
        text,
        occurredAt: node.getAttribute("data-message-timestamp") || "",
        artifacts: collectArtifacts(container)
      };
    }).filter((message) => message.text);
  }

  function findLimitNotice(documentRef) {
    if (!documentRef || typeof documentRef.querySelectorAll !== "function") return "";
    const root = documentRef.querySelector("main") || documentRef.body;
    if (!root) return "";
    const candidates = Array.from(root.querySelectorAll("div, section, aside"))
      .map((node) => normalizeText(node.textContent || ""))
      .filter((text) => text && text.length < 1600 && isLimitNotice(text));
    candidates.sort((a, b) => a.length - b.length);
    return candidates[0] || "";
  }

  function buildCapturePacket(input) {
    const sourceUrl = String(input.sourceUrl || "");
    const title = normalizeText(input.title) || "Untitled ChatGPT conversation";
    const observations = input.messages || [];
    const terminalNotice = normalizeText(input.terminalNotice || "");
    return {
      schema: PACKET_SCHEMA,
      capturedAt: input.capturedAt || new Date().toISOString(),
      conversationKey: input.conversationKey || deriveConversationKey(sourceUrl),
      namespaceKey: input.namespaceKey || namespaceHint(sourceUrl, title),
      source: {
        provider: "CHATGPT_RENDERED_DOM",
        pathId: "rendered-dom-companion",
        independentGroup: "browser-rendered-dom",
        url: sourceUrl,
        title,
        successorUrl: sourceUrl ? deriveNewChatUrl(sourceUrl) : "https://chatgpt.com/"
      },
      observations,
      terminalNotice,
      metrics: {
        renderedMessageCount: observations.length,
        estimatedRenderedTokens: estimateTokens(observations.map((item) => item.text).join("\n")),
        requiredArtifactCount: observations.flatMap((item) => item.artifacts || []).filter((item) => item.requiredForContext).length
      }
    };
  }

  function missingRanges(sequences, expectedFirst, expectedLast) {
    const present = new Set((sequences || []).map(Number));
    const ranges = [];
    let start = null;
    for (let current = expectedFirst; current <= expectedLast; current += 1) {
      if (!present.has(current) && start === null) start = current;
      if (present.has(current) && start !== null) {
        ranges.push([start, current - 1]);
        start = null;
      }
    }
    if (start !== null) ranges.push([start, expectedLast]);
    return ranges;
  }

  function latestTranscriptEvents(ledger) {
    if (!ledger || !Array.isArray(ledger.events)) return [];
    const latest = new Map();
    for (const event of ledger.events) {
      if (event.eventType !== "MESSAGE") continue;
      latest.set(event.sourceMessageId, event);
    }
    return Array.from(latest.values()).sort((a, b) => a.sourceSequence - b.sourceSequence || a.appendSequence - b.appendSequence);
  }

  function transcriptLine(event) {
    const role = String(event.role || "unknown").toUpperCase();
    return `[${event.sourceSequence}] ${role}\n${normalizeText(event.content)}`;
  }

  function buildReplayPrompts(ledger, maxChars) {
    const limit = Math.max(12000, Number(maxChars) || 100000);
    const events = latestTranscriptEvents(ledger);
    const manifest = ledger.manifest || {};
    const header = [
      "CHATBRIDGE Ω4.9 — FULL-FIDELITY SUCCESSOR RESTORE",
      "",
      `Source conversation: ${ledger.conversationKey}`,
      `Namespace: ${ledger.namespaceKey}`,
      `Restore mode: ${manifest.restoreMode || "BOUNDED_MULTIPATH_MULTISTREAM_RESTORE"}`,
      `Integrity: ${manifest.integrityState || "UNVERIFIED"}`,
      `Coverage: ${manifest.coverageState || "UNVERIFIED"}`,
      "",
      "The following packets are an ordered rendered-conversation transcript captured by the authorised browser companion. Preserve corrections and provenance. Do not infer hidden or missing provider events. Reply only with the requested packet acknowledgement until the FINAL packet arrives."
    ].join("\n");
    const prompts = [header];
    let current = [];
    let used = 0;
    for (const event of events) {
      const line = transcriptLine(event);
      if (line.length > limit) {
        if (current.length) {
          prompts.push(current.join("\n\n"));
          current = [];
          used = 0;
        }
        const parts = Math.ceil(line.length / limit);
        for (let index = 0; index < parts; index += 1) {
          prompts.push(`OVERSIZED EVENT ${event.sourceSequence} — PART ${index + 1}/${parts}\n${line.slice(index * limit, (index + 1) * limit)}`);
        }
        continue;
      }
      if (used + line.length + 2 > limit && current.length) {
        prompts.push(current.join("\n\n"));
        current = [];
        used = 0;
      }
      current.push(line);
      used += line.length + 2;
    }
    if (current.length) prompts.push(current.join("\n\n"));
    prompts.push([
      "FINAL CHATBRIDGE Ω4.9 RESTORE PACKET",
      "Reconcile the transcript with the exact namespace, current canonical provider sources and active governance controls. Preserve the manifest gaps. Do not rebuild completed work. Resume the latest verified next action only after semantic acceptance and duplicate-action checks pass.",
      `Manifest: ${canonicalJson(manifest)}`
    ].join("\n\n"));
    return prompts.map((text, index) => ({
      packetIndex: index + 1,
      packetCount: prompts.length,
      text: index === prompts.length - 1 ? text : `${text}\n\nPACKET ${index + 1}/${prompts.length}. Reply exactly: ACK ${index + 1}`
    }));
  }

  function buildWorkingSetPrompts(ledger, options) {
    const opts = options || {};
    const maxChars = Math.max(6000, Number(opts.maxChars) || 12000);
    const maxEvents = Math.max(4, Number(opts.maxEvents) || 12);
    const events = latestTranscriptEvents(ledger);
    const manifest = ledger.manifest || {};
    const archive = {
      conversationKey: String(ledger.conversationKey || ""),
      namespaceKey: String(ledger.namespaceKey || ""),
      restoreMode: String(manifest.restoreMode || "BOUNDED_MULTIPATH_MULTISTREAM_RESTORE"),
      integrityState: String(manifest.integrityState || "UNVERIFIED"),
      coverageState: String(manifest.coverageState || "UNVERIFIED"),
      firstSourceSequence: manifest.firstSourceSequence == null ? null : Number(manifest.firstSourceSequence),
      lastSourceSequence: manifest.lastSourceSequence == null ? null : Number(manifest.lastSourceSequence),
      capturedEventCount: Number(manifest.capturedEventCount || 0),
      chainHeadSha256: String(manifest.chainHeadSha256 || ""),
      terminalObserved: Boolean(manifest.terminalObserved),
      missingRanges: manifest.missingRanges || [],
      unresolvedArtifactCount: Array.isArray(manifest.unresolvedArtifacts) ? manifest.unresolvedArtifacts.length : 0
    };
    const header = [
      "CHATBRIDGE Ω4.9 — CAPACITY-SAFE WORKING-SET RESTORE",
      "",
      "This successor chat is a detachable client, not the mission authority.",
      "The full rendered transcript remains in the governed external ledger/archive; do not ask the owner to paste or replay history.",
      "Fresh-read START:FUSE_ONE and current canonical/provider state, JOIN the existing mission/checkpoint, and resume only the highest-value unresolved action.",
      "The recent turns below are a bounded working projection, not a complete transcript."
    ].join("\n");
    const trailerPrefix = "\n\nARCHIVE MANIFEST\n";
    const trailer = trailerPrefix + canonicalJson(archive);
    const budget = Math.max(1000, maxChars - header.length - trailer.length - 4);
    const selected = [];
    let used = 0;
    for (let index = events.length - 1; index >= 0 && selected.length < maxEvents; index -= 1) {
      const line = transcriptLine(events[index]);
      if (selected.length && used + line.length + 2 > budget) break;
      if (!selected.length && line.length > budget) {
        selected.unshift(line.slice(Math.max(0, line.length - budget)));
        used = budget;
        break;
      }
      selected.unshift(line);
      used += line.length + 2;
    }
    const body = selected.length ? selected.join("\n\n") : "(No rendered message events were available; restore from canonical mission state.)";
    let text = header + "\n\nRECENT WORKING SET\n" + body + trailer;
    if (text.length > maxChars) text = text.slice(0, maxChars);
    return [{packetIndex: 1, packetCount: 1, text}];
  }

  function shouldPreempt(metrics, settings) {
    const tokenThreshold = Number(settings && settings.tokenThreshold) || 65000;
    const messageThreshold = Number(settings && settings.messageThreshold) || 80;
    return Number(metrics.estimatedRenderedTokens) >= tokenThreshold || Number(metrics.renderedMessageCount) >= messageThreshold;
  }

  function shouldAutoHandoff(packet, settings) {
    const current = packet || {};
    return Boolean(normalizeText(current.terminalNotice || "")) || shouldPreempt(current.metrics || {}, settings);
  }

  return Object.freeze({
    PACKET_SCHEMA,
    LEDGER_SCHEMA,
    normalizeText,
    canonicalize,
    canonicalJson,
    isLimitNotice,
    estimateTokens,
    fnv1a,
    sha256,
    deriveConversationKey,
    deriveNewChatUrl,
    namespaceHint,
    classifyStream,
    collectArtifacts,
    collectMessages,
    findLimitNotice,
    buildCapturePacket,
    missingRanges,
    latestTranscriptEvents,
    buildReplayPrompts,
    buildWorkingSetPrompts,
    shouldPreempt,
    shouldAutoHandoff
  });
});
