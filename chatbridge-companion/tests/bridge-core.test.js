"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const core = require("../src/bridge-core.js");

test("detects current maximum-length and weighted-token warnings", () => {
  assert.equal(core.isLimitNotice("You've reached the maximum length for this conversation, but you can keep talking by starting a new chat."), true);
  assert.equal(core.isLimitNotice("You've hit max weighted tokens for this chat"), true);
  assert.equal(core.isLimitNotice("Maximum weighted tokens for this chat"), true);
  assert.equal(core.isLimitNotice("weighted token limit"), true);
  assert.equal(core.isLimitNotice("Ordinary response text about a long project."), false);
});

test("preserves the project route and extracts exact conversation identity", () => {
  assert.equal(
    core.deriveNewChatUrl("https://chatgpt.com/g/g-p-abc-truthgrid/c/old-id?model=x#tail"),
    "https://chatgpt.com/g/g-p-abc-truthgrid"
  );
  assert.equal(core.deriveConversationKey("https://chatgpt.com/g/g-p-abc-truthgrid/c/old-id"), "old-id");
});

test("builds an exact source-bound capture packet", () => {
  const packet = core.buildCapturePacket({
    sourceUrl: "https://chatgpt.com/g/g-p-abc-truthgrid/c/old-id",
    title: "TruthGrid",
    capturedAt: "2026-08-17T02:00:00Z",
    messages: [{sourceSequence: 1, sourceMessageId: "m1", role: "user", stream: "USER", eventType: "MESSAGE", text: "Continue the verified work.", artifacts: []}]
  });
  assert.equal(packet.schema, core.PACKET_SCHEMA);
  assert.equal(packet.conversationKey, "old-id");
  assert.equal(packet.source.successorUrl, "https://chatgpt.com/g/g-p-abc-truthgrid");
  assert.equal(packet.observations.length, 1);
});

test("SHA-256 and canonical JSON are deterministic", async () => {
  const first = await core.sha256({b: 2, a: 1});
  const second = await core.sha256({a: 1, b: 2});
  assert.equal(first, second);
  assert.equal(first.length, 64);
});

test("reports exact missing ranges", () => {
  assert.deepEqual(core.missingRanges([1, 2, 5, 8], 1, 8), [[3, 4], [6, 7]]);
});

test("builds sequence-preserving bounded replay packets", () => {
  const ledger = {
    conversationKey: "old-id",
    namespaceKey: "truthgrid",
    manifest: {restoreMode: "EXACT_SINGLE_PATH_TRANSCRIPT_RESTORE", integrityState: "HASH_CHAIN_VERIFIED"},
    events: [
      {eventId: "e1", appendSequence: 1, sourceSequence: 1, sourceMessageId: "m1", eventType: "MESSAGE", role: "user", content: "A".repeat(7000)},
      {eventId: "e2", appendSequence: 2, sourceSequence: 2, sourceMessageId: "m2", eventType: "MESSAGE", role: "assistant", content: "B".repeat(7000)}
    ]
  };
  const prompts = core.buildReplayPrompts(ledger, 12000);
  assert.ok(prompts.length >= 3);
  assert.match(prompts[0].text, /Source conversation: old-id/);
  assert.match(prompts.at(-1).text, /FINAL CHATBRIDGE/);
});

test("pre-emption is deterministic", () => {
  assert.equal(core.shouldPreempt({estimatedRenderedTokens: 65000, renderedMessageCount: 1}, {}), true);
  assert.equal(core.shouldPreempt({estimatedRenderedTokens: 100, renderedMessageCount: 80}, {}), true);
  assert.equal(core.shouldPreempt({estimatedRenderedTokens: 100, renderedMessageCount: 2}, {}), false);
});

test("automatic handoff is mandatory for pre-limit pressure or a terminal notice", () => {
  assert.equal(core.shouldAutoHandoff({metrics: {estimatedRenderedTokens: 65000, renderedMessageCount: 1}}, {}), true);
  assert.equal(core.shouldAutoHandoff({metrics: {estimatedRenderedTokens: 100, renderedMessageCount: 2}, terminalNotice: "You've hit max weighted tokens for this chat"}, {}), true);
  assert.equal(core.shouldAutoHandoff({metrics: {estimatedRenderedTokens: 100, renderedMessageCount: 2}, terminalNotice: ""}, {}), false);
});

test("capacity-safe restore keeps full history external and sends only a bounded recent working set", () => {
  const events = [];
  for (let i = 1; i <= 100; i += 1) {
    events.push({
      eventId: "e" + i,
      appendSequence: i,
      sourceSequence: i,
      sourceMessageId: "m" + i,
      eventType: "MESSAGE",
      role: i % 2 ? "user" : "assistant",
      content: "turn-" + i + "-" + "X".repeat(900)
    });
  }
  const ledger = {
    conversationKey: "capacity-old",
    namespaceKey: "fuse-chat-capacity-continuity",
    manifest: {
      restoreMode: "EXACT_SINGLE_PATH_TRANSCRIPT_RESTORE",
      integrityState: "HASH_CHAIN_VERIFIED",
      coverageState: "COMPLETE_RENDERED_MESSAGE_RANGE",
      firstSourceSequence: 1,
      lastSourceSequence: 100,
      capturedEventCount: 100,
      chainHeadSha256: "a".repeat(64),
      terminalObserved: true,
      missingRanges: [],
      unresolvedArtifacts: []
    },
    events
  };
  const prompts = core.buildWorkingSetPrompts(ledger, {maxChars: 12000, maxEvents: 8});
  assert.equal(prompts.length, 1);
  assert.ok(prompts[0].text.length <= 12000);
  assert.match(prompts[0].text, /CAPACITY-SAFE WORKING-SET RESTORE/);
  assert.match(prompts[0].text, /full rendered transcript remains in the governed external ledger/i);
  assert.match(prompts[0].text, /turn-100-/);
  assert.doesNotMatch(prompts[0].text, /turn-1-/);
  assert.match(prompts[0].text, /ARCHIVE MANIFEST/);
});


test("weighted-pressure reserve preempts before owner-visible terminal limit", () => {
  const metrics = {estimatedRenderedTokens: 26000, renderedMessageCount: 20, requiredArtifactCount: 0};
  assert.equal(core.estimateWeightedPressure(metrics, {}), 45920);
  assert.equal(core.shouldPreempt(metrics, {}), false);
  assert.equal(core.shouldPreempt({...metrics, estimatedRenderedTokens: 26100}, {}), true);
  assert.equal(core.shouldAutoHandoff({metrics: {...metrics, estimatedRenderedTokens: 26100}, terminalNotice: ""}, {}), true);
});
