# EvidenceOps Workflow and Service Register

Status: SOURCE-AUDITED / CLOUD-READBACK-PENDING
Owner: Kim Kagiso Mosiane
Repository: mosianekk-lang/Federation-Omega

## Current controlled workflows

| Workflow | Purpose | Identity pattern | Classification | Current state |
|---|---|---|---|---|
| evidenceops-infrastructure-inventory.yml | Read-only Google Cloud inventory | Repository variables | CURRENT | Fail-closed because variables are empty |
| evidenceops-sovereign-runtime.yml | Test and optionally deploy private sovereign runtime | Repository variables and secret-name variables | CURRENT | CI-capable; provider deployment unverified |
| deploy-cloud-run.yml | Superior Logic canary and optional promotion | Hard-coded project, WIF, identities and service | CURRENT-BUT-HARDENING-REQUIRED | Must not run until WIF verified and variables adopted |

## Legacy or supersession-review workflows

The following workflow families reference historic NEXUS, PFRD, live-thread or recovery paths and require explicit comparison before any dispatch:

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
- CURRENT-BUT-HARDENING-REQUIRED: useful current workflow with hard-coded cloud authority or incomplete proof gates.
- LEGACY: historic implementation not aligned to the current platform kernel.
- SUPERSESSION-REVIEW: potentially useful logic that must be harvested or retired.
- DANGEROUS: may mutate cloud state automatically or use stale identities without current verification.

## Service register

| Service | Purpose | Expected runtime identity | Source state | Provider state |
|---|---|---|---|---|
| architron9 | Superior Logic runtime | superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com | Deployment workflow exists | Current revision and health unverified |
| evidenceops-sovereign-runtime | Mission and translator runtime | Dedicated runtime identity to be confirmed | CI and conditional deployment exist | Unverified |
| EvidenceOps MCP adapter | Remote MCP bridge | evidenceops-mcp-runtime@sov-hybrid-suite.iam.gserviceaccount.com | Setup and deployment package exist | Unverified |
| IPEP audio worker | Audio processing vertical | Dedicated worker identity required | Scaffold exists | Unverified |

## Required standardisation

1. Cloud project, region, WIF provider and deployer identity must come from one verified repository-variable set.
2. Service-specific names may be workflow variables only after provider readback.
3. No workflow may authenticate with a stale hard-coded provider.
4. Automatic push-to-production paths must be disabled or require explicit environment approval.
5. Every cloud-mutating workflow must have zero-traffic canary, authenticated readback and rollback.
6. Legacy workflows must be closed, archived or marked deployment-inert.

## Current closure gates

- WIF verification receipt: pending.
- Repository variables: empty.
- Infrastructure inventory artifact: absent.
- Service and identity provider readback: pending.
- Legacy workflow disposition: pending.

Maturity: `REGISTER_CREATED / SOURCE_CLASSIFIED / PROVIDER_TRUTH_PENDING`
