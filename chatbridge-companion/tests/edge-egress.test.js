"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const egress = require("../src/edge-egress.js");

function event(n, artifact) {
  return {
    eventId: `e${n}`,
    appendSequence: n,
    sourceSequence: n,
    sourceMessageId: `m${n}`,
    role: "user",
    stream: "USER",
    eventType: "MESSAGE",
    content: `message ${n}`,
    occurredAt: "",
    capturedAt: "2026-08-27T00:00:00Z",
    executionState: "OBSERVED",
    payloadAvailability: "RAW_GOVERNED",
    sensitivity: "GOVERNED_LOCAL",
    artifacts: artifact ? [artifact] : [],
    contentHash: "a".repeat(64),
    previousEventHash: n === 1 ? "" : "b".repeat(64),
    supersedesEventId: "",
    pathId: "rendered-dom-companion",
    providerReadback: "BROWSER_RENDERED_DOM_OBSERVATION",
    eventHash: "c".repeat(64)
  };
}

function ledger(events) {
  return {
    conversationKey: "chat-1",
    namespaceKey: "sovara",
    source: {
      provider: "CHATGPT_RENDERED_DOM",
      pathId: "rendered-dom-companion",
      independentGroup: "browser-rendered-dom",
      url: "https://chatgpt.com/c/secret-conversation-id?foo=bar",
      title: "Design chat"
    },
    events,
    manifest: {
      restoreMode: "EXACT_SINGLE_PATH_TRANSCRIPT_RESTORE",
      integrityState: "HASH_CHAIN_VERIFIED",
      coverageState: "COMPLETE_RENDERED_MESSAGE_RANGE",
      providerCompleteness: "RENDERED_DOM_ONLY_NOT_HIDDEN_NATIVE_EVENTS",
      exactRenderedTranscriptComplete: true,
      exactContextComplete: false,
      firstSourceSequence: 1,
      lastSourceSequence: events.length,
      capturedEventCount: events.length,
      latestRenderedMessageCount: events.length,
      missingRanges: [],
      unresolvedArtifacts: [],
      chainHeadSha256: "c".repeat(64),
      terminalObserved: false,
      truthBoundary: "Rendered browser messages only"
    }
  };
}

test("signed artifact locator is reduced to origin/path and separately hashed", async () => {
  const artifact = await egress.sanitizeArtifact({
    artifactKey: "a1",
    filename: "evidence.pdf",
    mimeType: "application/pdf",
    locator: "https://files.example/evidence.pdf?X-Signed=secret#fragment",
    availability: "POINTER_ONLY",
    requiredForContext: true,
    sourceProvider: "CHATGPT_RENDERED_DOM"
  });
  assert.equal(artifact.locator, "https://files.example/evidence.pdf");
  assert.match(artifact.locatorSha256, /^[a-f0-9]{64}$/);
  assert.equal(artifact.locator.includes("secret"), false);
});

test("delta envelope hashes source URL instead of exporting it", async () => {
  const value = await egress.buildEnvelope(ledger([event(1)]), [event(1)], "CAPTURE");
  assert.equal(value.source.url, undefined);
  assert.match(value.source.urlSha256, /^[a-f0-9]{64}$/);
  assert.match(value.envelopeSha256, /^[a-f0-9]{64}$/);
  assert.equal(value.manifest.exactRenderedTranscriptComplete, true);
  assert.equal(value.manifest.exactContextComplete, false);
});

test("chunking preserves event order and bounded batch count", () => {
  const rows = Array.from({length: 5}, (_, i) => event(i + 1));
  const chunks = egress.chunkEvents(rows, 2, 700000);
  assert.deepEqual(chunks.map((chunk) => chunk.map((row) => row.appendSequence)), [[1, 2], [3, 4], [5]]);
});

test("flush without browser runtime fails closed and keeps raw ledger untouched", async () => {
  const value = ledger([event(1)]);
  const before = JSON.stringify(value);
  const result = await egress.flushLedger(value, {reason: "TEST"});
  assert.equal(result.ok, false);
  assert.equal(result.state, "EDGE_AGENT_UNAVAILABLE");
  assert.equal(JSON.stringify(value), before);
});
