import assert from "node:assert/strict";
import test from "node:test";
import { authenticate, AuthenticationError } from "../lib/auth.mjs";
import { ALLOWED_ACTIONS, CFRE_MANIFEST_SHA256, CFRE_REPAIR_SHA256, ContractError, sha256Hex, validateBindPayload } from "../lib/contracts.mjs";
import { GoogleCloudAdapter } from "../lib/google_cloud.mjs";
import { executeAction } from "../lib/operator.mjs";

const env = {
  PROJECT_ID: "sov-hybrid-suite",
  REGION: "africa-south1",
  CFRE_PRIVATE_SERVICE: "cfre-omega-private-runtime",
  CFRE_RUNTIME_SERVICE_ACCOUNT: "fo-operator-sa@sov-hybrid-suite.iam.gserviceaccount.com",
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
