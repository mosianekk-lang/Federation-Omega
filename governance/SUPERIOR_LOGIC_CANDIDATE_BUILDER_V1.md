# Superior Logic PR-only Candidate Builder v1

## Status

`IMPLEMENTED_PROVIDER_DISABLED_CANARY`; stable promotion, provider execution, source mutation, pull-request merge and self-sustaining maturity claims remain disabled.

## Integration

The builder consumes the existing Stage-20 `BRANCH_BOUND_CHALLENGER` work package and routes five deterministic challenger missions through the Bubbles cognitive court introduced by PR #866. A separate assurance court verifies the manifest, observations, no-effect boundary and exact rollback anchor without re-running or trusting the builder's route-ranking logic.

## Lifecycle

`WORK_PACKAGE_ADMITTED → FIVE_MISSIONS_OBSERVED → CANDIDATE_MANIFEST_BUILT → INDEPENDENTLY_ASSURED → HELD_FOR_30_PAIR_GATE`

Failure states are `REJECTED_INPUT`, `COURT_HOLD`, `ASSURANCE_FAILED` and `QUARANTINED`. The canary never transitions to source mutation or promotion.

## Invariants

- Output is bound to a non-canonical branch with `base_ref=main` and `direct_main_mutation=false`.
- All five challenger missions execute locally with `provider_execution=false`, `external_effect=false` and `effect_authorized=false`.
- The source head SHA is the exact rollback anchor; deterministic replay tests the generated candidate identity and receipts.
- Independent assurance recomputes the manifest hash, verifies every observation and rejects tampering.
- Five observed pairs are canary evidence only. Stable promotion remains false until at least 30 independent paired missions and a separate Formation promotion review.
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
| Observability | Five court receipts, trace digests, manifest hash, assurance hash and heartbeat |

## Truth boundary

This closes the code-and-canary portion of the Stage-20 `ADMIT_PR_ONLY_CANDIDATE_BUILDER_AND_INDEPENDENT_ASSURANCE` gate on the draft branch. It does not prove provider-live value, 30-pair qualification, stable superiority, self-sustaining operation or cross-receiver learning.
