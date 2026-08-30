# Superior Logic PR-only Candidate Builder v1

## Status

`IMPLEMENTED_EMPIRICAL_GATE_ASSURANCE_NO_PROMOTION`; stable promotion, provider execution, source mutation, pull-request merge and self-sustaining maturity claims remain disabled.

## Integration

The builder consumes the existing Stage-20 `BRANCH_BOUND_CHALLENGER` work package and routes five deterministic challenger missions through the Bubbles cognitive court introduced by PR #866. Those executions are labelled `CANARY_EXECUTED_NO_EFFECT`, never empirical observations. A separate assurance court verifies the manifest, canary receipts, no-effect boundary and exact rollback anchor, then independently admits the exact hash-pinned 30-pair observed campaign already present on `main`.

## Lifecycle

`WORK_PACKAGE_ADMITTED → FIVE_CANARIES_EXECUTED → 30_PAIR_RECEIPT_HASH_ADMITTED → CANDIDATE_MANIFEST_BUILT → INDEPENDENTLY_ASSURED → PROMOTION_DISABLED`

Failure states are `REJECTED_INPUT`, `COURT_HOLD`, `ASSURANCE_FAILED` and `QUARANTINED`. The canary never transitions to source mutation or promotion.

## Invariants

- Output is bound to a non-canonical branch with `base_ref=main` and `direct_main_mutation=false`.
- All five challenger missions execute locally with `provider_execution=false`, `external_effect=false` and `effect_authorized=false`.
- The source head SHA is the exact rollback anchor; deterministic replay tests the generated candidate identity and receipts.
- Independent assurance recomputes the manifest hash, verifies every canary, revalidates the immutable observed-campaign receipt, and rejects either form of tampering.
- Five court executions are canary evidence only and never increment the observed-pair count.
- The separately admitted receipt supplies 30 `OBSERVED` pairs across eight mission classes and satisfies only the empirical-value gate. Stable promotion remains false because provider registration, deployment and owner-value proof remain separate.
- Candidate generation produces a manifest and proof bundle only. It does not edit source, open or merge a PR, deploy, call providers or expand authority.

## Architecture disposition

| Component | Disposition |
|---|---|
| Backend/library | Deterministic Python builder and independent verifier |
| CLI | Package-native receipt generator |
| Scheduler | PR-triggered GitHub Actions canary only |
| Storage | Immutable 90-day workflow artifact |
| Queue/worker/cache/database | Not applicable; one bounded synchronous no-effect canary |
| Authentication | GitHub read-only workflow token; checkout credentials are not persisted |
| Recovery | Exact branch-head rollback anchor plus deterministic replay |
| Observability | Five canary receipts, 30-pair immutable receipt hash, bridge hash, trace digests, manifest hash, assurance hash and heartbeat |

## Truth boundary

This closes the code, canary, and 30-pair empirical-evidence binding portion of the Stage-20 `ADMIT_PR_ONLY_CANDIDATE_BUILDER_AND_INDEPENDENT_ASSURANCE` gate on the draft branch. It does not prove provider registration, production deployment, owner-value improvement, stable superiority, self-sustaining operation or cross-receiver learning.
