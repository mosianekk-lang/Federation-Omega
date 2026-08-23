# GCP deployment — Federation Omni-Mesh v1

This directory is a **proof-gated shadow infrastructure module**. It must not be applied against a project number inferred from historical bridge metadata, and it must not be run from a public source workflow that can mutate `main`.

## Current execution boundary

The public `Federation-Omega` repository is the source/admission plane. Provider-authorized execution belongs in a separately authenticated **private execution plane**. Runtime receipts must go to an immutable Actions artifact or an approved private append-only evidence store—not to a source-repository commit.

The legacy `.github/workflows/nexus-direct-preflight.yml` contains useful inventory logic, but its `contents: write` plus `git commit`/`git push` behavior is incompatible with the current Airlock model. Reuse the provider-read logic through:

```bash
python -m federation_omni_mesh_v1.provider_preflight \
  --project-id "$PROJECT_ID" \
  --expected-project-number "$PROJECT_NUMBER" \
  --wif-provider "$WIF_PROVIDER" \
  --deployer-service-account "$DEPLOYER_SERVICE_ACCOUNT" \
  --required-api run.googleapis.com \
  --required-api pubsub.googleapis.com \
  --required-api cloudtasks.googleapis.com \
  --required-api iamcredentials.googleapis.com \
  --output "$PRIVATE_RECEIPT_PATH"
```

That preflight is read-only. It does not read secret values, change IAM, create resources, or mutate Git.

## Preflight gates

Before `terraform plan`, independently prove:

1. current Google Cloud `project_id` and `project_number`;
2. active deployment principal;
3. exact WIF pool/provider state and multi-tenant attribute conditions;
4. deployment and runtime service-account state;
5. required APIs, billing/quota context and regional availability;
6. no duplicate Pub/Sub topic, Cloud Tasks queue or mesh gateway already exists;
7. exact least-privilege IAM plan;
8. private durable ledger backend and append-only receipt sink;
9. immutable gateway image digest;
10. rollback target and existing serving-route health.

The bridge advertising project number `516699068552` remains fallback transport only. It is not an authority source merely because its transport is live.

## What the Terraform now includes

- required API activation, visible in the plan;
- dedicated gateway and task-dispatcher service accounts;
- Pub/Sub event, receipt and dead-letter topics;
- event, receipt and dead-letter subscriptions;
- Pub/Sub service-agent IAM required for dead-letter forwarding and acknowledgement;
- a bounded Cloud Tasks queue;
- a private-by-IAM Cloud Run v2 gateway pinned to an immutable image digest;
- OIDC task-dispatch identity and Cloud Run invoker binding;
- queue-level enqueuer permission;
- external durable-ledger and append-only receipt-sink references;
- no unauthenticated Cloud Run invoker;
- no Owner/Editor grant;
- no service-account JSON key.

The module intentionally prohibits `environment = "production"`. Production eligibility must be introduced only after the full CFBE/JARVIS/Sentinel gate chain passes.

## Deployment order

1. Run the read-only identity preflight in the private execution plane.
2. Verify the receipt independently.
3. Provide an immutable image digest and private durable-backend references.
4. `terraform init` using an approved private remote state backend.
5. `terraform validate`.
6. `terraform plan -out=shadow.tfplan`.
7. Review identity, API, resource, IAM and estimated-cost diffs.
8. Apply only the `shadow` environment.
9. Verify exact resource IDs, service accounts, Cloud Run revision and zero serving traffic.
10. Publish one harmless nonce event.
11. Verify one and only one receiver delivery and one semantic receipt.
12. Force bounded retry exhaustion and verify dead-letter forwarding.
13. Verify explicit replay and application-level idempotency.
14. Create one Cloud Task with an OIDC token whose audience is the Cloud Run service URI.
15. Verify read-only adapter delivery, restart persistence and receipt-sink write.
16. Run node/provider outage and missed-run recovery tests.
17. Compare the successor with the incumbent for correctness, latency, cost and owner burden.
18. Demonstrate cutover and rollback before any serving migration.
19. Run the defined soak period.
20. Retire `516699068552` only after the successor is independently proven and the legacy route remains unused.

## IAM posture

- no service-account JSON keys;
- no project-level Owner/Editor role for mesh workloads;
- short-lived WIF/identity tokens;
- WIF attribute conditions restricted to the exact trusted tenant/repository/ref policy;
- one workload identity per application role;
- per-resource IAM wherever supported;
- per-secret Secret Manager access rather than project-wide access;
- the task-dispatch service account is only an authenticated Cloud Run invoker;
- every consequential effect remains a separate SOVARA effect-permit gate.

## Durability boundary

`AtomicJsonFileLedgerStore` is suitable only for provider-disabled and single-writer restart canaries. Cloud Run local files are not durable across instance replacement. A provider deployment must bind a transactional external ledger backend before it can claim restart or failover durability.

## Provider independence

This Terraform module is one transport implementation. The common envelope, node descriptor, routing, idempotency, proof and telemetry contracts remain provider-neutral and can be implemented by another broker without changing system-level semantics.
