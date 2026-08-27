"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const protocol = require("../src/protocol.js");

async function envelope(overrides) {
  const value = {
    schema: protocol.EGRESS_SCHEMA,
    version: "1.0",
    conversationKey: "chat-1",
    namespaceKey: "sovara",
    source: {
      provider: "CHATGPT_RENDERED_DOM",
      pathId: "rendered-dom-companion",
      independentGroup: "browser-rendered-dom",
      title: "Example",
      urlSha256: "a".repeat(64)
    },
    fromAppendSequence: 1,
    toAppendSequence: 1,
    events: [{
      eventId: "e1",
      appendSequence: 1,
      sourceSequence: 1,
      sourceMessageId: "m1",
      role: "user",
      stream: "USER",
      eventType: "MESSAGE",
      content: "hello",
      occurredAt: "",
      capturedAt: "2026-08-27T00:00:00Z",
      executionState: "OBSERVED",
      payloadAvailability: "RAW_GOVERNED",
      sensitivity: "GOVERNED_LOCAL",
      artifacts: [{
        artifactKey: "a1",
        filename: "x.txt",
        mimeType: "text/plain",
        locator: "https://example.com/x.txt",
        locatorSha256: "b".repeat(64),
        availability: "POINTER_ONLY",
        requiredForContext: false,
        sourceProvider: "CHATGPT_RENDERED_DOM"
      }],
      contentHash: "c".repeat(64),
      previousEventHash: "",
      supersedesEventId: "",
      pathId: "rendered-dom-companion",
      providerReadback: "BROWSER_RENDERED_DOM_OBSERVATION",
      eventHash: "d".repeat(64)
    }],
    manifest: {
      restoreMode: "EXACT_SINGLE_PATH_TRANSCRIPT_RESTORE",
      integrityState: "HASH_CHAIN_VERIFIED",
      coverageState: "COMPLETE_RENDERED_MESSAGE_RANGE",
      providerCompleteness: "RENDERED_DOM_ONLY_NOT_HIDDEN_NATIVE_EVENTS",
      exactRenderedTranscriptComplete: true,
      exactContextComplete: false,
      firstSourceSequence: 1,
      lastSourceSequence: 1,
      capturedEventCount: 1,
      latestRenderedMessageCount: 1,
      missingRanges: [],
      unresolvedArtifacts: [],
      chainHeadSha256: "d".repeat(64),
      terminalObserved: false,
      truthBoundary: "Rendered only"
    },
    reason: "CAPTURE",
    createdAt: "2026-08-27T00:00:00Z"
  };
  Object.assign(value, overrides || {});
  const copy = Object.assign({}, value);
  delete copy.envelopeSha256;
  value.envelopeSha256 = await protocol.sha256(copy);
  return value;
}

test("stable extension identities are fixed", () => {
  assert.equal(protocol.CHATBRIDGE_EXTENSION_ID, "kacbginamagliaddmlkffhcadpamomjb");
  assert.equal(protocol.EDGE_AGENT_EXTENSION_ID, "apokbhjjgiaceigelkedcelcecfmgnia");
  assert.equal(protocol.NATIVE_HOST_NAME, "com.sovara.bef_edge");
});

test("valid rendered provenance envelope passes", async () => {
  const value = await envelope();
  assert.deepEqual(await protocol.validateEnvelope(value), {ok: true});
});

test("rendered envelope cannot claim provider-native exact", async () => {
  const value = await envelope();
  value.manifest.exactContextComplete = true;
  const copy = Object.assign({}, value);
  delete copy.envelopeSha256;
  value.envelopeSha256 = await protocol.sha256(copy);
  const result = await protocol.validateEnvelope(value);
  assert.equal(result.ok, false);
  assert.equal(result.error, "RENDERED_EGRESS_CANNOT_CLAIM_PROVIDER_NATIVE_EXACT");
});

test("signed or tokenized artifact URLs are stripped before the edge agent", async () => {
  const value = await envelope();
  value.events[0].artifacts[0].locator = "https://example.com/x?token=secret";
  const copy = Object.assign({}, value);
  delete copy.envelopeSha256;
  value.envelopeSha256 = await protocol.sha256(copy);
  const result = await protocol.validateEnvelope(value);
  assert.equal(result.ok, false);
  assert.equal(result.error, "ARTIFACT_LOCATOR_NOT_REDACTED");
});

test("envelope hash tamper fails", async () => {
  const value = await envelope();
  value.events[0].content = "changed after hash";
  const result = await protocol.validateEnvelope(value);
  assert.equal(result.ok, false);
  assert.equal(result.error, "ENVELOPE_HASH_MISMATCH");
});

test("native ack is bound to hash and append sequence", async () => {
  const value = await envelope();
  const ack = protocol.normalizeNativeAck({
    ok: true,
    receiptId: "r1",
    envelopeSha256: value.envelopeSha256,
    toAppendSequence: 1,
    storedEncrypted: true,
    observedAt: "2026-08-27T00:00:01Z"
  }, value);
  assert.equal(ack.ok, true);
  assert.equal(ack.state, "NATIVE_HOST_ACK_VERIFIED");
  const bad = protocol.normalizeNativeAck({
    ok: true,
    receiptId: "r1",
    envelopeSha256: "f".repeat(64),
    toAppendSequence: 1
  }, value);
  assert.equal(bad.ok, false);
  assert.equal(bad.state, "NATIVE_HOST_ACK_HASH_MISMATCH");
});
