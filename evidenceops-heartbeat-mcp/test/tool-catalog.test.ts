import assert from "node:assert/strict";
import test from "node:test";
import { emitInputSchema } from "../src/backend.js";
import {
  TOOL_POLICIES,
  fetchInputSchema,
  requiredScopeForBody,
  searchInputSchema,
} from "../src/tool-catalog.js";

test("tool boundary is exactly three read tools and one effectful metadata-only tool", () => {
  assert.deepEqual(Object.keys(TOOL_POLICIES).sort(), [
    "fetch",
    "heartbeat_emit",
    "heartbeat_status",
    "search",
  ]);
  assert.equal(TOOL_POLICIES.heartbeat_emit.effectful, true);
  assert.equal(TOOL_POLICIES.heartbeat_emit.readOnly, false);
  assert.equal(TOOL_POLICIES.search.readOnly, true);
  assert.equal(TOOL_POLICIES.fetch.readOnly, true);
  assert.equal(TOOL_POLICIES.heartbeat_status.readOnly, true);
});

test("metadata emit rejects arbitrary payload or evidence content", () => {
  const base = {
    idempotency_hash: `sha256:${"a".repeat(64)}`,
    trace_id: `sha256:${"b".repeat(64)}`,
    root_transaction_id: `sha256:${"c".repeat(64)}`,
    mission_code: "MISSION-A1B2C3D4",
    emitter_node_id: "NODE-ROOT",
    authority_ceiling: "A0",
    state: "NEEDS_CAPABILITY",
    observed_at: "2026-08-02T22:00:00Z",
    expires_at: "2026-08-02T22:05:00Z",
    sequence: 1,
    observations: [{
      source_code: "LOCAL_REPO",
      node_id: "NODE-ROOT",
      capability_code: "CAP-INDEX",
      status: "AVAILABLE",
      confidence_bp: 9000,
      freshness_seconds: 1,
      evidence_count: 3,
      blocker_code: "NONE",
      capability_hash: `sha256:${"d".repeat(64)}`,
      observed_at: "2026-08-02T22:00:00Z",
      semantic_receipt: `sha256:${"e".repeat(64)}`,
    }],
  };
  assert.equal(emitInputSchema.safeParse(base).success, true);
  assert.equal(emitInputSchema.safeParse({ ...base, payload: "document content" }).success, false);
  assert.equal(emitInputSchema.safeParse({ ...base, observations: [] }).success, false);
});

test("search and fetch accept only bounded metadata identifiers", () => {
  assert.equal(searchInputSchema.safeParse({ query: "NODE-ROOT heartbeat" }).success, true);
  assert.equal(searchInputSchema.safeParse({ query: "person@example.com" }).success, false);
  assert.equal(searchInputSchema.safeParse({ query: "-" }).success, false);
  assert.equal(searchInputSchema.safeParse({ query: "x".repeat(161) }).success, false);
  assert.equal(fetchInputSchema.safeParse({ id: "emitter/NODE-ROOT" }).success, true);
  assert.equal(
    fetchInputSchema.safeParse({ id: `heartbeat/sha256:${"a".repeat(64)}` }).success,
    true,
  );
  assert.equal(fetchInputSchema.safeParse({ id: "https://unexpected.example/item" }).success, false);
});

test("per-tool scope resolution fails closed at the effect boundary", () => {
  assert.equal(requiredScopeForBody({
    method: "tools/call",
    params: { name: "heartbeat_emit" },
  }), "heartbeat:emit");
  assert.equal(requiredScopeForBody({
    method: "tools/call",
    params: { name: "search" },
  }), "heartbeat:read");
  assert.equal(requiredScopeForBody({ method: "tools/list" }), undefined);
});
