import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const cloudbuild = fs.readFileSync(new URL("../cloudbuild.v022.yaml", import.meta.url), "utf8");
const verifyWorkflow = fs.readFileSync(new URL("../.github/workflows/verify-gcp-admin-mcp-v022.yml", import.meta.url), "utf8");
const releaseWorkflow = fs.readFileSync(new URL("../.github/workflows/release-gcp-admin-mcp-v022.yml", import.meta.url), "utf8");

test("v0.2.2 distinguishes NOT_FOUND and proves rollback or absence", () => {
  assert.match(cloudbuild, /PRIOR_SERVICE_STATE_UNRESOLVED/);
  assert.match(cloudbuild, /NOT_FOUND\|not found\|does not exist/);
  assert.match(cloudbuild, /AUTOMATIC_TRAFFIC_RESTORATION_READBACK_MISMATCH/);
  assert.match(cloudbuild, /AUTOMATIC_NEW_SERVICE_REMOVAL_READBACK_FAILED/);
  assert.match(cloudbuild, /RESTORED_TRAFFIC_NOT_EXACTLY_100/);
});

test("v0.2.2 requires a serialized release fence and exact immutable digest", () => {
  assert.match(cloudbuild, /RELEASE_FENCE_INVALID/);
  assert.match(cloudbuild, /\^sha256:\[0-9a-f\]\{64\}\$/);
  assert.match(releaseWorkflow, /concurrency:/);
  assert.match(releaseWorkflow, /cancel-in-progress: false/);
  assert.match(releaseWorkflow, /cloudbuild\.v022\.yaml/);
});

test("v0.2.2 proves private posture independently of authenticated health", () => {
  assert.match(cloudbuild, /UNAUTHENTICATED_CANARY_NOT_REJECTED/);
  assert.match(cloudbuild, /PUBLIC_CLOUD_RUN_IAM_BINDING/);
  assert.match(cloudbuild, /MCP_LINEAGE_PRIVATE_IAM_NOT_PROVEN/);
});

test("public source carries secret references, not Apps Script identifiers", () => {
  assert.match(cloudbuild, /ALLOWED_SCRIPT_IDS=federation-omega-allowed-script-ids:latest/);
  assert.doesNotMatch(cloudbuild, /ALLOWED_SCRIPT_IDS=1[A-Za-z0-9_-]{20,}/);
});

test("GitHub routes are pinned, separated and dormant by default", () => {
  assert.match(verifyWorkflow, /permissions:\n  contents: read/);
  assert.doesNotMatch(verifyWorkflow, /id-token: write/);
  assert.match(releaseWorkflow, /workflow_dispatch:/);
  assert.doesNotMatch(releaseWorkflow, /\bpush:/);
  assert.doesNotMatch(releaseWorkflow, /pull_request:/);
  for (const workflow of [verifyWorkflow, releaseWorkflow]) {
    assert.doesNotMatch(workflow, /uses:\s+[^\s]+@(v\d+|main|master)\b/);
    assert.match(workflow, /persist-credentials: false/);
  }
  assert.match(releaseWorkflow, /github\.repository_id/);
  assert.match(releaseWorkflow, /github\.repository_owner_id/);
});
