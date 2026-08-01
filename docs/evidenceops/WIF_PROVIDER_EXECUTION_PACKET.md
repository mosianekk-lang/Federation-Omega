# EvidenceOps WIF Provider Execution Packet

Status: READY_FOR_AUTHORISED_PROVIDER_EXECUTION / NOT YET RUN
Owner approval authority: Kim Kagiso Mosiane

## Objective

Restore repository-scoped GitHub-to-Google Workload Identity Federation, populate verified non-secret repository variables, and execute the read-only infrastructure inventory without guessing provider state.

## Expected estate

- Project ID: `sov-hybrid-suite`
- Project number: `257649435135`
- Region: `africa-south1`
- Pool: `github-federation-omega`
- Provider: `github`
- Repository: `mosianekk-lang/Federation-Omega`
- Trusted ref: `refs/heads/main`
- Deployer: `superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com`
- Runtime: `superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com`
- Existing Cloud Run target: `architron9`
- Existing Artifact Registry target: `federation-omega`

## Phase 1 — read-only plan

From an authorised Google Cloud administration surface:

```bash
set -euo pipefail

gcloud auth list
gcloud config set project sov-hybrid-suite
gcloud projects describe sov-hybrid-suite --format='value(projectNumber)'

git clone https://github.com/mosianekk-lang/Federation-Omega.git
cd Federation-Omega
git checkout main

bash ops/bootstrap_github_wif.sh --plan | tee /tmp/fedomega-wif-plan.json
```

Required review:

- active account is authorised;
- observed project number equals `257649435135`;
- Cloud Run service and Artifact Registry repository exist;
- exact missing WIF and IAM controls are listed;
- no mutation is reported.

## Phase 2 — owner-gated repair

Run only after reviewing Phase 1 and confirming the target resources:

```bash
export FEDOMEGA_WIF_APPLY_APPROVAL=APPLY_FEDOMEGA_WIF_LEAST_PRIVILEGE
bash ops/bootstrap_github_wif.sh --apply | tee /tmp/fedomega-wif-apply.json
bash ops/bootstrap_github_wif.sh --verify | tee /tmp/fedomega-wif-verify.json
```

Required exact verification:

- receipt: `FEDOMEGA-WIF-CLOUD-VERIFIED`
- state: `VERIFIED`
- pool state: `ACTIVE`
- provider state: `ACTIVE`
- repository condition exact;
- attribute mapping exact;
- required IAM bindings present;
- mutation flag false on verification.

## Phase 3 — repository variables

Populate only after verification:

```text
GCP_PROJECT_ID=sov-hybrid-suite
GCP_REGION=africa-south1
GCP_WIF_PROVIDER=<verified provider resource from receipt>
GCP_SERVICE_ACCOUNT=superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com
GCP_RUNTIME_DEPLOY_ENABLED=false
```

Do not set `GCP_RUNTIME_DEPLOY_ENABLED=true` during inventory recovery.

## Phase 4 — read-only inventory

Dispatch `EvidenceOps Infrastructure Inventory` on the active branch or merged workflow.

Required artifact:

`evidenceops-infrastructure-inventory`

Required contents:

- active account metadata;
- project metadata;
- enabled services;
- Artifact Registry repositories;
- storage buckets;
- Pub/Sub topics and subscriptions;
- Cloud SQL instances;
- Cloud Run services;
- service accounts;
- Secret Manager secret names only;
- inventory summary with SHA-256 hashes and resource counts.

## Phase 5 — readback and closure

1. Download the workflow artifact.
2. Verify every JSON file parses.
3. Recompute SHA-256 hashes.
4. Compare hashes to `inventory-summary.json`.
5. Record counts without secret values.
6. Update GitHub issue #52 and PR #50.
7. Preserve a redacted receipt in the private operations store.

## Prohibited actions

- Do not broaden trust to an organisation-wide principal when repository scope is sufficient.
- Do not trust pull-request code before base-branch protections are considered.
- Do not print secret payloads or secret versions.
- Do not promote Cloud Run traffic during this packet.
- Do not treat source consistency as provider verification.

Maturity: `PACKET_READY / OWNER-GATED / PROVIDER_EXECUTION_PENDING`
