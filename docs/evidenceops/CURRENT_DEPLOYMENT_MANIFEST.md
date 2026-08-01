# EvidenceOps Current Deployment Manifest

Status: SOURCE-CURRENT / PROVIDER-UNVERIFIED
Owner: Kim Kagiso Mosiane
Repository: mosianekk-lang/Federation-Omega

## Current platform components

- EvidenceOps sovereign runtime
- EvidenceOps MCP adapter
- Durable AI ICT runtime overlay
- Connector Foundry
- Provenance Passport
- In-Place Audit Omega
- Innovation Engine
- IPEP audio worker scaffold
- Public repository leak guard
- WIF bootstrap and deployment controls

## Authoritative cloud identities

- Project: sov-hybrid-suite
- Project number: 257649435135
- Region: africa-south1
- WIF pool: github-federation-omega
- WIF provider: github
- Deployer: superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com
- Superior Logic runtime: superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com
- EvidenceOps MCP runtime: evidenceops-mcp-runtime@sov-hybrid-suite.iam.gserviceaccount.com

## Cloud Run services referenced by source

- architron9
- evidenceops-sovereign-runtime
- EvidenceOps MCP adapter service
- IPEP audio-worker service

## Required infrastructure classes

- Workload Identity Federation
- Cloud Run
- Artifact Registry
- Secret Manager
- Cloud KMS
- PostgreSQL / Cloud SQL
- task and event queues
- encrypted object storage
- logging, metrics and distributed tracing

## Required proof gates

1. `bootstrap_github_wif.sh --verify` returns `FEDOMEGA-WIF-CLOUD-VERIFIED`.
2. Required repository variables are populated from provider-verified values.
3. Infrastructure inventory workflow authenticates and produces its artifact.
4. Artifact hashes and resource counts are read back.
5. Each deployed runtime passes private authenticated health verification.
6. Every secret is bound by service identity and least privilege.
7. No production promotion occurs without an explicit owner gate and rollback route.

## Historical package boundary

`IPEP_PLATFORM_SETUP_v0.1.0.zip` is a historical foundation package. It contains the original Apps Script intake, audio worker scaffold, schema, cloud build and CI files. It does not represent the current platform and must not be deployed as the authoritative release.

## Current open boundaries

- GitHub Actions cloud variables are empty.
- WIF pool/provider state is not provider-verified.
- Cloud Run, Artifact Registry, Secret Manager, KMS, database, storage and queue resources are not yet inventoried through the repaired workflow.
- Replacement OpenAI key creation, binding, revocation and dual canaries remain unverified.
- Production deployment and promotion remain unverified.

## Related controls

- `docs/evidenceops/CLOUD_IDENTITY_AND_AUTHORITY_REGISTER.md`
- `docs/evidenceops/CLOUD_DEPENDENCY_MAP.md`
- `docs/evidenceops/ICT_CLOUD_COMPETENCY_AND_RUNBOOK.md`
- `docs/evidenceops/OPENAI_RUNTIME_SECRET_BINDING_CONTRACT.md`
- `ops/INFRASTRUCTURE_FOUNDATION_ACTIVATION.md`
- GitHub issues #51 and #52

Maturity: `SOURCE_CONSOLIDATED / FAIL_CLOSED / CLOUD_READBACK_PENDING`
