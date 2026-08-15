"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const core = require("../src/bridge-core.js");

test("detects the current maximum-length warning", () => {
  assert.equal(core.isLimitNotice("You've reached the maximum length for this conversation, but you can keep talking by starting a new chat."), true);
  assert.equal(core.isLimitNotice("Ordinary response text about a long project."), false);
});

test("preserves the GPT or project route while removing the old conversation id", () => {
  assert.equal(
    core.deriveNewChatUrl("https://chatgpt.com/g/g-p-abc-truthgrid/c/old-id?model=x#tail"),
    "https://chatgpt.com/g/g-p-abc-truthgrid"
  );
  assert.equal(core.deriveNewChatUrl("https://chatgpt.com/c/old-id"), "https://chatgpt.com/");
});

test("bounds the transcript while preserving objective head and recent tail", () => {
  const messages = Array.from({length: 30}, (_, index) => ({index: index + 1, role: index % 2 ? "assistant" : "user", text: `message-${index + 1} ${"x".repeat(1000)}`}));
  const packed = core.boundMessages(messages, 9000);
  assert.equal(packed.messages[0].index, 1);
  assert.equal(packed.messages.at(-1).index, 30);
  assert.ok(packed.omittedMessageCount > 0);
});

test("creates an actionable, source-bound capsule", () => {
  const capsule = core.buildCapsule({
    sourceUrl: "https://chatgpt.com/g/g-p-abc-truthgrid/c/old-id",
    title: "TruthGrid",
    capturedAt: "2026-08-14T21:00:00Z",
    messages: [{role: "user", text: "Continue the verified work."}]
  });
  assert.equal(capsule.schema, "CHATBRIDGE-HANDOFF-CAPSULE-1");
  assert.equal(capsule.source.successorUrl, "https://chatgpt.com/g/g-p-abc-truthgrid");
  assert.match(capsule.continuity.truthRule, /UNVERIFIED/);
  assert.match(core.renderRestorePrompt(capsule), /CHATBRIDGE RESTORE — SUCCESSOR CHAT/);
});

test("pre-emption is deterministic", () => {
  assert.equal(core.shouldPreempt({estimatedRenderedTokens: 65000, renderedMessageCount: 1}, {}), true);
  assert.equal(core.shouldPreempt({estimatedRenderedTokens: 100, renderedMessageCount: 80}, {}), true);
  assert.equal(core.shouldPreempt({estimatedRenderedTokens: 100, renderedMessageCount: 2}, {}), false);
});
