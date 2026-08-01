# EvidenceOps Infrastructure Foundation Activation

This runbook governs the authenticated Google Cloud bootstrap required before the automated infrastructure inventory can run.

## Current failure boundary

The last inventory run failed before token issuance with Google STS `invalid_target`. No cloud inventory command ran and no inventory artifact was produced.

## Authoritative identities

- Project: `sov-hybrid-suite`
- Project number: `257649435135`
- Region: `africa-south1`
- WIF pool: `github-federation-omega`
- Provider: `github`
- Repository: `mosianekk-lang/Federation-Omega`
- Deployer service account: `superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com`
- Runtime service account: `superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com`
- Existing Cloud Run service: `architron9`
- Existing Artifact Registry repository: `federation-omega`

## Read-only discovery first

Run from an authenticated Google Cloud administration surface:

```bash
set -euo pipefail

git clone https://github.com/mosianekk-lang/Federation-Omega.git
cd Federation-Omega
git fetch origin evidenceops/ai-ict-production-runtime-v1-4
git checkout evidenceops/ai-ict-production-runtime-v1-4

export PROJECT_ID=sov-hybrid-suite
export PROJECT_NUMBER=257649435135

bash ops/bootstrap_github_wif.sh --plan | tee /tmp/evidenceops-wif-plan.json
```

The plan must identify the actual state of the pool, provider, attribute mapping, repository condition, service accounts, target resources, APIs and IAM bindings.

## Controlled repair

Cloud mutation remains owner-approved and fail-closed. Apply only after reviewing the plan output:

```bash
export FEDOMEGA_WIF_APPLY_APPROVAL=APPLY_FEDOMEGA_WIF_LEAST_PRIVILEGE
bash ops/bootstrap_github_wif.sh --apply | tee /tmp/evidenceops-wif-apply.json
bash ops/bootstrap_github_wif.sh --verify | tee /tmp/evidenceops-wif-verify.json
```

The verification step must return the exact receipt `FEDOMEGA-WIF-CLOUD-VERIFIED`.

## Repository variables

After verification, configure these non-secret GitHub repository variables with the verified values:

```text
GCP_PROJECT_ID=sov-hybrid-suite
GCP_REGION=africa-south1
GCP_WIF_PROVIDER=projects/257649435135/locations/global/workloadIdentityPools/github-federation-omega/providers/github
GCP_SERVICE_ACCOUNT=superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com
```

Do not store API keys, OAuth refresh tokens or service-account private keys in repository variables.

## Inventory dispatch

```bash
gh workflow run evidenceops-infrastructure-inventory.yml \
  --repo mosianekk-lang/Federation-Omega \
  --ref evidenceops/ai-ict-production-runtime-v1-4
```

## Required proof

The foundation is verified only when:

- WIF pool state is `ACTIVE`;
- provider state is `ACTIVE`;
- provider mapping is exact;
- provider condition restricts the authorised repository and branch;
- deployer and runtime service accounts exist;
- least-privilege IAM bindings pass;
- the infrastructure inventory workflow succeeds;
- the `evidenceops-infrastructure-inventory` artifact is downloaded and independently inspected.

## Boundary

This procedure repairs authentication and inventories existing resources. It does not itself deploy the ICT runtime, create a database, rotate OpenAI keys, or promote production traffic.
