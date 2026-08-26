import assert from "node:assert/strict";
import test from "node:test";
import { authenticate, AuthenticationError } from "../lib/auth.mjs";
import {
  ALLOWED_ACTIONS,
  CFRE_MANIFEST_SHA256,
  CFRE_REPAIR_SHA256,
  ContractError,
  sha256Hex,
  validateBindPayload,
  validateGeminiCapabilityPayload,
  validateGeminiSemanticPayload,
} from "../lib/contracts.mjs";
import { GoogleCloudAdapter } from "../lib/google_cloud.mjs";
import { executeAction } from "../lib/operator.mjs";

const env = {
  PROJECT_ID: "sov-hybrid-suite",
  REGION: "africa-south1",
  CFRE_PRIVATE_SERVICE: "cfre-omega-private-runtime",
  CFRE_RUNTIME_SERVICE_ACCOUNT: "fo-operator-sa@sov-hybrid-suite.iam.gserviceaccount.com",
  VERTEX_LOCATION: "global",
  GEMINI_MODEL: "gemini-2.5-flash",
  GEMINI_ALLOWED_MODELS: "gemini-2.5-flash",
  FEDERATION_TENANT_ID: "federation-omega",
};

const valid = {
  approvalKey: "APPROVED",
  project: "sov-hybrid-suite",
  region: "africa-south1",
  service: "cfre-omega-private-runtime",
  serviceAccount: "fo-operator-sa@sov-hybrid-suite.iam.gserviceaccount.com",
  sourceDriveId: "1abcdefghijklmnopqrstuvxyz",
  sourceSha256: "a".repeat(64),
  embeddedRepairSha256: CFRE_REPAIR_SHA256,
  manifestSha256: CFRE_MANIFEST_SHA256,
  idempotencyKey: "CFRE-BIND-aaaaaaaaaaaaaaaa",
};

test("allowlist restores the exact CFRE binding action", () => {
  assert.equal(ALLOWED_ACTIONS.includes("BIND_CFRE_PRIVATE_RUNTIME"), true);
});

test("allowlist exposes capability read and separately gated semantic canary", () => {
  assert.equal(ALLOWED_ACTIONS.includes("READ_GEMINI_VERTEX_CAPABILITY"), true);
  assert.equal(ALLOWED_ACTIONS.includes("VERIFY_GEMINI_VERTEX_SEMANTIC"), true);
});

test("Gemini capability contract is pinned to project, tenant, location and model", () => {
  assert.deepEqual(validateGeminiCapabilityPayload({}, env), {
    project: "sov-hybrid-suite",
    location: "global",
    model: "gemini-2.5-flash",
    tenantId: "federation-omega",
  });
  assert.throws(
    () => validateGeminiCapabilityPayload({ model: "gemini-unreviewed" }, env),
    (error) => error instanceof ContractError && error.code === "MODEL_NOT_ALLOWED",
  );
  assert.throws(
    () => validateGeminiCapabilityPayload({ tenantId: "other-tenant" }, env),
    /tenantId/,
  );
});

test("semantic canary remains disabled unless the operator environment enables it", () => {
  assert.throws(
    () => validateGeminiSemanticPayload({
      approvalKey: "APPROVED_SEMANTIC_CANARY",
      nonce: "FEDOMEGA-1234567890",
      idempotencyKey: "GEMINI-CANARY-123456",
    }, env),
    (error) => error instanceof ContractError && error.code === "SEMANTIC_CANARY_DISABLED",
  );
});

test("semantic contract accepts only the exact approval and bounded nonce", () => {
  const semanticEnv = { ...env, GEMINI_SEMANTIC_CANARY_ENABLED: "true" };
  assert.deepEqual(validateGeminiSemanticPayload({
    approvalKey: "APPROVED_SEMANTIC_CANARY",
    nonce: "FEDOMEGA-1234567890",
    idempotencyKey: "GEMINI-CANARY-123456",
  }, semanticEnv), {
    project: "sov-hybrid-suite",
    location: "global",
    model: "gemini-2.5-flash",
    tenantId: "federation-omega",
    approvalKey: "APPROVED_SEMANTIC_CANARY",
    nonce: "FEDOMEGA-1234567890",
    idempotencyKey: "GEMINI-CANARY-123456",
    maxOutputTokens: 64,
  });
  assert.throws(() => validateGeminiSemanticPayload({
    approvalKey: "APPROVED",
    nonce: "FEDOMEGA-1234567890",
    idempotencyKey: "GEMINI-CANARY-123456",
  }, semanticEnv), /approvalKey/);
});

test("bind contract accepts the exact target and pinned hashes", () => {
  assert.deepEqual(validateBindPayload(valid, env), { ...valid, dryRun: false });
});

