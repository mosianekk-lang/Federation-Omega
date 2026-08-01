# EvidenceOps Workflow and Service Register

Status: SOURCE-AUDITED / CLOUD-READBACK-PENDING
Owner: Kim Kagiso Mosiane
Repository: mosianekk-lang/Federation-Omega

## Current controlled workflows

| Workflow | Purpose | Identity pattern | Classification | Current state |
|---|---|---|---|---|
| evidenceops-infrastructure-inventory.yml | Read-only Google Cloud inventory | Verified repository variables | CURRENT | Fail-closed because variables are empty |
| evidenceops-sovereign-runtime.yml | Test and optionally deploy private sovereign runtime | Repository variables and secret-name variables | CURRENT | CI-capable; provider deployment unverified |
| deploy-cloud-run.yml | Superior Logic canary and optional promotion | Verified repository variables, explicit owner token and WIF receipt | CURRENT / MANUAL / FAIL-CLOSED | Variable migration completed on PR branch; provider execution pending |

## Repository variables — shared cloud authority

- GCP_PROJECT_ID
- GCP_PROJECT_NUMBER
- GCP_REGION
- GCP_WIF_PROVIDER
- GCP_SERVICE_ACCOUNT
- GCP_ARTIFACT_REPOSITORY

## Repository variables — Superior Logic service

- SLRK_CLOUD_RUN_SERVICE
- SLRK_RUNTIME_SERVICE_ACCOUNT

## Repository variables — sovereign runtime deployment and secret references

- GCP_RUNTIME_DEPLOY_ENABLED
- KIM_CANONICAL_BACKEND_ID_SECRET_NAME
- KIM_CANONICAL_RECEIPT_ID_SECRET_NAME
- KIM_CANONICAL_STATUS_SECRET_NAME
- KIM_DATAVERSE_URL (optional)
- KIM_DATAVERSE_MISSION_TABLE (optional)
- KIM_DATAVERSE_SECRET_NAME (optional)

Secret-name variables contain only Secret Manager resource names. They must never contain secret values.

## Legacy or supersession-review workflows

The following workflow families are deployment-inert under `LEGACY_WORKFLOW_RETIREMENT_REGISTER.md` until individually reviewed and re-authorised:

- nexus-operator-recovery-now.yml
- nexus-secret-access-diagnostic.yml
- nexus-direct-preflight.yml
- nexus-direct-runtime-target.yml
- nexus-operator-auth-canary.yml
- pfrd-omega-secure-recovery-deploy.yml
- pfrd-omega-cloudrun-canary.yml
- live-thread-autodeploy.yml
- live-thread-key-recovery.yml

Classification rule:

- CURRENT: part of the active EvidenceOps deployment architecture.
- CURRENT / MANUAL / FAIL-CLOSED: mutation requires explicit owner and provider proof gates.
- LEGACY: historic implementation not aligned to the current platform kernel.
- SUPERSESSION-REVIEW: potentially useful logic that must be harvested or retired.
- DANGEROUS: may mutate cloud state automatically or use stale identities without current verification.

## Service register

| Service | Purpose | Expected runtime identity | Source state | Provider state |
|---|---|---|---|---|
| architron9 | Superior Logic runtime | SLRK_RUNTIME_SERVICE_ACCOUNT | Variable-based gated deployment workflow | Current revision and health unverified |
| evidenceops-sovereign-runtime | Mission and translator runtime | Dedicated runtime identity to be confirmed | CI and conditional deployment exist | Unverified |
| EvidenceOps MCP adapter | Remote MCP bridge | evidenceops-mcp-runtime@sov-hybrid-suite.iam.gserviceaccount.com | Setup and deployment package exist | Unverified |
| IPEP audio worker | Audio processing vertical | Dedicated worker identity required | Scaffold exists | Unverified |

## Required standardisation

1. Cloud project, project number, region, WIF provider and deployer identity must come from one verified repository-variable set.
2. Service-specific names may be configured only after provider readback.
3. No current workflow may authenticate with a stale hard-coded provider.
4. Automatic push-to-production paths remain unauthorised.
5. Every cloud-mutating workflow must have zero-traffic canary, authenticated readback and rollback.
6. Legacy workflows remain deployment-inert until supersession review completes.
7. Secret values must be injected only from Secret Manager under runtime service identity.

## Current closure gates

- WIF verification receipt: pending.
- Repository variables: empty.
- Infrastructure inventory artifact: absent.
- Service and identity provider readback: pending.
- Legacy workflow register: created.
- Superior Logic variable migration: completed on PR branch.

Maturity: REGISTER_UPDATED / CURRENT_PATHS_HARDENED / LEGACY_PATHS_INERT / PROVIDER_TRUTH_PENDING
