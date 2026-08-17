"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const core = require("../src/bridge-core.js");

test("detects the current maximum-length warning", () => {
  assert.equal(core.isLimitNotice("You've reached the maximum length for this conversation, but you can keep talking by starting a new chat."), true);
  assert.equal(core.isLimitNotice("Ordinary response text about a long project."), false);
});

test("preserves the GPT/project route while removing the old conversation id", () => {
  assert.equal(
    core.deriveNewChatUrl("https://chatgpt.com/g/g-p-abc-truthgrid/c/old-id?model=x#tail"),
    "https://chatgpt.com/g/g-p-abc-truthgrid"
  );
  assert.equal(core.deriveNewChatUrl("https://chatgpt.com/c/old-id"), "https://chatgpt.com/");
});

test("parses exact conversation identity and refuses unbound routes", () => {
  assert.deepEqual(
    core.parseConversationIdentity("https://chatgpt.com/g/g-p-abc/c/6a7decb0?model=x"),
    {conversationKey: "6a7decb0", routeKey: "g/g-p-abc", origin: "https://chatgpt.com", bound: true}
  );
  assert.equal(core.parseConversationIdentity("https://chatgpt.com/").bound, false);
});

test("bounds the handoff transcript while preserving objective head and recent tail", () => {
  const messages = Array.from({length: 30}, (_, index) => ({index: index + 1, role: index % 2 ? "assistant" : "user", text: `message-${index + 1} ${"x".repeat(1000)}`}));
  const packed = core.boundMessages(messages, 9000);
  assert.equal(packed.messages[0].index, 1);
  assert.equal(packed.messages.at(-1).index, 30);
  assert.ok(packed.omittedMessageCount > 0);
});

test("does not collapse repeated identical turns", () => {
  const normalized = core.normalizeMessages([
    {role: "user", text: "n", sourceTurnId: "turn-1"},
    {role: "user", text: "n", sourceTurnId: "turn-2"}
  ]);
  assert.equal(normalized.length, 2);
  assert.notEqual(normalized[0].sourceTurnId, normalized[1].sourceTurnId);
});

test("builds a SHA-256-bound Alpha-Omega browser capture envelope", async () => {
  const envelope = await core.buildCaptureEnvelope({
    sourceUrl: "https://chatgpt.com/g/g-p-abc-truthgrid/c/conv-001",
    title: "TruthGrid",
    namespaceKey: "truthgrid-federation-canonicalisation",
    installationId: "browser-a",
    capturedAt: "2026-08-17T01:15:00Z",
    messages: [
      {role: "user", text: "start", sourceTurnId: "conversation-turn-1"},
      {role: "assistant", text: "middle", sourceTurnId: "conversation-turn-2"}
    ]
  });
  assert.equal(envelope.schema, core.CAPTURE_SCHEMA);
  assert.equal(envelope.source.conversation_key, "conv-001");
  assert.equal(envelope.capture_path.kind, "RENDERED_DOM");
  assert.equal(envelope.observations.length, 2);
  assert.equal(envelope.observations[0].global_sequence, 1);
  assert.match(envelope.snapshot.sha256, /^[0-9a-f]{64}$/);
  assert.equal(envelope.truth_boundary.exact_restore_from_this_path_alone, false);
  assert.equal(core.validateCaptureEnvelope(envelope), true);
});

test("delta capture is idempotent and appends a correction instead of rewriting history", async () => {
  const first = await core.buildCaptureEnvelope({
    sourceUrl: "https://chatgpt.com/c/conv-002",
    namespaceKey: "demo",
    installationId: "browser-a",
    capturedAt: "2026-08-17T01:15:00Z",
    messages: [
      {role: "user", text: "question", sourceTurnId: "turn-1"},
      {role: "assistant", text: "draft", sourceTurnId: "turn-2"}
    ]
  });
  const noChange = core.diffCaptureEnvelope(core.snapshotState(first), first);
  assert.equal(noChange.observations.length, 0);
  assert.equal(noChange.delta.unchanged_count, 2);

  const second = await core.buildCaptureEnvelope({
    sourceUrl: "https://chatgpt.com/c/conv-002",
    namespaceKey: "demo",
    installationId: "browser-a",
    capturedAt: "2026-08-17T01:16:00Z",
    previousSnapshotSha256: first.snapshot.sha256,
    messages: [
      {role: "user", text: "question", sourceTurnId: "turn-1"},
      {role: "assistant", text: "final", sourceTurnId: "turn-2"},
      {role: "user", text: "continue", sourceTurnId: "turn-3"}
    ]
  });
  const delta = core.diffCaptureEnvelope(core.snapshotState(first), second);
  assert.equal(delta.delta.added_count, 1);
  assert.equal(delta.delta.correction_count, 1);
  assert.equal(delta.observations[0].source_event_id, "turn:turn-3");
  assert.equal(delta.observations[1].event_type, "CORRECTION");
  assert.equal(delta.observations[1].metadata.correction_of_source_event_id, "turn:turn-2");
  assert.equal(delta.observations[1].global_sequence, null);
});

test("terminal warning is captured as not executed terminal intent", async () => {
  const envelope = await core.buildCaptureEnvelope({
    sourceUrl: "https://chatgpt.com/c/conv-terminal",
    namespaceKey: "demo",
    installationId: "browser-a",
    capturedAt: "2026-08-17T01:17:00Z",
    terminalObserved: true,
    terminalText: "You've reached the maximum length for this conversation.",
    messages: [{role: "user", text: "chatbridge - LEX", sourceTurnId: "turn-1"}]
  });
  const terminal = envelope.observations.at(-1);
  assert.equal(terminal.event_type, "TERMINAL_WARNING");
  assert.equal(terminal.execution_state, "NOT_EXECUTED_TERMINAL");
  assert.equal(terminal.metadata.terminal_intent_is_not_execution, true);
});

test("creates a compact actionable capsule with a full-fidelity capture pointer", () => {
  const capsule = core.buildCapsule({
    sourceUrl: "https://chatgpt.com/g/g-p-abc-truthgrid/c/old-id",
    title: "TruthGrid",
    capturedAt: "2026-08-17T01:18:00Z",
    messages: [{role: "user", text: "Continue the verified work.", sourceTurnId: "turn-1"}],
    captureReceipt: {state: "LOCAL_DURABLE_CAPTURED", captureId: "capture-1"},
    snapshotSha256: "a".repeat(64)
  });
  assert.equal(capsule.schema, core.HANDOFF_SCHEMA);
  assert.equal(capsule.source.conversationKey, "old-id");
  assert.match(capsule.continuity.truthRule, /UNVERIFIED/);
  assert.match(core.renderRestorePrompt(capsule), /FFCL \/ Alpha→Omega/);
});

test("pre-emption is deterministic", () => {
  assert.equal(core.shouldPreempt({estimatedRenderedTokens: 65000, renderedMessageCount: 1}, {}), true);
  assert.equal(core.shouldPreempt({estimatedRenderedTokens: 100, renderedMessageCount: 80}, {}), true);
  assert.equal(core.shouldPreempt({estimatedRenderedTokens: 100, renderedMessageCount: 2}, {}), false);
});
