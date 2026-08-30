# Bubbles Cognitive Court v1

## Status

`IMPLEMENTED_LOCAL_CANARY`; provider execution, production deployment, stable promotion and superiority claims remain disabled.

## Purpose

The court composes the existing Bubbles current-state lease, trace spine and idempotency ledger into one deterministic decision surface. It adds proof-adjusted route ranking, blocking input/tool/output guardrails, counterfactual comparison, compensation-before-effect enforcement, bounded failure policy and claim-to-fruit learning candidates.

## Invariants

- The court never grants provider, financial or production authority.
- An effectful winner can only reach `READY_FOR_FORMATION`; `effect_authorized` is always false.
- Required leases must be current, proved and issued by the expected authority.
- Every effectful route requires a valid idempotency envelope and a compensation plan registered before the effect.
- Guardrail tripwires fail closed.
- Trace events contain correlation metadata and proof pointers, never sensitive payloads.
- Rejected routes and score deltas remain visible as counterfactuals.
- Outcome deviations become review-required learning candidates; weights never self-promote.
- Transient/intermittent retries are bounded. Permanent failures and contradictions do not retry.

## CFBE benchmark harvest

| Capability | Prior Bubbles surface | v1 harvest |
|---|---|---|
| State freshness | Current-state lease | Required as route eligibility proof |
| Duplicate-effect defense | Idempotency ledger | Checked before an effectful winner advances |
| Observability | Privacy-safe trace spine | Adds court input and decision spans |
| Safety | Distributed control proofs | Blocking staged guardrails and tripwires |
| Recovery | Route-specific controls | Compensation must be registered before effect |
| Evaluation | Proof-adjusted scoring | Deterministic ranking plus counterfactual deltas |
| Formation | External execution permits | Court stops at `READY_FOR_FORMATION` |

## Verification target

The isolated unit canary covers ranking, deterministic ties, missing/stale/wrong-authority leases, compensation gating, authority non-expansion, tripwires, idempotency conflicts, privacy-safe traces, deterministic receipts, counterfactual retention, bounded retry policy, non-retryable failures, learning quarantine and empty-input fail-closed behavior.
