# GCP deployment — Federation Omni-Mesh v1

This directory is a **proof-gated infrastructure scaffold**. It must not be applied against a project number inferred from historical bridge metadata.

## Preflight gates

Before `terraform apply`, independently prove:

1. current Google Cloud `project_id` and `project_number`;
2. active deployment principal;
3. required APIs and quota/billing context;
4. current WIF pool/provider and service-account state;
5. no duplicate Pub/Sub topic, Cloud Tasks queue or mesh gateway already exists;
6. exact least-privilege IAM plan;
7. rollback target and existing serving-route health.

The legacy bridge that advertises project number `516699068552` is not a valid authority source merely because its transport is live. It should remain fallback-only until the provider-canonical successor route passes equivalent/better transport, idempotency, readback, recovery and rollback canaries.

## Deployment order

1. `terraform plan` only.
2. Review provider-native identity and resource diff.
3. Apply in `shadow` environment.
4. Publish a harmless nonce event.
5. Verify one and only one router delivery.
6. Force a bounded retry and dead-letter test.
7. Verify replay/idempotency.
8. Bind one read-only adapter.
9. Bind SOVARA/JARVIS/CFBE/Sentinel control identities with minimum resource-level roles.
10. Run bidirectional state/readback canary.
11. Run missed-run recovery and node-outage tests.
12. Only then migrate a serving route; preserve the incumbent until rollback is proven.

## IAM posture

- no service-account JSON keys;
- no project-level Owner/Editor role for mesh workloads;
- short-lived WIF/identity tokens where supported;
- one workload identity per application role;
- per-secret Secret Manager access rather than project-wide secret access;
- resource-level Pub/Sub permissions where practical;
- all consequential effects remain separate SOVARA effect-permit gates.

## Provider independence

The Terraform in this directory is one transport implementation. The common mesh envelope, routing, idempotency and proof contracts remain provider-neutral and can be implemented by another broker without changing system-level semantics.