test("bind contract rejects target drift", () => {
  assert.throws(() => validateBindPayload({ ...valid, project: "wrong" }, env), ContractError);
});

test("bind contract rejects repair-hash drift", () => {
  assert.throws(() => validateBindPayload({ ...valid, embeddedRepairSha256: "b".repeat(64) }, env), /embeddedRepairSha256/);
});

test("missing trusted authentication fails closed", async () => {
  await assert.rejects(() => authenticate({}, {}), AuthenticationError);
});

test("Secret Manager token remains a compatible trusted route", async () => {
  assert.deepEqual(await authenticate({ "x-fo-admin-token": "secret" }, { ADMIN_TOKEN: "secret" }), { mode: "SECRET_MANAGER_TOKEN", principal: "fo-admin-token" });
});

test("dry-run bind verifies semantics without invoking provider mutation", async () => {
  let called = false;
  const result = await executeAction({ action: "BIND_CFRE_PRIVATE_RUNTIME", payload: { ...valid, dryRun: true }, principal: { mode: "TEST", principal: "test" }, env, adapter: { async bindCfrePrivateRuntime() { called = true; } } });
  assert.equal(result.body.status, "CFRE_BIND_PLAN_VERIFIED");
  assert.equal(result.body.mutationAttempted, false);
  assert.equal(called, false);
});

test("live bind delegates only after exact contract validation", async () => {
  const adapter = { async bindCfrePrivateRuntime(binding) { return { ok: true, status: "CFRE_PRIVATE_RUNTIME_BOUND", binding }; } };
  const result = await executeAction({ action: "BIND_CFRE_PRIVATE_RUNTIME", payload: valid, principal: { mode: "TEST", principal: "test" }, env, adapter });
  assert.equal(result.body.status, "CFRE_PRIVATE_RUNTIME_BOUND");
  assert.equal(result.body.binding.embeddedRepairSha256, CFRE_REPAIR_SHA256);
});

test("unknown actions remain fail-closed", async () => {
  const result = await executeAction({ action: "DEPLOY_ANYTHING", payload: {}, principal: { mode: "TEST", principal: "test" }, env, adapter: {} });
  assert.equal(result.httpStatus, 400);
  assert.equal(result.body.status, "ACTION_NOT_ALLOWED");
});

test("capability action delegates only after contract validation", async () => {
  let observed;
  const adapter = {
    async readGeminiVertexCapability(target) {
      observed = target;
      return { ok: true, status: "GEMINI_VERTEX_CAPABILITY_READ", target };
    },
  };
  const result = await executeAction({
    action: "READ_GEMINI_VERTEX_CAPABILITY",
    payload: {},
    principal: { mode: "TEST", principal: "test" },
    env,
    adapter,
  });
  assert.equal(result.body.status, "GEMINI_VERTEX_CAPABILITY_READ");
  assert.deepEqual(observed, validateGeminiCapabilityPayload({}, env));
});

test("capability read proves service and publisher model without inference", async () => {
  const calls = [];
  const adapter = new GoogleCloudAdapter({});
  adapter.api = async (url) => {
    calls.push(url);
    if (url.includes("serviceusage.googleapis.com")) {
      return { status: 200, body: { state: "ENABLED" } };
    }
    return { status: 200, body: {
      name: "publishers/google/models/gemini-2.5-flash",
      versionId: "stable",
      displayName: "Gemini 2.5 Flash",
      launchStage: "GA",
      supportedActions: ["generateContent"],
    } };
  };
  const result = await adapter.readGeminiVertexCapability(validateGeminiCapabilityPayload({}, env));
  assert.equal(result.status, "GEMINI_VERTEX_CAPABILITY_READ");
  assert.equal(result.semanticExecutionAttempted, false);
  assert.equal(result.incrementalCost, 0);
  assert.equal(result.silentFallback, false);
  assert.equal(calls.length, 2);
  assert.match(calls[0], /aiplatform\.googleapis\.com$/);
  assert.match(calls[1], /locations\/global\/publishers\/google\/models\/gemini-2\.5-flash$/);
});

test("disabled Vertex service stops before publisher model read", async () => {
  let calls = 0;
  const adapter = new GoogleCloudAdapter({});
  adapter.api = async () => {
    calls += 1;
    return { status: 200, body: { state: "DISABLED" } };
  };
  const result = await adapter.readGeminiVertexCapability(validateGeminiCapabilityPayload({}, env));
  assert.equal(result.status, "VERTEX_AI_API_DISABLED");
  assert.equal(result.semanticExecutionAttempted, false);
  assert.equal(calls, 1);
});

