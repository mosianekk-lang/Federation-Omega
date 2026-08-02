import assert from "node:assert/strict";
import test from "node:test";
import {
  HeartbeatBackendClient,
  type EmitInput,
  type IdentityTokenProvider,
} from "../src/backend.js";
import { testConfig } from "./helpers.js";

test("private backend call uses a Google ID token header and never forwards Authorization", async () => {
  const audiences: string[] = [];
  const identity: IdentityTokenProvider = {
    async getIdToken(audience) {
      audiences.push(audience);
      return "google-id-token";
    },
  };
  const calls: Array<{ url: string; init: RequestInit }> = [];
  const fetchImpl: typeof fetch = async (input, init) => {
    calls.push({ url: input.toString(), init: init ?? {} });
    return new Response(JSON.stringify({
      results: [{
        resource_id: "emitter/NODE-ROOT",
        resource_kind: "EMITTER",
        emitter_node_id: "NODE-ROOT",
        authority_ceiling: "A0",
        state_code: "REGISTERED",
        observed_at: "2026-08-02T22:00:00Z",
        semantic_hash: `sha256:${"a".repeat(64)}`,
      }],
      offset: 0,
      next_offset: null,
      total: 1,
    }), { status: 200, headers: { "content-type": "application/json" } });
  };
  const config = testConfig();
  const client = new HeartbeatBackendClient(config, identity, fetchImpl);

  const result = await client.search("NODE ROOT");
  assert.equal(result.results[0]?.id, "emitter/NODE-ROOT");
  assert.deepEqual(audiences, [config.backendAudience]);
  assert.equal(calls.length, 1);
  const headers = new Headers(calls[0]?.init.headers);
  assert.equal(headers.get("x-serverless-authorization"), "Bearer google-id-token");
  assert.equal(headers.get("x-evidenceops-internal-auth"), config.internalAuthValue);
  assert.equal(headers.has("authorization"), false);
  assert.equal(calls[0]?.url, "https://heartbeat-private.example.com/v1/search");
  assert.equal(calls[0]?.init.method, "POST");
  assert.deepEqual(JSON.parse(String(calls[0]?.init.body)), {
    resource_kind: "ALL",
    authority_ceiling: "A0",
    offset: 0,
    limit: 100,
  });
});

test("backend response limits fail closed", async () => {
  const identity: IdentityTokenProvider = { async getIdToken() { return "id-token"; } };
  const fetchImpl: typeof fetch = async () => new Response("{}", {
    status: 200,
    headers: { "content-length": "999" },
  });
  const client = new HeartbeatBackendClient(
    testConfig({ maxBackendResponseBytes: 100 }),
    identity,
    fetchImpl,
  );
  await assert.rejects(() => client.status(), /configured limit/);
});

