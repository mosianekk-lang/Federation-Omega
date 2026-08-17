(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ChatBridgeCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const COMPANION_VERSION = "0.3.0";
  const HANDOFF_SCHEMA = "CHATBRIDGE-HANDOFF-CAPSULE-2";
  const LEGACY_HANDOFF_SCHEMA = "CHATBRIDGE-HANDOFF-CAPSULE-1";
  const CAPTURE_SCHEMA = "CHATBRIDGE-ALPHA-OMEGA-BROWSER-CAPTURE-1";
  const PATH_KIND = "RENDERED_DOM";
  const LIMIT_PATTERNS = [
    /reached the maximum length for this conversation/i,
    /maximum (?:conversation|context) length/i,
    /conversation (?:is |has become )?too long/i,
    /keep talking by starting a new chat/i
  ];

  function normalizeText(value) {
    return String(value || "")
      .replace(/\r\n/g, "\n")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n{4,}/g, "\n\n\n")
      .trim();
  }

  function normalizeRole(value) {
    const role = normalizeText(value).toUpperCase();
    if (["USER", "ASSISTANT", "SYSTEM", "DEVELOPER", "TOOL", "CONNECTOR"].includes(role)) return role;
    return "UNKNOWN";
  }

  function streamForRole(role) {
    const normalized = normalizeRole(role);
    if (normalized === "TOOL") return "TOOL_RESULT";
    if (normalized === "CONNECTOR") return "CONNECTOR";
    if (["USER", "ASSISTANT", "SYSTEM", "DEVELOPER"].includes(normalized)) return normalized;
    return "OTHER";
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

  function canonicalize(value) {
    if (Array.isArray(value)) return value.map(canonicalize);
    if (value && typeof value === "object") {
      return Object.keys(value).sort().reduce((out, key) => {
        const item = value[key];
        if (typeof item !== "undefined") out[key] = canonicalize(item);
        return out;
      }, {});
    }
    return value;
  }

  function canonicalJson(value) {
    return JSON.stringify(canonicalize(value));
  }

  function bytesToHex(buffer) {
    return Array.from(new Uint8Array(buffer), (byte) => byte.toString(16).padStart(2, "0")).join("");
  }

  async function sha256(value) {
    const text = typeof value === "string" ? value : canonicalJson(value);
    const cryptoRef = globalThis.crypto;
    if (!cryptoRef || !cryptoRef.subtle || typeof TextEncoder === "undefined") {
      throw new Error("SHA256_UNAVAILABLE");
    }
    return bytesToHex(await cryptoRef.subtle.digest("SHA-256", new TextEncoder().encode(text)));
  }

  function deriveNewChatUrl(sourceUrl) {
    const url = new URL(sourceUrl);
    const segments = url.pathname.split("/").filter(Boolean);
    const conversationIndex = segments.indexOf("c");
    if (conversationIndex >= 0) {
      const retained = segments.slice(0, conversationIndex);
      url.pathname = retained.length ? `/${retained.join("/")}` : "/";
    }
    url.search = "";
    url.hash = "";
    return url.toString().replace(/\/$/, url.pathname === "/" ? "/" : "");
  }

  function parseConversationIdentity(sourceUrl) {
    let url;
    try {
      url = new URL(String(sourceUrl || ""));
    } catch (_error) {
      return {conversationKey: "", routeKey: "", origin: "", bound: false};
    }
    const segments = url.pathname.split("/").filter(Boolean);
    const conversationIndex = segments.indexOf("c");
    const conversationKey = conversationIndex >= 0 && segments[conversationIndex + 1]
      ? decodeURIComponent(segments[conversationIndex + 1])
      : "";
    const routeSegments = conversationIndex >= 0 ? segments.slice(0, conversationIndex) : segments;
    return {
      conversationKey,
      routeKey: routeSegments.join("/"),
      origin: url.origin,
      bound: Boolean(conversationKey)
    };
  }

  function closestTurnContainer(node) {
    if (!node) return null;
    if (typeof node.closest === "function") {
      return node.closest("[data-testid^='conversation-turn-'], article") || node;
    }
    return node;
  }

  function attribute(node, name) {
    return node && typeof node.getAttribute === "function" ? normalizeText(node.getAttribute(name)) : "";
  }

  function collectArtifactReferences(container) {
    if (!container || typeof container.querySelectorAll !== "function") return [];
    const links = Array.from(container.querySelectorAll("a[href]"));
    const artifacts = [];
    const seen = new Set();
    for (const link of links) {
      const href = attribute(link, "href");
      if (!href || href.startsWith("javascript:")) continue;
      const filename = normalizeText(attribute(link, "download") || link.textContent || "");
      const looksLikeArtifact = Boolean(
        attribute(link, "download") ||
        /(?:\/files?\/|\/download\/|sandbox:\/\/|attachment|file_)/i.test(href)
      );
      if (!looksLikeArtifact) continue;
      const key = `${href}|${filename}`;
      if (seen.has(key)) continue;
      seen.add(key);
      artifacts.push({
        artifact_key: `browser:${fnv1a(key)}`,
        filename,
        mime_type: "",
        size_bytes: 0,
        sha256: "",
        locator: href,
        availability: "POINTER_ONLY",
        required_for_context: true
      });
    }
    return artifacts;
  }

  function collectMessages(documentRef) {
    if (!documentRef || typeof documentRef.querySelectorAll !== "function") return [];
    const rawNodes = Array.from(documentRef.querySelectorAll(
      "[data-testid^='conversation-turn-'], article [data-message-author-role], [data-message-author-role]"
    ));
    const containers = [];
    const seenContainers = new Set();
    for (const rawNode of rawNodes) {
      const container = closestTurnContainer(rawNode);
      if (!container || seenContainers.has(container)) continue;
      seenContainers.add(container);
      containers.push(container);
    }

    const messages = [];
    for (const container of containers) {
      const roleNode = attribute(container, "data-message-author-role")
        ? container
        : (typeof container.querySelector === "function" ? container.querySelector("[data-message-author-role]") : null);
      const role = normalizeRole(attribute(roleNode, "data-message-author-role"));
      const contentNode = typeof container.querySelector === "function"
        ? (container.querySelector("[data-message-content], .markdown, [class*='markdown']") || container)
        : container;
      const text = normalizeText((contentNode && (contentNode.innerText || contentNode.textContent)) || "");
      if (!text || isLimitNotice(text)) continue;
      const sourceTurnId = attribute(container, "data-testid")
        || attribute(container, "data-message-id")
        || attribute(container, "id")
        || `rendered-turn-${messages.length + 1}`;
      const providerEventId = attribute(container, "data-message-id");
      messages.push({
        index: messages.length + 1,
        role: role.toLowerCase(),
        text,
        sourceTurnId,
        providerEventId,
        occurredAt: "",
        artifacts: collectArtifactReferences(container)
      });
    }
    return messages;
  }

  function normalizeMessages(messages) {
    return (messages || []).map((message, index) => ({
      index: Number(message.index) || index + 1,
      role: normalizeRole(message.role),
      text: normalizeText(message.text),
      sourceTurnId: normalizeText(message.sourceTurnId) || `rendered-turn-${index + 1}`,
      providerEventId: normalizeText(message.providerEventId),
      occurredAt: normalizeText(message.occurredAt),
      artifacts: Array.isArray(message.artifacts) ? message.artifacts.map((item) => canonicalize(item)) : []
    })).filter((message) => message.text);
  }

  function boundMessages(messages, maxChars) {
    const limit = Math.max(8000, Number(maxChars) || 60000);
    const clean = normalizeMessages(messages).map((message) => ({
      index: message.index,
      role: message.role.toLowerCase(),
      text: message.text,
      sourceTurnId: message.sourceTurnId
    }));
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

  function buildPathId(installationId) {
    return `browser-rendered-dom:${normalizeText(installationId) || "unbound-installation"}`;
  }

  async function buildCaptureEnvelope(input) {
    const capturedAt = normalizeText(input.capturedAt) || new Date().toISOString();
    const sourceUrl = String(input.sourceUrl || "");
    const identity = parseConversationIdentity(sourceUrl);
    if (!identity.bound) throw new Error("CONVERSATION_ID_UNAVAILABLE");
    const namespaceKey = normalizeText(input.namespaceKey).toLowerCase() || `chatgpt:${identity.conversationKey}`;
    const installationId = normalizeText(input.installationId) || "unbound-installation";
    const pathId = buildPathId(installationId);
    const normalized = normalizeMessages(input.messages || []);
    const streamCounts = new Map();
    const observations = [];

    for (let index = 0; index < normalized.length; index += 1) {
      const message = normalized[index];
      const globalSequence = index + 1;
      const stream = streamForRole(message.role);
      const streamSequence = (streamCounts.get(stream) || 0) + 1;
      streamCounts.set(stream, streamSequence);
      const sourceEventId = message.providerEventId
        ? `provider:${message.providerEventId}`
        : `turn:${message.sourceTurnId}`;
      const payloadHash = await sha256({
        conversation_key: identity.conversationKey,
        role: message.role,
        event_type: "MESSAGE",
        content: message.text,
        source_turn_id: message.sourceTurnId,
        provider_event_id: message.providerEventId,
        artifacts: message.artifacts
      });
      observations.push({
        conversation_key: identity.conversationKey,
        namespace_key: namespaceKey,
        path_id: pathId,
        stream,
        role: message.role,
        event_type: "MESSAGE",
        content: message.text,
        occurred_at: message.occurredAt || capturedAt,
        global_sequence: globalSequence,
        stream_sequence: streamSequence,
        source_event_id: sourceEventId,
        source_turn_id: message.sourceTurnId,
        provider_event_id: message.providerEventId,
        idempotency_key: `browser:${identity.conversationKey}:${sourceEventId}:${payloadHash}`,
        execution_state: "OBSERVED",
        payload_availability: "RAW_GOVERNED",
        sensitivity: normalizeText(input.sensitivity) || "GOVERNED_LOCAL",
        artifacts: message.artifacts,
        metadata: {
          companion_version: COMPANION_VERSION,
          capture_path_kind: PATH_KIND,
          payload_hash: payloadHash,
          timestamp_semantics: message.occurredAt ? "SOURCE_OBSERVED" : "SNAPSHOT_CAPTURE_TIME",
          rendered_dom_snapshot: true
        }
      });
    }

    const terminalObserved = Boolean(input.terminalObserved);
    if (terminalObserved) {
      const terminalSequence = observations.length + 1;
      const terminalText = normalizeText(input.terminalText) || "Provider maximum conversation length observed";
      const terminalHash = await sha256({
        conversation_key: identity.conversationKey,
        event_type: "TERMINAL_WARNING",
        content: terminalText,
        sequence: terminalSequence
      });
      observations.push({
        conversation_key: identity.conversationKey,
        namespace_key: namespaceKey,
        path_id: pathId,
        stream: "TERMINAL",
        role: "SYSTEM",
        event_type: "TERMINAL_WARNING",
        content: terminalText,
        occurred_at: capturedAt,
        global_sequence: terminalSequence,
        stream_sequence: 1,
        source_event_id: `terminal:${terminalHash}`,
        source_turn_id: "",
        provider_event_id: "",
        idempotency_key: `browser:${identity.conversationKey}:terminal:${terminalHash}`,
        execution_state: "NOT_EXECUTED_TERMINAL",
        payload_availability: "RAW_GOVERNED",
        sensitivity: normalizeText(input.sensitivity) || "GOVERNED_LOCAL",
        artifacts: [],
        metadata: {
          companion_version: COMPANION_VERSION,
          capture_path_kind: PATH_KIND,
          payload_hash: terminalHash,
          terminal_intent_is_not_execution: true
        }
      });
    }

    const streamManifest = Array.from(streamCounts.entries()).map(([stream, count]) => ({
      stream,
      observed_first_sequence: count ? 1 : null,
      observed_last_sequence: count || null,
      observed_count: count,
      required_for_exact_restore: Boolean(input.sourceCompleteClaim),
      source_complete_claim: Boolean(input.sourceCompleteClaim)
    }));
    if (terminalObserved) {
      streamManifest.push({
        stream: "TERMINAL",
        observed_first_sequence: 1,
        observed_last_sequence: 1,
        observed_count: 1,
        required_for_exact_restore: false,
        source_complete_claim: Boolean(input.sourceCompleteClaim)
      });
    }

    const snapshotSha256 = await sha256({
      conversation_key: identity.conversationKey,
      path_id: pathId,
      observations: observations.map((item) => ({
        source_event_id: item.source_event_id,
        payload_hash: item.metadata.payload_hash,
        global_sequence: item.global_sequence,
        stream: item.stream
      }))
    });

    return {
      schema: CAPTURE_SCHEMA,
      companion_version: COMPANION_VERSION,
      capture_id: `cbcap-${capturedAt.replace(/[-:.TZ]/g, "").slice(0, 14)}-${snapshotSha256.slice(0, 16)}`,
      captured_at: capturedAt,
      source: {
        provider: "CHATGPT_WEB",
        url: sourceUrl,
        title: normalizeText(input.title) || "Untitled ChatGPT conversation",
        conversation_key: identity.conversationKey,
        route_key: identity.routeKey
      },
      namespace_key: namespaceKey,
      capture_path: {
        conversation_key: identity.conversationKey,
        path_id: pathId,
        kind: PATH_KIND,
        source_provider: "CHATGPT_WEB",
        state: "AVAILABLE",
        priority: 70,
        proof_strength: 0.72,
        completeness: Boolean(input.sourceCompleteClaim) ? 1.0 : 0.65,
        freshness: 1.0,
        speed: 0.95,
        reversibility: 1.0,
        owner_burden: 0.0,
        privacy_cost: 0.35,
        maintenance_cost: 0.25,
        independent_group: `browser-installation:${installationId}`,
        authoritative: false,
        metadata: {
          companion_version: COMPANION_VERSION,
          rendered_dom_snapshot: true,
          source_complete_claim: Boolean(input.sourceCompleteClaim),
          coverage_assertion: Boolean(input.sourceCompleteClaim)
            ? "USER_OR_TEST_ASSERTED_COMPLETE_RENDERED_RANGE"
            : "BOUNDED_RENDERED_DOM_NO_NATIVE_COMPLETENESS_CLAIM"
        }
      },
      observations,
      stream_manifest: streamManifest,
      snapshot: {
        sha256: snapshotSha256,
        previous_sha256: normalizeText(input.previousSnapshotSha256),
        rendered_message_count: normalized.length,
        observation_count: observations.length,
        first_global_sequence: observations.length ? 1 : null,
        last_global_sequence: observations.length || null,
        terminal_observed: terminalObserved,
        exact_source_completeness_claimed: Boolean(input.sourceCompleteClaim)
      },
      truth_boundary: {
        native_hidden_chat_access: false,
        rendered_dom_may_be_virtualized: true,
        exact_restore_from_this_path_alone: Boolean(input.sourceCompleteClaim),
        provider_effects_require_readback: true,
        missing_content_is_never_guessed: true
      }
    };
  }

  function snapshotState(envelope) {
    const events = {};
    for (const observation of envelope.observations || []) {
      events[observation.source_event_id] = {
        payloadHash: observation.metadata && observation.metadata.payload_hash || "",
        globalSequence: observation.global_sequence,
        stream: observation.stream
      };
    }
    return {
      schema: "CHATBRIDGE-COMPANION-SNAPSHOT-STATE-1",
      conversationKey: envelope.source && envelope.source.conversation_key || "",
      pathId: envelope.capture_path && envelope.capture_path.path_id || "",
      snapshotSha256: envelope.snapshot && envelope.snapshot.sha256 || "",
      capturedAt: envelope.captured_at,
      events
    };
  }

  function diffCaptureEnvelope(previousState, envelope) {
    const previous = previousState && previousState.events || {};
    const added = [];
    const corrections = [];
    const currentKeys = new Set();

    for (const observation of envelope.observations || []) {
      const key = observation.source_event_id;
      currentKeys.add(key);
      const payloadHash = observation.metadata && observation.metadata.payload_hash || "";
      const prior = previous[key];
      if (!prior) {
        added.push(observation);
        continue;
      }
      if (prior.payloadHash !== payloadHash) {
        const correction = canonicalize(observation);
        correction.event_type = "CORRECTION";
        correction.stream = "CORRECTION";
        correction.global_sequence = null;
        correction.stream_sequence = null;
        correction.source_event_id = `${key}:revision:${payloadHash.slice(0, 16)}`;
        correction.idempotency_key = `browser:${envelope.source.conversation_key}:${correction.source_event_id}`;
        correction.metadata = Object.assign({}, correction.metadata, {
          correction_of_source_event_id: key,
          correction_of_payload_hash: prior.payloadHash,
          correction_reason: "RENDERED_TURN_CHANGED_AFTER_PRIOR_STABLE_SNAPSHOT"
        });
        corrections.push(correction);
      }
    }

    const removed = Object.keys(previous).filter((key) => !currentKeys.has(key));
    return Object.assign({}, envelope, {
      delta: {
        previous_snapshot_sha256: previousState && previousState.snapshotSha256 || "",
        current_snapshot_sha256: envelope.snapshot.sha256,
        added_count: added.length,
        correction_count: corrections.length,
        removed_from_rendered_dom_count: removed.length,
        removed_source_event_ids: removed,
        unchanged_count: Math.max(0, (envelope.observations || []).length - added.length - corrections.length),
        no_silent_deletion: true
      },
      observations: added.concat(corrections)
    });
  }

  function validateCaptureEnvelope(envelope) {
    if (!envelope || envelope.schema !== CAPTURE_SCHEMA) throw new Error("INVALID_CAPTURE_SCHEMA");
    if (!envelope.source || !normalizeText(envelope.source.conversation_key)) throw new Error("MISSING_CONVERSATION_KEY");
    if (!envelope.capture_path || envelope.capture_path.conversation_key !== envelope.source.conversation_key) {
      throw new Error("CAPTURE_PATH_IDENTITY_MISMATCH");
    }
    const seen = new Set();
    for (const observation of envelope.observations || []) {
      if (observation.conversation_key !== envelope.source.conversation_key) throw new Error("OBSERVATION_IDENTITY_MISMATCH");
      if (observation.namespace_key !== envelope.namespace_key) throw new Error("OBSERVATION_NAMESPACE_MISMATCH");
      if (observation.path_id !== envelope.capture_path.path_id) throw new Error("OBSERVATION_PATH_MISMATCH");
      if (!observation.source_event_id || seen.has(observation.source_event_id)) throw new Error("DUPLICATE_OR_MISSING_SOURCE_EVENT_ID");
      seen.add(observation.source_event_id);
    }
    return true;
  }

  function buildCapsule(input) {
    const capturedAt = input.capturedAt || new Date().toISOString();
    const sourceUrl = String(input.sourceUrl || "");
    const identity = parseConversationIdentity(sourceUrl);
    const packed = boundMessages(input.messages || [], input.maxChars);
    const transcriptText = packed.messages.map((message) => `${message.role}: ${message.text}`).join("\n\n");
    const idSeed = [sourceUrl, input.title || "", capturedAt, fnv1a(transcriptText)].join("|");
    return {
      schema: HANDOFF_SCHEMA,
      compatibleSchemas: [LEGACY_HANDOFF_SCHEMA],
      capsuleId: `CB-${capturedAt.replace(/[-:.TZ]/g, "").slice(0, 14)}-${fnv1a(idSeed)}`,
      capturedAt,
      source: {
        url: sourceUrl,
        title: normalizeText(input.title) || "Untitled ChatGPT conversation",
        conversationKey: identity.conversationKey,
        routeKey: identity.routeKey,
        successorUrl: sourceUrl ? deriveNewChatUrl(sourceUrl) : "https://chatgpt.com/"
      },
      continuity: {
        mode: "COMPACT_OPERATIONAL_CHECKPOINT_PLUS_FFCL_CAPTURE_POINTER",
        canonicalRegistryTitle: "CHATBRIDGE — UNIVERSAL — REGISTRY.md",
        adapterResolution: "RESOLVE_EXACT_CONVERSATION_THEN_NARROWEST_MATCHING_NAMESPACE",
        truthRule: "VERIFY_CANONICAL_SOURCES; LABEL_GAPS_UNVERIFIED; NEVER_GUESS",
        transcriptCapture: "BOUNDED_RENDERED_DOM_WITH_SEPARATE_FFCL_EVENT_LINEAGE",
        omittedMessageCount: packed.omittedMessageCount,
        captureReceipt: canonicalize(input.captureReceipt || {}),
        snapshotSha256: normalizeText(input.snapshotSha256)
      },
      metrics: {
        renderedMessageCount: (input.messages || []).length,
        retainedMessageCount: packed.messages.length,
        estimatedRenderedTokens: estimateTokens((input.messages || []).map((item) => item.text).join("\n"))
      },
      messages: packed.messages,
      nextAction: "Resolve the exact conversation and namespace, verify the FFCL/Alpha→Omega capture receipt, replay only verified events, reconcile bounded gaps, and continue the latest verified open action without restarting completed work."
    };
  }

  function validateCapsule(capsule) {
    if (!capsule || ![HANDOFF_SCHEMA, LEGACY_HANDOFF_SCHEMA].includes(capsule.schema) || !capsule.capsuleId) {
      throw new Error("INVALID_CAPSULE");
    }
    return true;
  }

  function renderRestorePrompt(capsule) {
    validateCapsule(capsule);
    return [
      "CHATBRIDGE RESTORE — SUCCESSOR CHAT",
      "",
      "Restore and continue the exact source conversation and workstream represented below.",
      "Resolve exact conversation identity before semantic aliases. Reconcile the compact checkpoint with the FFCL / Alpha→Omega capture receipt and current canonical sources.",
      "Replay only verified captured events in sequence. Expose missing ranges, unavailable payloads and unresolved artifacts; never synthesize gaps.",
      "Preserve corrections, execution-state distinctions, approval gates, privacy walls and provenance. Do not redo completed work.",
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
    COMPANION_VERSION,
    HANDOFF_SCHEMA,
    LEGACY_HANDOFF_SCHEMA,
    CAPTURE_SCHEMA,
    PATH_KIND,
    normalizeText,
    normalizeRole,
    streamForRole,
    isLimitNotice,
    estimateTokens,
    canonicalJson,
    sha256,
    deriveNewChatUrl,
    parseConversationIdentity,
    collectArtifactReferences,
    collectMessages,
    normalizeMessages,
    boundMessages,
    buildPathId,
    buildCaptureEnvelope,
    snapshotState,
    diffCaptureEnvelope,
    validateCaptureEnvelope,
    buildCapsule,
    validateCapsule,
    renderRestorePrompt,
    shouldPreempt,
    fnv1a
  });
});
