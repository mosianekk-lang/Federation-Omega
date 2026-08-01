# EvidenceOps Current Deployment Manifest

Generated from the current `main` architecture and PR #50 infrastructure-recovery work.

## Canonical platform components

- `evidenceops/runtime_service/` — sovereign FastAPI mission runtime
- `evidenceops/ai_ict_durable/` — durable approval, resume-fencing, KMS and PostgreSQL overlay
- `evidenceops/connector_foundry/` — connector contracts and ECTS conformance
- `evidenceops/provenance_passport/` — Merkle-backed provenance toolkit
- `evidenceops/in_place_audit_omega/` — source-local audit engine
- `evidenceops/innovation_engine/` — proof-gated lane and innovation registry
- `evidenceops/fevx_mcoe/` — orchestration doctrine and mission controls
- `evidenceops-mcp-adapter/` — authenticated remote MCP adapter and Cloud Run packaging
- `evidenceops-web-drive-bridge/` — Google Drive bridge
- `evidenceops/security/` — public/private boundary and leak controls
- `ops/bootstrap_github_wif.sh` — repository-scoped WIF plan/apply/verify bootstrap
- `.github/workflows/evidenceops-infrastructure-inventory.yml` — read-only cloud inventory carrier

## Required production infrastructure

- Google Cloud project: `sov-hybrid-suite`
- Region: `africa-south1`
- Repository-scoped GitHub OIDC Workload Identity Federation
- Deployer service account: `superior-logic-deployer`
- Runtime service account: `superior-logic-runtime`
- Cloud Run
- Artifact Registry
- Secret Manager
- Cloud KMS
- private PostgreSQL / Cloud SQL
- structured logging, metrics and traces

## Current proof boundary

- source architecture and deterministic tests: materially present
- public leak guard: operational
- WIF bootstrap: implemented, live provider currently unverified
- infrastructure inventory: blocked by missing repository variables and unverified WIF
- production Cloud Run runtime: unverified
- OpenAI replacement runtime key: secure setup initiated, binding unverified

## Historical package boundary

`IPEP_PLATFORM_SETUP_v0.1.0.zip` is a historical foundation package. It is not the current deployment package and omits later durable-runtime, provenance, connector, audit, security and infrastructure-control components.

## Promotion gate

No deployment may be labelled production verified until:

1. WIF verification returns `FEDOMEGA-WIF-CLOUD-VERIFIED`;
2. the infrastructure inventory artifact is generated and reviewed;
3. runtime secrets are bound through Secret Manager;
4. PostgreSQL, KMS and Cloud Run are read back;
5. a non-sensitive end-to-end canary passes;
6. receipts and rollback proof are preserved.
