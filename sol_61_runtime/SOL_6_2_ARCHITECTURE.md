# SOL 6.2 — Transactional Self-Verifying Runtime

Status: DETERMINISTIC_TESTED  
Predecessor: SOL 6.1 durable reference runtime  
Date: 2026-09-01

## Evolution

SOL 6.1 remains the compatibility and historical reference runtime. SOL 6.2 changes the unit of control from task completion to **verified state transition**.

A mission is complete only when its declared target state is observed and its proof contract is valid.

## Runtime contract

```
INTENT
  -> GATEWAY + WORKLOAD IDENTITY
  -> DURABLE IDEMPOTENCY RESERVATION
  -> EFFECT + INTENT PREPARATION
  -> FENCED ACTION AUTHORITY
  -> OPTIONAL SHADOW/SIMULATION PROOF
  -> DISPATCH
  -> PROVIDER READBACK
  -> SEMANTIC + ATTESTATION VERIFICATION
  -> ATOMIC EFFECT/STATE/AUDIT COMMIT
  -> VERIFIED REALITY
```

## Core invariants

1. **One transactional truth spine.** SOL 6.2 uses SQLite WAL/`BEGIN IMMEDIATE` for its bounded reference control plane. This is serialized multi-process durability on one shared filesystem; it is not claimed as multi-region consensus.
2. **No task-status closure.** Mission closure requires target-state satisfaction plus proof.
3. **Atomic commit boundary.** Effect `OBSERVED -> VERIFIED`, mission projection, transition status and audit event commit in one transaction.
4. **Effect preparation is atomic.** Idempotency reservation, effect creation, intent persistence and preparation audit are one transaction.
5. **Dispatch authority is atomic.** Fencing, action-bound one-use authority consumption, transition start and dispatch authorization are one transaction.
6. **Idempotency collisions fail closed.** Reusing an idempotency key with different semantic input is rejected.
7. **Proof is evidence-bound.** Proof digest, freshness, subject, target, operation, source version and semantic verifier must pass. Provider-native proof additionally requires an explicit attestation verifier.
8. **Workload identity and gateway ingress are required for execution.** Long-lived/static credential classes are rejected by policy.
9. **High-risk actions require simulation proof.** `HIGH` and `CRITICAL` transitions require a verified simulation/shadow receipt before dispatch.
10. **Recovery respects effect semantics.** Interrupted at-most-once effects require provider probing before retry; idempotent effects may reuse the same idempotency key.
11. **Schema versions are monotonic.** Downgrades fail closed; same-version/same-content registration is idempotent.
12. **Supersession does not prematurely unblock dependants.** A superseded dependency is satisfied only after its replacement is verified.
13. **Output guardrails run before irreversible state commit.**
14. **State races fail closed through CAS/version fencing.**
15. **Maturity does not inherit from source design.** Reference proof does not imply provider-live or production deployment.

## Compatibility strategy

The new runtime is placed under `sol_61_runtime/**` so the already-admitted SOL proof workflow compiles and exercises the new version without widening GitHub workflow authority. `prove_runtime.py` retains the SOL 6.1 receipt and adds a mandatory SOL 6.2 reference-runtime gate.

No SOL 6.1 public module is replaced in this upgrade.

## Main implementation

- `sol_62_frontier_primitives.py` — CFBE-harvested transactional/proof/identity/observability primitives.
- `sol_62_runtime.py` — SOL 6.2 state-transition runtime.
- `sol_62_strict_runtime.py` — strict effect/proof/closure binding facade.
- `sol_62.py` — canonical SOL 6.2 runtime facade.
- `test_sol_62_runtime.py` and `test_sol_62_strict_runtime.py` — adversarial and transactional regression courts.
- `prove_sol_62_runtime.py` — machine-readable reference-runtime proof.
- `SOL_6_2_PROGRAMME.json` — promotion state and truth boundary.

## Current verified maturity

The repository's exact-head Airlock/ProofOS court has admitted the SOL 6.2 source/reference runtime at **DETERMINISTIC_TESTED**. The SOL62 mapping has zero unmapped production paths and uses a scoped blocking court while retaining global Airlock, provenance, default-deny, Bubbles Command Bus and public leak-guard controls.

This maturity is intentionally bounded to source/reference-runtime proof. It does not inherit into provider-live or production status.

## Promotion ladder

`SOURCE_IMPLEMENTED`
-> `DETERMINISTIC_TESTED`
-> `HOSTED_SHADOW`
-> `PROVIDER_VERIFIED_SCOPED`
-> `OPERATIONAL_VERIFIED_SCOPED`
-> `SUSTAINED_VALUE_VERIFIED_SCOPED`

Promotion is one step at a time, within the same scope, with a complete proof chain.

## Explicit non-claims

This source upgrade does **not** establish:

- multi-region consensus;
- universal exactly-once semantics across providers that do not support idempotency;
- provider IAM/workload identity deployment;
- provider-hosted continuous/background execution;
- production cutover;
- sustained SLO/value proof;
- AGI;
- market superiority.

Those require separate empirical provider-native evidence.
