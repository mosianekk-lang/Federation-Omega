(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.SovaraBefEdgeProtocol = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const EGRESS_SCHEMA = "CHATBRIDGE-OMEGA49-EDGE-EGRESS-1";
  const ACK_SCHEMA = "SOVARA-BEF-EDGE-ACK-1";
  const CHATBRIDGE_EXTENSION_ID = "kacbginamagliaddmlkffhcadpamomjb";
  const EDGE_AGENT_EXTENSION_ID = "apokbhjjgiaceigelkedcelcecfmgnia";
  const NATIVE_HOST_NAME = "com.sovara.bef_edge";
  const MAX_EVENTS = 100;
  const MAX_ENVELOPE_BYTES = 900000;

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

  async function sha256(value) {
    const text = typeof value === "string" ? value : canonicalJson(value);
    if (globalThis.crypto && globalThis.crypto.subtle) {
      const digest = await globalThis.crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
      return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
    }
    if (typeof require === "function") {
      return require("node:crypto").createHash("sha256").update(text, "utf8").digest("hex");
    }
    throw new Error("SHA256_UNAVAILABLE");
  }

  function bytes(value) {
    return new TextEncoder().encode(canonicalJson(value)).length;
  }

  function isSha256(value) {
    return /^[a-f0-9]{64}$/i.test(String(value || ""));
  }

  function validateArtifact(artifact) {
    if (!artifact || typeof artifact !== "object") return false;
    if (artifact.locator && /[?#]/.test(String(artifact.locator))) return false;
    if (artifact.locatorSha256 && !isSha256(artifact.locatorSha256)) return false;
    return true;
  }

  function validateEvent(event, previousAppend) {
    if (!event || typeof event !== "object") return {ok: false, error: "EVENT_NOT_OBJECT"};
    const append = Number(event.appendSequence || 0);
    if (!Number.isInteger(append) || append <= previousAppend) return {ok: false, error: "EVENT_APPEND_ORDER_INVALID"};
    if (!isSha256(event.contentHash) || !isSha256(event.eventHash)) return {ok: false, error: "EVENT_HASH_INVALID"};
    for (const artifact of event.artifacts || []) {
      if (!validateArtifact(artifact)) return {ok: false, error: "ARTIFACT_LOCATOR_NOT_REDACTED"};
    }
    return {ok: true, append};
  }

  async function validateEnvelope(envelope) {
    if (!envelope || typeof envelope !== "object") return {ok: false, error: "ENVELOPE_NOT_OBJECT"};
    if (envelope.schema !== EGRESS_SCHEMA) return {ok: false, error: "SCHEMA_MISMATCH"};
    if (!String(envelope.conversationKey || "").trim()) return {ok: false, error: "CONVERSATION_REQUIRED"};
    if (!String(envelope.namespaceKey || "").trim()) return {ok: false, error: "NAMESPACE_REQUIRED"};
    if (!Array.isArray(envelope.events) || !envelope.events.length || envelope.events.length > MAX_EVENTS) {
      return {ok: false, error: "EVENT_COUNT_INVALID"};
    }
    if (bytes(envelope) > MAX_ENVELOPE_BYTES) return {ok: false, error: "ENVELOPE_TOO_LARGE"};
    if (!isSha256(envelope.envelopeSha256)) return {ok: false, error: "ENVELOPE_HASH_MISSING"};
    let previous = Number(envelope.fromAppendSequence || 0) - 1;
    for (const event of envelope.events) {
      const result = validateEvent(event, previous);
      if (!result.ok) return result;
      previous = result.append;
    }
    if (Number(envelope.events[0].appendSequence) !== Number(envelope.fromAppendSequence)) {
      return {ok: false, error: "FIRST_APPEND_MISMATCH"};
    }
    if (Number(envelope.events[envelope.events.length - 1].appendSequence) !== Number(envelope.toAppendSequence)) {
      return {ok: false, error: "LAST_APPEND_MISMATCH"};
    }
    if (envelope.manifest && envelope.manifest.exactContextComplete === true) {
      return {ok: false, error: "RENDERED_EGRESS_CANNOT_CLAIM_PROVIDER_NATIVE_EXACT"};
    }
    const copy = Object.assign({}, envelope);
    delete copy.envelopeSha256;
    const expected = await sha256(copy);
    if (expected !== String(envelope.envelopeSha256)) return {ok: false, error: "ENVELOPE_HASH_MISMATCH"};
    return {ok: true};
  }

  function normalizeNativeAck(nativeAck, envelope) {
    if (!nativeAck || nativeAck.ok !== true) {
      return {schema: ACK_SCHEMA, ok: false, state: String(nativeAck && nativeAck.state || "NATIVE_HOST_REJECTED")};
    }
    if (String(nativeAck.envelopeSha256 || "") !== String(envelope.envelopeSha256 || "")) {
      return {schema: ACK_SCHEMA, ok: false, state: "NATIVE_HOST_ACK_HASH_MISMATCH"};
    }
    if (Number(nativeAck.toAppendSequence || 0) !== Number(envelope.toAppendSequence || 0)) {
      return {schema: ACK_SCHEMA, ok: false, state: "NATIVE_HOST_ACK_SEQUENCE_MISMATCH"};
    }
    return {
      schema: ACK_SCHEMA,
      ok: true,
      state: "NATIVE_HOST_ACK_VERIFIED",
      receiptId: String(nativeAck.receiptId || ""),
      envelopeSha256: String(nativeAck.envelopeSha256 || ""),
      toAppendSequence: Number(nativeAck.toAppendSequence || 0),
      storedEncrypted: Boolean(nativeAck.storedEncrypted),
      observedAt: String(nativeAck.observedAt || "")
    };
  }

  return Object.freeze({
    EGRESS_SCHEMA,
    ACK_SCHEMA,
    CHATBRIDGE_EXTENSION_ID,
    EDGE_AGENT_EXTENSION_ID,
    NATIVE_HOST_NAME,
    MAX_EVENTS,
    MAX_ENVELOPE_BYTES,
    canonicalize,
    canonicalJson,
    sha256,
    validateEnvelope,
    normalizeNativeAck
  });
});
