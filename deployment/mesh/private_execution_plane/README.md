# Federation Omni-Mesh — Private Execution Plane Contract

This directory documents the runtime boundary required by the Federation Omega Airlock. It contains **no credentials, private project configuration or provider receipts**.

## Separation of duties

- **Public source/admission plane:** source, tests, schemas, provider-neutral IaC and security policy.
- **Private execution plane:** short-lived provider authentication, plans, shadow deployment, runtime canaries and immutable private receipts.
- **Evidence plane:** append-only private receipt storage with independent JARVIS/Sentinel/CFBE readback.
- **Canonical control plane:** SOVARA/KDV/Fabric mission, authority, route and proof state.

The private executor must never commit runtime receipts to the public source repository.

## Minimum executor contract

The executor must:

1. obtain a short-lived Google identity through the already-proven WIF or another provider-native route;
2. bind the exact project, principal, WIF provider, service account, action and target;
3. refuse project-number substitution;
4. run `provider_preflight.py` before any mutation;
5. reject raw secrets in arguments, logs and receipts;
6. use immutable source/image digests;
7. run Terraform plan before apply;
8. keep the incumbent route serving during shadow work;
9. emit transport, semantic, readback, postcondition, rollback and telemetry evidence separately;
10. write receipts to a private append-only evidence store;
11. expose no general reusable credential to ChatGPT, models, KDV or message payloads;
12. support immediate rollback and independently verifiable cleanup.

## Required private configuration

Configuration belongs in the private executor's protected environment or secret manager:

- provider project ID and expected project number;
- full WIF provider resource;
- deployer service account;
- immutable gateway image digest;
- remote Terraform state backend;
- transactional ledger backend reference;
- append-only receipt sink reference;
- exact repository/tenant/ref WIF conditions;
- cost ceiling and effect permit reference.

No raw secret value belongs in this repository.

## Invocation sequence

```text
identity preflight
→ independent receipt verification
→ terraform validate
→ terraform plan
→ cost/IAM/effect gate
→ shadow apply
→ exact resource readback
→ nonce semantic canary
→ DLQ/replay/idempotency
→ restart/outage recovery
→ champion/challenger
→ reversible cutover/rollback
→ sustained soak
→ legacy retirement eligibility
```

## Stop conditions

The executor fails closed on identity mismatch, stale WIF condition, unknown cost, unpinned image, missing durable backend, missing receipt sink, unexpected state change, semantic mismatch, missing readback, rollback failure, owner-burden regression or any request to grant project-level Owner/Editor to a workload.
