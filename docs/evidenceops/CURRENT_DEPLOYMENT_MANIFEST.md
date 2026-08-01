# EvidenceOps Current Deployment Manifest

Status: SOURCE-CURRENT / PROVIDER-UNVERIFIED / NO-MERGE-GATE
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
- WIF pool/provider: apply only from provider-native verification
- Deployer: superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com
- Superior Logic runtime: superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com
- EvidenceOps MCP runtime: evidenceops-mcp-runtime@sov-hybrid-suite.iam.gserviceaccount.com

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
2. The verified receipt provider, project number and deployer exactly match repository variables.
3. Required repository variables are populated from provider-verified values.
4. Infrastructure inventory authenticates and produces a complete artifact.
5. Artifact hashes and resource counts are independently read back.
6. Every runtime secret is bound by service identity and least privilege.
7. A zero-traffic canary passes authenticated health checks and produces a retained receipt.
8. Production promotion requires explicit owner input and produces a separate promotion receipt.
9. Failed promotion proves rollback to the previous ready revision.

## Historical package boundary

`IPEP_PLATFORM_SETUP_v0.1.0.zip` is a historical foundation package and is not the authoritative release.

## Current open boundaries

- GitHub Actions cloud variables are empty.
- WIF pool/provider state is not provider-verified.
- Cloud Run, Artifact Registry, Secret Manager, KMS, database, storage and queue resources are not yet inventoried through the repaired workflow.
- Replacement OpenAI key creation, binding, revocation and dual canaries remain unverified.
- Production deployment and promotion remain unverified.

## Related controls

- `docs/evidenceops/CLOUD_IDENTITY_AND_AUTHORITY_REGISTER.md`
- `docs/evidenceops/CLOUD_DEPENDENCY_MAP.md`
- `docs/evidenceops/WORKFLOW_AND_SERVICE_REGISTER.md`
- `docs/evidenceops/LEGACY_WORKFLOW_RETIREMENT_REGISTER.md`
- `docs/evidenceops/ICT_CLOUD_COMPETENCY_AND_RUNBOOK.md`
- `docs/evidenceops/OPENAI_RUNTIME_SECRET_BINDING_CONTRACT.md`
- `docs/evidenceops/REPOSITORY_VARIABLE_APPLICATION_MANIFEST.md`
- `docs/evidenceops/WIF_PROVIDER_EXECUTION_PACKET.md`
- `schemas/cloud-provider-execution-receipt.schema.json`
- GitHub issues #51 and #52

## No-merge gate

PR #50 must not merge until:

- the latest source and leak checks pass;
- WIF provider verification succeeds;
- the four shared inventory variables are populated from verified values;
- the infrastructure inventory artifact is generated and inspected;
- no unresolved P0 security defect remains in the PR diff.

Maturity: `SOURCE_CONSOLIDATED / FAIL_CLOSED / CLOUD_READBACK_PENDING / MERGE_PROHIBITED`
