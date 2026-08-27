(function (root, factory) {
  const core = root.ChatBridgeCore || (typeof require === "function" ? require("./bridge-core.js") : null);
  const api = factory(core);
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ChatBridgeEdgeEgress = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function (core) {
  "use strict";

  if (!core) throw new Error("CHATBRIDGE_CORE_REQUIRED");

  const EGRESS_SCHEMA = "CHATBRIDGE-OMEGA49-EDGE-EGRESS-1";
  const ACK_SCHEMA = "SOVARA-BEF-EDGE-ACK-1";
  const EDGE_AGENT_EXTENSION_ID = "apokbhjjgiaceigelkedcelcecfmgnia";
  const DEFAULT_MAX_EVENTS = 50;
  const DEFAULT_MAX_BYTES = 700000;
  const CIRCUIT_MS = 5 * 60 * 1000;

  function stateKey(conversationKey) {
    return `chatbridgeEdgeEgress:${String(conversationKey)}`;
  }

  function stripLocator(locator) {
    const value = String(locator || "");
    if (!value) return "";
    try {
      const url = new URL(value);
      if (!/^https?:$/i.test(url.protocol)) return "";
      url.search = "";
      url.hash = "";
      return url.toString();
    } catch (_) {
      return "";
    }
  }

  async function sanitizeArtifact(artifact) {
    const input = artifact || {};
    const locator = String(input.locator || "");
    return {
      artifactKey: String(input.artifactKey || input.artifact_key || ""),
      filename: String(input.filename || "artifact"),
      mimeType: String(input.mimeType || input.mime_type || "application/octet-stream"),
      locator: stripLocator(locator),
      locatorSha256: locator ? await core.sha256(locator) : "",
      availability: String(input.availability || "POINTER_ONLY"),
      requiredForContext: Boolean(input.requiredForContext || input.required_for_context),
      sourceProvider: String(input.sourceProvider || input.source_provider || "CHATGPT_RENDERED_DOM")
    };
  }

  async function sanitizeEvent(event) {
    const artifacts = [];
    for (const artifact of event.artifacts || []) artifacts.push(await sanitizeArtifact(artifact));
    return {
      eventId: String(event.eventId || ""),
      appendSequence: Number(event.appendSequence || 0),
      sourceSequence: event.sourceSequence == null ? null : Number(event.sourceSequence),
      sourceMessageId: String(event.sourceMessageId || ""),
      role: String(event.role || "unknown"),
      stream: String(event.stream || "OTHER"),
      eventType: String(event.eventType || "OTHER"),
      content: String(event.content || ""),
      occurredAt: String(event.occurredAt || ""),
      capturedAt: String(event.capturedAt || ""),
      executionState: String(event.executionState || "OBSERVED"),
      payloadAvailability: String(event.payloadAvailability || "RAW_GOVERNED"),
      sensitivity: String(event.sensitivity || "GOVERNED_LOCAL"),
      artifacts,
      contentHash: String(event.contentHash || ""),
      previousEventHash: String(event.previousEventHash || ""),
      supersedesEventId: String(event.supersedesEventId || ""),
      pathId: String(event.pathId || "rendered-dom-companion"),
      providerReadback: String(event.providerReadback || "BROWSER_RENDERED_DOM_OBSERVATION"),
      eventHash: String(event.eventHash || "")
    };
  }

  function byteLength(value) {
    return new TextEncoder().encode(core.canonicalJson(value)).length;
  }

  function chunkEvents(events, maxEvents, maxBytes) {
    const eventLimit = Math.max(1, Number(maxEvents) || DEFAULT_MAX_EVENTS);
    const byteLimit = Math.max(4096, Number(maxBytes) || DEFAULT_MAX_BYTES);
    const chunks = [];
    let current = [];
    for (const event of events || []) {
      const candidate = current.concat([event]);
      if (current.length && (candidate.length > eventLimit || byteLength(candidate) > byteLimit)) {
        chunks.push(current);
        current = [event];
      } else {
        current = candidate;
      }
    }
    if (current.length) chunks.push(current);
    return chunks;
  }

  async function buildEnvelope(ledger, events, reason) {
    const sanitized = [];
    for (const event of events) sanitized.push(await sanitizeEvent(event));
    const firstAppend = sanitized.length ? sanitized[0].appendSequence : 0;
    const lastAppend = sanitized.length ? sanitized[sanitized.length - 1].appendSequence : 0;
    const source = ledger.source || {};
    const manifest = ledger.manifest || {};
    const envelope = {
      schema: EGRESS_SCHEMA,
      version: "1.0",
      conversationKey: String(ledger.conversationKey || ""),
      namespaceKey: String(ledger.namespaceKey || ""),
      source: {
        provider: String(source.provider || "CHATGPT_RENDERED_DOM"),
        pathId: String(source.pathId || "rendered-dom-companion"),
        independentGroup: String(source.independentGroup || "browser-rendered-dom"),
        title: String(source.title || ""),
        urlSha256: source.url ? await core.sha256(String(source.url)) : ""
      },
      fromAppendSequence: firstAppend,
      toAppendSequence: lastAppend,
      events: sanitized,
      manifest: {
        restoreMode: String(manifest.restoreMode || ""),
        integrityState: String(manifest.integrityState || ""),
        coverageState: String(manifest.coverageState || ""),
        providerCompleteness: String(manifest.providerCompleteness || "RENDERED_DOM_ONLY_NOT_HIDDEN_NATIVE_EVENTS"),
        exactRenderedTranscriptComplete: Boolean(manifest.exactRenderedTranscriptComplete),
        exactContextComplete: Boolean(manifest.exactContextComplete),
        firstSourceSequence: manifest.firstSourceSequence == null ? null : Number(manifest.firstSourceSequence),
        lastSourceSequence: manifest.lastSourceSequence == null ? null : Number(manifest.lastSourceSequence),
        capturedEventCount: Number(manifest.capturedEventCount || 0),
        latestRenderedMessageCount: Number(manifest.latestRenderedMessageCount || 0),
        missingRanges: manifest.missingRanges || [],
        unresolvedArtifacts: manifest.unresolvedArtifacts || [],
        chainHeadSha256: String(manifest.chainHeadSha256 || ""),
        terminalObserved: Boolean(manifest.terminalObserved),
        truthBoundary: String(manifest.truthBoundary || "")
      },
      reason: String(reason || "CAPTURE"),
      createdAt: new Date().toISOString()
    };
    envelope.envelopeSha256 = await core.sha256(envelope);
    return envelope;
  }

  async function loadState(conversationKey) {
    if (!globalThis.chrome || !chrome.storage || !chrome.storage.local) return {};
    const key = stateKey(conversationKey);
    const stored = await chrome.storage.local.get(key);
    return stored[key] || {};
  }

  async function saveState(conversationKey, state) {
    if (!globalThis.chrome || !chrome.storage || !chrome.storage.local) return;
    await chrome.storage.local.set({[stateKey(conversationKey)]: state});
  }

  async function sendEnvelope(envelope) {
    if (!globalThis.chrome || !chrome.runtime || !chrome.runtime.sendMessage) {
      return {ok: false, state: "EDGE_AGENT_RUNTIME_UNAVAILABLE"};
    }
    try {
      const response = await chrome.runtime.sendMessage(
        EDGE_AGENT_EXTENSION_ID,
        {type: "CHATBRIDGE_PROVENANCE_DELTA", envelope}
      );
      if (!response || response.schema !== ACK_SCHEMA || !response.ok) {
        return {ok: false, state: "EDGE_AGENT_ACK_INVALID", response: response || null};
      }
      if (String(response.envelopeSha256 || "") !== envelope.envelopeSha256) {
        return {ok: false, state: "EDGE_AGENT_ACK_HASH_MISMATCH"};
      }
      if (Number(response.toAppendSequence || 0) !== Number(envelope.toAppendSequence || 0)) {
        return {ok: false, state: "EDGE_AGENT_ACK_SEQUENCE_MISMATCH"};
      }
      return {ok: true, state: "EDGE_AGENT_ACK_VERIFIED", response};
    } catch (error) {
      return {ok: false, state: "EDGE_AGENT_UNAVAILABLE", error: String(error && error.message || error)};
    }
  }

  async function flushLedger(ledger, options) {
    const opts = options || {};
    if (!ledger || !ledger.conversationKey || !Array.isArray(ledger.events)) {
      return {ok: false, state: "INVALID_LEDGER"};
    }
    const now = Date.now();
    const state = await loadState(ledger.conversationKey);
    if (Number(state.circuitUntil || 0) > now) {
      return {ok: false, state: "EDGE_EGRESS_CIRCUIT_OPEN", circuitUntil: state.circuitUntil};
    }
    const lastAck = Number(state.lastAckAppendSequence || 0);
    const pending = ledger.events.filter((event) => Number(event.appendSequence || 0) > lastAck);
    if (!pending.length) return {ok: true, state: "NO_NEW_EVENTS", lastAckAppendSequence: lastAck};

    const chunks = chunkEvents(pending, opts.maxEvents, opts.maxBytes);
    let acknowledged = lastAck;
    let lastReceipt = "";
    for (const chunk of chunks.slice(0, Number(opts.maxBatches || 4))) {
      const envelope = await buildEnvelope(ledger, chunk, opts.reason || "CAPTURE");
      const result = await sendEnvelope(envelope);
      if (!result.ok) {
        const failures = Number(state.consecutiveFailures || 0) + 1;
        const nextState = {
          lastAckAppendSequence: acknowledged,
          consecutiveFailures: failures,
          lastFailure: result.state,
          lastFailureAt: new Date().toISOString(),
          circuitUntil: now + CIRCUIT_MS
        };
        await saveState(ledger.conversationKey, nextState);
        return Object.assign({lastAckAppendSequence: acknowledged}, result);
      }
      acknowledged = Number(envelope.toAppendSequence || acknowledged);
      lastReceipt = String(result.response.receiptId || "");
      await saveState(ledger.conversationKey, {
        lastAckAppendSequence: acknowledged,
        consecutiveFailures: 0,
        circuitUntil: 0,
        lastReceiptId: lastReceipt,
        lastEnvelopeSha256: envelope.envelopeSha256,
        lastAckAt: new Date().toISOString()
      });
    }
    return {
      ok: true,
      state: acknowledged === Number(ledger.events[ledger.events.length - 1].appendSequence || 0)
        ? "EDGE_EGRESS_CAUGHT_UP"
        : "EDGE_EGRESS_PARTIAL_BACKLOG",
      lastAckAppendSequence: acknowledged,
      lastReceiptId: lastReceipt
    };
  }

  return Object.freeze({
    EGRESS_SCHEMA,
    ACK_SCHEMA,
    EDGE_AGENT_EXTENSION_ID,
    stripLocator,
    sanitizeArtifact,
    sanitizeEvent,
    chunkEvents,
    buildEnvelope,
    flushLedger
  });
});
