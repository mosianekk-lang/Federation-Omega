import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const cloudbuild = fs.readFileSync(new URL("../cloudbuild.v022.yaml", import.meta.url), "utf8");
const bootstrap = fs.readFileSync(new URL("../bootstrap.sh", import.meta.url), "utf8");
const packageJson = JSON.parse(fs.readFileSync(new URL("../package.json", import.meta.url), "utf8"));

test("v0.2.2 hardens the server and deployment as one release", () => {
  assert.equal(packageJson.version, "0.2.2");
  assert.match(packageJson.scripts["test:smoke"], /SERVER_VERSION!==['"]0\.2\.2/);
});

test("deployment creates an immutable zero-traffic canary", () => {
  assert.match(cloudbuild, /immutable_image=/);
  assert.match(cloudbuild, /--revision-suffix=/);
  assert.match(cloudbuild, /--tag=/);
  assert.match(cloudbuild, /--no-traffic/);
  assert.doesNotMatch(cloudbuild, /--allow-unauthenticated/);
  assert.doesNotMatch(cloudbuild, /--to-latest/);
});

test("rollout captures and restores exact prior traffic", () => {
  assert.match(cloudbuild, /prior-service\.json/);
  assert.match(cloudbuild, /PRIOR_TRAFFIC_NOT_EXACTLY_100/);
  assert.match(cloudbuild, /restore_prior_traffic/);
  assert.match(cloudbuild, /--to-revisions="\$\$\{prior_traffic\}"/);
  assert.match(cloudbuild, /AUTOMATIC_TRAFFIC_RESTORATION_CONFIRMED/);
  assert.match(cloudbuild, /AUTOMATIC_NEW_SERVICE_REMOVAL_CONFIRMED/);
  assert.match(cloudbuild, /trap restore_prior_traffic ERR INT TERM/);
});

test("promotion requires authenticated semantic canaries and exact readback", () => {
  assert.match(cloudbuild, /print-identity-token --audiences=/);
  assert.match(cloudbuild, /Authorization: Bearer/);
  assert.match(cloudbuild, /proofBoundary.*transport_liveness_only/);
  assert.match(cloudbuild, /gcp_deployment_lineage_attest/);
  assert.match(cloudbuild, /"rollback":\{"revision":revision,"buildId":build_id\}/);
  assert.match(cloudbuild, /MCP_LINEAGE_NOT_ATTESTED/);
  assert.match(cloudbuild, /provider_identifiers_matched_across_two_independent_reads/);
  assert.match(cloudbuild, /--to-revisions="\$\$\{candidate_revision\}=100"/);
  assert.match(cloudbuild, /MCP_LINEAGE_REVISION_MISMATCH/);
  assert.match(cloudbuild, /MCP_LINEAGE_BUILD_DIGEST_MISMATCH/);
  assert.match(cloudbuild, /PROMOTED_TRAFFIC_MISMATCH/);
  assert.match(cloudbuild, /promoted-lineage\.json/);
});

test("bootstrap separates runtime and deployer authority", () => {
  assert.match(bootstrap, /federation-omega-admin/);
  assert.match(bootstrap, /federation-omega-deployer/);
  assert.match(bootstrap, /FederationOmegaServiceEnable/);
  assert.match(bootstrap, /roles\/artifactregistry\.writer/);
  assert.match(bootstrap, /roles\/iam\.serviceAccountUser/);
  assert.match(bootstrap, /--service-account="projects\/\$\{HOST_PROJECT\}\/serviceAccounts\/\$\{DEPLOYER_SA\}"/);
  assert.match(bootstrap, /ATTEST_SERVICE="\$\{ATTEST_SERVICE:-\$\{SERVICE\}\}"/);
  assert.match(bootstrap, /FederationOmegaSourceVerify/);
  assert.match(bootstrap, /--permissions="storage\.objects\.get"/);
  assert.doesNotMatch(bootstrap, /roles\/owner|roles\/editor/);
  assert.doesNotMatch(bootstrap, /serviceUsageAdmin/);
});
