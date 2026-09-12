# Federation Omni-Mesh v1 — Audit Hardening Tranche

Status: `SOURCE_HARDENED / HOSTED_ADMISSION_REQUIRED / PROVIDER_RUNTIME_GATED`

This tranche converts the 23 August 2026 audit findings into enforceable source controls. It does not claim provider deployment or raise the proof-adjusted CFBE score by itself.

## Closed source defects

### Fail-closed node admission

`NodeDescriptor` now rejects:

- unknown authority or privacy classifications;
- unknown health states;
- out-of-range freshness, reliability, proof, executability or owner-burden metrics;
- negative latency;
- invalid versions and supersession hashes;
- non-JSON metadata.

Unbound, stale, unknown, failed, retired and quarantined nodes are not routable. Degraded nodes may use an explicit fallback only for internal/read-only work. Reversible and consequential routes require stronger freshness and proof floors.

### Collision-safe descriptor replacement

A node ID can no longer be silently overwritten. A changed descriptor must:

1. increment `descriptor_version`; and
2. bind `supersedes_descriptor_hash` to the exact previous descriptor.

Identical re-registration remains idempotent.

### Operation-aware proof

Read-only operations no longer need a fabricated state delta. Every receipt declares `expected_state_change`:

- `True`: a mutation must change state;
- `False`: a read-only action must not change state;
- `None`: the operation has another explicitly verified postcondition.

Transport, semantics, readback, expected postcondition and rollback remain distinct gates.

### Crash-safe delivery resumption

The delivery ledger now records event identity, payload hash and receiver-level states. Its serializable snapshot can be restored after interruption. `resume_incomplete()` reissues only unfinished receivers; completed receivers are not repeated, and dead-letter deliveries require explicit replay re-arming.

### Secret-safe payload controls

Secret detection now covers suspicious key names and common credential value patterns. Exact opaque secret/credential/permit reference forms are allowed. Raw credentials remain forbidden.

### Measured telemetry integrity

Telemetry now keeps unknown cost as unknown rather than zero. It supports:

- bounded timestamp windows;
- minimum sample sizes;
- verified delivery rate;
- transport, semantic, readback and postcondition error budgets;
- latency, retry and owner-burden targets;
- explicit incomplete timestamp/cost/telemetry findings.

The 5,000-node synthetic probe is labelled `IN_MEMORY_ROUTABILITY_ONLY`; it is not throughput or capacity proof.

### Durable provider-disabled ledger

`AtomicJsonFileLedgerStore` provides hash-verified, compare-and-set, atomic local persistence for provider-disabled and single-writer canaries. It is not a Cloud Run durability claim. A transactional external store remains mandatory before provider restart/failover promotion.

### Safe provider identity preflight

`provider_preflight.py` extracts the reusable part of the legacy NEXUS preflight into a read-only, no-secret, no-Git-mutation tool. It verifies exact project, WIF provider, deployer service account, IAM visibility and enabled APIs, and emits a hash-bound receipt.

The old workflow's `contents: write`, `git commit` and `git push` behavior is not part of the new route.

## Hosted admission

The existing allowlisted Federation Omega Airlock now runs `test_federation_omni_mesh_unittest.py`. This gives the current PR a provider-hosted regression gate for the critical authority, proof, recovery, durability, secret and identity-preflight controls without adding a new workflow.

The larger pytest suites remain useful local/source QA. Hosted Airlock admission and provider-runtime proof remain separate.

## Provider deployment parity

The GCP Terraform scaffold now includes:

- immutable image-digest validation;
- dedicated gateway and task-dispatch identities;
- event, receipt and dead-letter topics/subscriptions;
- Pub/Sub service-agent dead-letter IAM;
- Cloud Tasks queue and queue-level enqueuer IAM;
- private-by-IAM Cloud Run v2 gateway;
- OIDC task-dispatch identity and invoker binding;
- required API activation visible in plan;
- external ledger and append-only receipt sink references;
- an explicit production-deployment prohibition.

No apply is authorized until the private execution plane produces an independently verified identity receipt and reviewed plan.

## Remaining provider gates

1. callable private execution plane;
2. current provider-native Google identity receipt;
3. immutable gateway image and private remote state;
4. shadow apply and exact resource readback;
5. event and command semantic nonce canaries;
6. DLQ/replay/idempotency proof;
7. external durable-state restart proof;
8. failure-domain/provider outage recovery;
9. measured SLO, cost and owner burden;
10. champion/challenger cutover and rollback;
11. sustained soak;
12. legacy-unused retirement eligibility.

CFBE remains frozen from terminal promotion until these gates produce provider-native evidence.