test("semantic action never reaches provider while its environment gate is closed", async () => {
  let called = false;
  await assert.rejects(
    async () => executeAction({
      action: "VERIFY_GEMINI_VERTEX_SEMANTIC",
      payload: {
        approvalKey: "APPROVED_SEMANTIC_CANARY",
        nonce: "FEDOMEGA-1234567890",
        idempotencyKey: "GEMINI-CANARY-123456",
      },
      principal: { mode: "TEST", principal: "test" },
      env,
      adapter: { async verifyGeminiVertexSemantic() { called = true; } },
    }),
    /disabled/,
  );
  assert.equal(called, false);
});

test("semantic canary accepts only exact nonce readback and reports usage", async () => {
  const canary = validateGeminiSemanticPayload({
    approvalKey: "APPROVED_SEMANTIC_CANARY",
    nonce: "FEDOMEGA-1234567890",
    idempotencyKey: "GEMINI-CANARY-123456",
  }, { ...env, GEMINI_SEMANTIC_CANARY_ENABLED: "true" });
  const adapter = new GoogleCloudAdapter({});
  adapter.readGeminiVertexCapability = async () => ({ ok: true, status: "GEMINI_VERTEX_CAPABILITY_READ" });
  adapter.api = async (url, options) => {
    assert.match(url, /:generateContent$/);
    const request = JSON.parse(options.body);
    assert.equal(request.generationConfig.candidateCount, 1);
    assert.equal(request.generationConfig.maxOutputTokens, 64);
    return { status: 200, body: {
      candidates: [{ content: { parts: [{ text: canary.nonce }] } }],
      usageMetadata: { promptTokenCount: 12, candidatesTokenCount: 5, totalTokenCount: 17 },
    } };
  };
  const result = await adapter.verifyGeminiVertexSemantic(canary);
  assert.equal(result.status, "GEMINI_VERTEX_SEMANTIC_VERIFIED");
  assert.equal(result.nonceVerified, true);
  assert.equal(result.usage.totalTokenCount, 17);
  assert.equal(result.silentFallback, false);
});

test("semantic nonce mismatch fails closed without a fallback model", async () => {
  const canary = validateGeminiSemanticPayload({
    approvalKey: "APPROVED_SEMANTIC_CANARY",
    nonce: "FEDOMEGA-1234567890",
    idempotencyKey: "GEMINI-CANARY-123456",
  }, { ...env, GEMINI_SEMANTIC_CANARY_ENABLED: "true" });
  const adapter = new GoogleCloudAdapter({});
  adapter.readGeminiVertexCapability = async () => ({ ok: true, status: "GEMINI_VERTEX_CAPABILITY_READ" });
  adapter.api = async () => ({ status: 200, body: {
    candidates: [{ content: { parts: [{ text: "wrong-value" }] } }],
  } });
  await assert.rejects(() => adapter.verifyGeminiVertexSemantic(canary), /nonce mismatch/);
});

test("provider adapter rejects a Drive hash mismatch before any mutation", async () => {
  const adapter = new GoogleCloudAdapter({});
  let mutated = false;
  adapter.downloadDriveFile = async () => Buffer.from("wrong bundle");
  adapter.stageSource = async () => { mutated = true; };
  await assert.rejects(() => adapter.bindCfrePrivateRuntime({ ...valid, sourceSha256: "f".repeat(64) }), /source hash mismatch/);
  assert.equal(mutated, false);
});

test("provider adapter completes the exact stage-build-deploy transaction", async () => {
  const bytes = Buffer.from("verified deployment envelope");
  const binding = { ...valid, sourceSha256: sha256Hex(bytes) };
  const order = [];
  const adapter = new GoogleCloudAdapter({});
  adapter.downloadDriveFile = async () => { order.push("download"); return bytes; };
  adapter.stageSource = async () => { order.push("stage"); return { bucket: "bucket", object: "object", generation: "1" }; };
  adapter.submitBuild = async () => { order.push("submit"); return { buildId: "build-1", image: "image@sha256:digest" }; };
  adapter.waitBuild = async () => { order.push("wait"); return { id: "build-1", status: "SUCCESS" }; };
  adapter.deployPrivateService = async () => { order.push("deploy"); return { before: { latestReadyRevision: "old" }, after: { latestReadyRevision: "new" } }; };
  const result = await adapter.bindCfrePrivateRuntime(binding);
  assert.deepEqual(order, ["download", "stage", "submit", "wait", "deploy"]);
  assert.equal(result.status, "CFRE_PRIVATE_RUNTIME_BOUND");
  assert.equal(result.sourceSha256, binding.sourceSha256);
  assert.equal(result.build.status, "SUCCESS");
});