test("emit uses canonical ingest then verified readback with exact snake-case body", async () => {
  const identity: IdentityTokenProvider = { async getIdToken() { return "id-token"; } };
  const calls: Array<{ url: string; init: RequestInit }> = [];
  const input: EmitInput = {
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
  const resourceId = `heartbeat/sha256:${"f".repeat(64)}`;
  const receiptId = `sha256:${"1".repeat(64)}`;
  const ingest = {
    resource_id: resourceId,
    idempotency_hash: input.idempotency_hash,
    envelope_id: `sha256:${"f".repeat(64)}`,
    receipt_id: receiptId,
    object_hash: `sha256:${"2".repeat(64)}`,
    authority_ceiling: "A0",
    created: true,
    replayed: false,
  };
  const readback = {
    schema: "EVIDENCEOPS-HEARTBEAT-READBACK-0.1",
    verified: true,
    resource_id: resourceId,
    idempotency_hash: input.idempotency_hash,
    envelope_id: ingest.envelope_id,
    receipt_id: receiptId,
    object_hash: ingest.object_hash,
    semantic_hash: `sha256:${"3".repeat(64)}`,
    authority_ceiling: "A0",
  };
  const fetchImpl: typeof fetch = async (request, init) => {
    calls.push({ url: request.toString(), init: init ?? {} });
    return new Response(JSON.stringify(request.toString().includes("/v1/ingest") ? ingest : readback), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
  const client = new HeartbeatBackendClient(testConfig(), identity, fetchImpl);

  const result = await client.emit(input);
  assert.deepEqual(result, { ingest, readback });
  assert.equal(calls[0]?.url, "https://heartbeat-private.example.com/v1/ingest");
  assert.equal(calls[0]?.init.method, "POST");
  assert.deepEqual(JSON.parse(String(calls[0]?.init.body)), input);
  assert.equal(
    calls[1]?.url,
    `https://heartbeat-private.example.com/v1/readback/${input.idempotency_hash}`,
  );
  assert.equal(calls[1]?.init.method, undefined);
  for (const call of calls) {
    const headers = new Headers(call.init.headers);
    assert.equal(headers.has("authorization"), false);
    assert.equal(headers.get("x-serverless-authorization"), "Bearer id-token");
  }
});

test("emit rejects every mismatched or missing proof-bound readback field", async () => {
  const identity: IdentityTokenProvider = { async getIdToken() { return "id-token"; } };
  const input: EmitInput = {
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
  const ingest = {
    resource_id: `heartbeat/sha256:${"f".repeat(64)}`,
    idempotency_hash: input.idempotency_hash,
    envelope_id: `sha256:${"f".repeat(64)}`,
    receipt_id: `sha256:${"1".repeat(64)}`,
    object_hash: `sha256:${"2".repeat(64)}`,
    authority_ceiling: "A0",
    created: true,
    replayed: false,
  };
  const readback = {
    schema: "EVIDENCEOPS-HEARTBEAT-READBACK-0.1",
    verified: true,
    resource_id: ingest.resource_id,
    idempotency_hash: ingest.idempotency_hash,
    envelope_id: ingest.envelope_id,
    receipt_id: ingest.receipt_id,
    object_hash: ingest.object_hash,
    semantic_hash: `sha256:${"3".repeat(64)}`,
    authority_ceiling: "A0",
  };
  const mismatches: Array<[keyof typeof readback, string]> = [
    ["resource_id", `heartbeat/sha256:${"9".repeat(64)}`],
    ["idempotency_hash", `sha256:${"8".repeat(64)}`],
    ["envelope_id", `sha256:${"7".repeat(64)}`],
    ["receipt_id", `sha256:${"6".repeat(64)}`],
    ["object_hash", `sha256:${"5".repeat(64)}`],
    ["authority_ceiling", "A1"],
  ];

  for (const [field, value] of mismatches) {
    let call = 0;
    const fetchImpl: typeof fetch = async () => {
      call += 1;
      return new Response(JSON.stringify(call === 1 ? ingest : { ...readback, [field]: value }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };
    const client = new HeartbeatBackendClient(testConfig(), identity, fetchImpl);
    await assert.rejects(() => client.emit(input));
  }

  let call = 0;
  const missingFetch: typeof fetch = async () => {
    call += 1;
    const incomplete = { ...readback } as Partial<typeof readback>;
    delete incomplete.object_hash;
    return new Response(JSON.stringify(call === 1 ? ingest : incomplete), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
  const client = new HeartbeatBackendClient(testConfig(), identity, missingFetch);
  await assert.rejects(() => client.emit(input));
});

test("status and fetch parse native API responses and adapt fetch to standard connector shape", async () => {
  const identity: IdentityTokenProvider = { async getIdToken() { return "id-token"; } };
  const resourceId = "emitter/NODE-ROOT";
  const nativeStatus = {
    schema: "EVIDENCEOPS-HEARTBEAT-API-STATUS-0.1",
    maturity: "IMPLEMENTED_NOT_DEPLOYED",
    authority_ceiling: "A0",
    recommendation_only: true,
    ready: true,
    readiness_reasons: [],
    registry_source_code: "ENVIRONMENT_INJECTED_RUNTIME",
    store: {
      healthy: true,
      backend_code: "MEMORY",
      durability_class: "PROCESS_MEMORY",
      object_count: 0,
    },
    authority: {},
    live_awareness_flags: { active_chat_inventory: false },
  };
  const nativeFetch = {
    resource: {
      schema: "EVIDENCEOPS-EMITTER-READ-MODEL-0.1",
      resource_id: resourceId,
      resource_kind: "EMITTER",
      node_id: "NODE-ROOT",
      authority_ceiling: "A0",
    },
    semantic_hash: `sha256:${"a".repeat(64)}`,
  };
  const fetchImpl: typeof fetch = async (request) => new Response(JSON.stringify(
    request.toString().endsWith("/v1/status") ? nativeStatus : nativeFetch,
  ), { status: 200, headers: { "content-type": "application/json" } });
  const client = new HeartbeatBackendClient(testConfig(), identity, fetchImpl);

  assert.deepEqual(await client.status(), nativeStatus);
  const fetched = await client.fetch(resourceId);
  assert.equal(fetched.id, resourceId);
  assert.equal(fetched.title, `EMITTER: ${resourceId}`);
  assert.equal(fetched.text, JSON.stringify({
    authority_ceiling: "A0",
    node_id: "NODE-ROOT",
    resource_id: resourceId,
    resource_kind: "EMITTER",
    schema: "EVIDENCEOPS-EMITTER-READ-MODEL-0.1",
  }));
  assert.equal(fetched.metadata.semantic_hash, nativeFetch.semantic_hash);
});
