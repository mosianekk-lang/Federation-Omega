# Federation Omni-Mesh v1 — Public-Safe Architecture

Status: `SOURCE_IMPLEMENTED / CONTROL_PLANE_DEPLOYMENT_IN_PROGRESS / PROVIDER_NATIVE_CUTOVER_GATED`

## Objective

Provide logical all-to-all communication across the Federation estate without building brittle point-to-point links. Every system or provider surface joins through one versioned event/command contract, retains its own authority ceiling and canonical truth role, and can be added or removed without redesigning the mesh.

## Architecture

The mesh is six cooperating planes:

1. **Mission and policy plane** — SOVARA owns mission compilation, route selection and effect admission. It does not grant itself provider authority.
2. **Event plane** — durable publish/subscribe for fan-out state, evidence, health, capability and learning events. The existing AO-Harmonic in-memory `EventBus` remains the deterministic reference primitive; provider-backed durable transport is an additive layer.
3. **Command plane** — targeted, retryable work requests with idempotency, bounded retries, dead-letter routing and rollback requirements for consequential operations.
4. **Identity and access plane** — short-lived workload identity, per-application service accounts, secret references only, least privilege and explicit project/provider identity. No raw long-lived credentials are stored in mesh payloads.
5. **Proof and observability plane** — JARVIS independent assurance, Sentinel health/freshness, semantic readback receipts, dead-letter/recovery events, drift detection and SLOs.
6. **Learning and benchmark plane** — CFBE independent benchmark/value feedback plus SOVARA receiver-specific adaptation. Successful behavior does not transfer authority or maturity to another node.

## Why brokered mesh instead of pairwise links

For `N` nodes, direct pairwise integration approaches `N*(N-1)` directional relationships. A common event/command contract reduces the integration problem to approximately `N` adapters plus shared routing/policy, while still providing logical any-to-any communication.

## Common envelope

Every message carries at least:

- immutable `event_id`;
- `event_type` and versioned `topic`;
- `source` and optional `targets`;
- `idempotency_key` and `correlation_id`;
- capability required;
- authority required;
- privacy class;
- payload hash;
- no raw credential material.

## Routing

Routing is capability-, authority-, privacy-, health-, freshness-, reliability-, proof-, latency- and owner-burden-aware. Eligibility is a hard gate. A theoretically high-scoring node cannot win when it lacks current authority, privacy compatibility, semantic capability or health.

## Reliability contract

- duplicate suppression by idempotency key + payload hash;
- key reuse with a changed payload fails closed;
- bounded retry budget;
- dead-letter after retry exhaustion;
- transport success is not semantic success;
- readback and observed state delta are required for completion;
- consequential promotion also requires a rollback path;
- a failed node does not freeze unrelated nodes;
- replacement/cutover occurs before retirement of a still-serving legacy route.

## Provider deployment target

Preferred target architecture when exact Google project/identity is provider-proven:

- Pub/Sub for fan-out events;
- Cloud Run mesh gateway/adapters;
- Cloud Tasks and/or Workflows for targeted commands and multi-step orchestration;
- Firestore or Cloud SQL for durable idempotency, delivery and receipt state;
- Secret Manager with per-secret least privilege;
- Workload Identity Federation for GitHub/external workloads, using short-lived credentials and tenant/repository attribute conditions;
- Apps Script as a Google Workspace edge adapter where native Workspace triggers are useful;
- KDV/Federation Bible Fabric as durable governance/projection and recovery controls, not as the high-throughput message broker.

## Provider independence

The common envelope, node descriptor, routing policy, delivery ledger and proof contract are provider-neutral. Pub/Sub/Cloud Run are a preferred current deployment target, not SOVARA's sovereign root. A future NATS/Kafka/Azure/AWS transport can implement the same adapter contract.

## Stable cutover ladder

`SOURCE_IMPLEMENTED -> DETERMINISTIC_TESTED -> SHADOW -> READ_ONLY_CANARY -> BIDIRECTIONAL_CANARY -> MISSED_RUN_RECOVERY -> LOAD/FAULT_CANARY -> REVERSIBLE_CUTOVER -> SUSTAINED_PROVEN`

No phase is skipped. Existing proven routes remain fallback until equivalent/better behavior is proven on the successor.

## Acceptance gates

A production mesh is not `FULLY_OPERATIONAL` until all of the following pass:

- every registered active system has a node descriptor or explicit NOT_APPLICABLE disposition;
- every externally acting adapter has current identity/authority proof;
- every node can publish and receive at least one harmless nonce event through the common envelope;
- target delivery is idempotent;
- fan-out delivery is independently read back;
- semantic mismatch is detected despite HTTP/transport success;
- dead-letter and replay work;
- missed-run recovery works;
- one node/provider outage does not stall independent safe lanes;
- credentials are transient and never stored in events/logs;
- JARVIS can hold false completion;
- Sentinel can detect stale or failed nodes;
- CFBE can measure routing/reliability/value without self-certification;
- rollback from the successor route to the incumbent is demonstrated;
- sustained operation is observed across a defined soak period.

## Validation and repository admission

The deterministic source test is `python -m pytest -q tests/test_federation_omni_mesh_v1.py` in an environment where repository test dependencies are installed.

Repository Airlock remains authoritative. Omni-Mesh does **not** add a new GitHub Actions workflow merely to run its tests: a first draft did so, the Airlock policy correctly rejected that workflow shape, and the workflow was removed before source promotion. Validation must run through an existing allowlisted repository control or an approved local/hosted runner, and merge remains blocked until those results are read back.

The provider deployment scaffold also remains inert until an exact provider-native Google project/identity preflight passes. Legacy bridge transport success is not accepted as that identity proof.

## Guarantee boundary

The design is intended to make access/automation failures diagnosable, recoverable and much less likely to stall the estate. No distributed system can truthfully guarantee that a third-party provider, credential, quota, network, policy or API will never fail. The mesh therefore treats failure as an expected state and is built to detect, isolate, reroute, recover and prove the result.
