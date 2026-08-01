# EvidenceOps Cloud Dependency Map

Status: SOURCE-DERIVED / PROVIDER-INVENTORY-PENDING
Owner: Kim Kagiso Mosiane

## Identity plane

- GitHub OIDC token issuer
- Google Workload Identity Pool `github-federation-omega`
- OIDC provider `github`
- Deployer service account `superior-logic-deployer`
- Runtime service account `superior-logic-runtime`
- MCP runtime service account `evidenceops-mcp-runtime`
- repository- and branch-scoped principal condition

## Compute plane

- Cloud Run service `architron9`
- Cloud Run service `evidenceops-sovereign-runtime`
- EvidenceOps MCP adapter Cloud Run service
- IPEP audio worker Cloud Run service
- zero-traffic canary and explicit traffic promotion

## Container and build plane

- Artifact Registry repository `federation-omega`
- possible MCP-specific repository `evidenceops`
- immutable commit-SHA image tags
- Docker and Cloud Build workflows
- image digest readback

## State plane

- PostgreSQL / Cloud SQL for missions, tasks, approvals, leases and receipts
- current local SQLite implementations for development and deterministic testing
- migration requirement from ephemeral/local state to private durable state

## Secret and encryption plane

- Secret Manager
- Cloud KMS
- OpenAI runtime key
- MCP access token
- operator admin token
- canonical backend identifiers and status
- optional Dataverse access token
- state-encryption KMS key and service identity

## Queue and orchestration plane

- Cloud Tasks and/or Pub/Sub for task delivery
- dead-letter handling
- lease and fencing-token enforcement
- idempotent operations and replay receipts
- durable approval pause/resume

## Evidence and object plane

- authorised Google Drive source repositories
- encrypted derivative/object storage
- immutable receipt storage
- Merkle/provenance passport outputs
- source-local connector operations

## Observability plane

- Cloud Logging
- structured runtime logs
- GitHub Actions receipts and artifacts
- service health/readiness readback
- distributed traces / OpenTelemetry requirement
- metrics, alerts and cost telemetry

## External provider plane

- OpenAI project and API key
- optional Microsoft Dataverse parity route
- Google Workspace connectors
- future transcription and authenticity providers

## Dependency gates

1. WIF verification.
2. repository variables populated.
3. cloud inventory artifact produced.
4. service accounts and IAM read back.
5. secrets and KMS keys read back without exposing values.
6. databases, queues, storage and Cloud Run services inventoried.
7. authenticated canaries pass.
8. promotion and rollback receipts preserved.

Maturity: `DEPENDENCIES_MAPPED / EXISTENCE_AND_HEALTH_UNVERIFIED`
