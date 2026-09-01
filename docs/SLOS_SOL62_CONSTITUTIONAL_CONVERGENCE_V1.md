# SLOS ↔ SOL 6.2 Constitutional Convergence v1

## Status

`SOURCE_CANDIDATE / CI_ADMISSION_PENDING / PROVIDER_MATURITY_NON_INHERITING`

This change removes the architectural ambiguity between the historical `superior_logic` runtime and `sol_61_runtime` SOL 6.2 line without deleting either compatibility surface.

## One constitutional hierarchy

```text
Owner intent
  → SLOS: mission semantics, Forest/Horizon cognition, algorithms, policy, terminal truth
    → SOL 6.2 kernel: transaction state, idempotency, fencing, authority leases, effect/readback/proof binding
      → SOVARA: provider credentials, effect admission, execution, rollback
        → provider-native readback
      → SOL proof/state commit
    → SLOS terminal-truth compilation and learning
```

SOL 6.2 is therefore a **transaction kernel beneath SLOS**, not a second sovereign mission operating system. SOVARA remains the only provider/effect sovereign. No model, provider, adapter, test, CI result or sibling maturity can inherit those authorities.

## Security correction

The legacy `superior_logic.service` API is retained for local compatibility tests, but it is no longer the deployment entry point. `Dockerfile` now serves `superior_logic.secure_service:app` and defaults to `SUPERIOR_LOGIC_AUTH_MODE=deny_mutations`.

State-changing HTTP methods therefore fail closed until one of the admitted application identity modes is explicitly configured:

- `hmac`: short-lived bounded private/local integration assertions;
- `trusted_proxy`: a provider-native authenticated ingress/IAM layer injects already-verified subject/role/audience claims and the runtime is configured to trust that isolated proxy boundary.

`trusted_proxy` must never be enabled on an unauthenticated public ingress. Provider-native IAM remains the preferred outer boundary.

## Dynamic provider truth

Provider state is no longer treated as a source-code constant in the converged path. `ProviderAttestationStore` persists expiring, evidence-referenced attestations in the SLOS durable database connection. Routing requires:

- exact provider/surface/capability;
- a verified state;
- non-expired observation;
- non-empty provider/readback evidence references;
- source revision identity;
- no raw secret-bearing fields.

A provider improvement therefore produces a new attestation rather than a source patch. Static SOL 6.2 Google mesh v1 remains a compatibility/historical snapshot until all consumers migrate to the attestation router.

## Change-impact control

`MissionSnapshot` and `ChangeImpactCompiler` classify repository movement as:

- `IGNORE_UNRELATED` — no rebase/retest required for the mission;
- `RETEST_ONLY` — assurance/test surface changed, but mission source/contract is unchanged;
- `REBASE_REQUIRED` — protected mission source or compatibility contract changed.

This prevents unrelated `main` activity from repeatedly resetting long-running work while preserving contract-sensitive safety.

## Evidence and observability compression

`EvidenceDistiller` keeps raw evidence at its authoritative source and carries content hashes, bounded excerpts, metadata and source references through control-plane/chat paths. Sensitive evidence never receives an excerpt.

`TraceBuffer` introduces one provider-neutral trace vocabulary across mission → workstream/task → agent/model/tool → provider/effect → readback → proof. It is intentionally exporter-neutral so an OpenTelemetry adapter can be added without changing constitutional semantics.

## WIF lease correction

The existing owner-gated WIF hardening workflow now serializes through one concurrency domain and reads GitHub Actions successful-run history before provider authentication. After the first successful hardening transaction, later triggers emit `ALREADY_CONSUMED` without authenticating to Google or performing provider mutation. Failed pre-effect attempts remain retryable. The admitted hardening script is invoked explicitly through `bash` for shell portability.

This is a **one-success transaction lease**, not a claim that GitHub run history is an immutable global authorization ledger. A future external durable authority ledger may replace this mechanism.

## Repository ruleset gap

Live readback on 1 September 2026 showed no repository rulesets and an unprotected `main`, despite the Airlock design documentation describing platform-enforced admission. The connected GitHub contract available to this workstream provides ruleset/branch-protection **read** operations but no ruleset/branch-protection mutation operation. Therefore this release cannot truthfully activate provider-side GitHub rulesets from this execution surface.

State: `BLOCKED_EXACT_EFFECT / PROVIDER_ADMIN_WRITE_UNAVAILABLE_IN_CURRENT_CONNECTOR`.

This gap must not block source-level convergence, but production repository governance must not be called platform-enforced until GitHub provider readback shows the required rule/ruleset active.

## Proof boundary

A green source/CI court proves this convergence source and its deterministic contracts. It does **not** by itself prove:

- external durable SLOS state;
- production network deployment;
- trusted-proxy ingress isolation;
- Google WIF hardening success;
- Gemini inference;
- GitHub platform ruleset activation;
- sustained operational value.

Each remains receiver/effect specific and requires its own provider-native readback.
