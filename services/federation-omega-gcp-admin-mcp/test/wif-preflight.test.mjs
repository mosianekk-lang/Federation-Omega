import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

const script = new URL("../ops/verify_gcp_admin_mcp_wif.sh", import.meta.url);

function runFixture(extra = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "fedomega-wif-"));
  const fake = path.join(dir, "gcloud");
  fs.writeFileSync(fake, `#!/usr/bin/env bash
set -euo pipefail
args="$*"
case "$args" in
  "projects describe "*) echo '{"projectId":"sov-hybrid-suite","projectNumber":"257649435135"}' ;;
  "iam workload-identity-pools providers describe "*)
    if [ "\${FAKE_NAME_ONLY:-0}" = 1 ]; then condition="assertion.repository=='mosianekk-lang/Federation-Omega'"; else condition="assertion.repository_id=='1292795464' && assertion.repository_owner_id=='261966700'"; fi
    printf '{"name":"projects/257649435135/locations/global/workloadIdentityPools/github-federation-omega/providers/github","state":"ACTIVE","attributeMapping":{"google.subject":"assertion.sub","attribute.repository_id":"assertion.repository_id","attribute.repository_owner_id":"assertion.repository_owner_id"},"attributeCondition":"%s"}\n' "$condition" ;;
  "iam service-accounts describe "*) echo '{"disabled":false}' ;;
  "iam service-accounts get-iam-policy "*) echo '{"bindings":[{"role":"roles/iam.workloadIdentityUser","members":["principalSet://iam.googleapis.com/projects/257649435135/locations/global/workloadIdentityPools/github-federation-omega/attribute.repository_id/1292795464"]}]}' ;;
  "projects get-iam-policy "*)
    if [ "\${FAKE_BROAD_ROLE:-0}" = 1 ]; then role="roles/owner"; else role="roles/run.admin"; fi
    printf '{"bindings":[{"role":"%s","members":["serviceAccount:federation-omega-deployer@sov-hybrid-suite.iam.gserviceaccount.com"],"condition":{"expression":"resource.name.endsWith('/services/federation-omega-gcp-admin-mcp')"}}]}\n' "$role" ;;
  "services list "*) echo '[{"config":{"name":"run.googleapis.com"}},{"config":{"name":"cloudbuild.googleapis.com"}},{"config":{"name":"artifactregistry.googleapis.com"}},{"config":{"name":"iamcredentials.googleapis.com"}},{"config":{"name":"logging.googleapis.com"}},{"config":{"name":"secretmanager.googleapis.com"}}]' ;;
  "artifacts repositories describe "*) echo '{"name":"projects/sov-hybrid-suite/locations/africa-south1/repositories/federation-omega"}' ;;
  "secrets describe "*) echo '{"state":"ENABLED"}' ;;
  *) echo "unexpected fake gcloud call: $args" >&2; exit 99 ;;
esac
`);
  fs.chmodSync(fake, 0o755);
  const result = spawnSync("bash", [script.pathname], {
    encoding: "utf8",
    env: {...process.env, PATH: `${dir}:${process.env.PATH}`, ...extra},
  });
  fs.rmSync(dir, {recursive: true, force: true});
  return result;
}

test("WIF preflight accepts exact numeric identity and emits a redacted receipt", () => {
  const result = runFixture();
  assert.equal(result.status, 0, result.stderr);
  const receipt = JSON.parse(result.stdout);
  assert.equal(receipt.state, "VERIFIED");
  assert.equal(receipt.mutationPerformed, false);
  assert.equal(receipt.repositoryId, "1292795464");
  assert.equal(Object.keys(receipt.evidenceHashes).length, 8);
});

test("WIF preflight rejects name-only claim conditions", () => {
  const result = runFixture({FAKE_NAME_ONLY: "1"});
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /WIF_NUMERIC_REPOSITORY_CONDITION_MISSING/);
});

test("WIF preflight rejects Owner or Editor authority", () => {
  const result = runFixture({FAKE_BROAD_ROLE: "1"});
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /BROAD_IAM_ROLE_PROHIBITED/);
});
