# Federation Living State Transition Lineage v1

Status: SOURCE_CANDIDATE
Authority ceiling: A1_INTERNAL
External effects: none

## Trigger

The first real prospective EDPF cohort produced a valid chronological prediction/outcome pair but the Living State snapshot classified the normal lifecycle

`PREDICTION_OPEN -> PREDICTION_RESOLVED_OCCURRED`

as `split_brain=true` because both fresh observations remained inside overlapping TTLs. That false conflict also created split-brain debt and a `HOLD_EFFECTFUL_ROUTE` reflex.

The event chain itself was valid; the defect was state-transition semantics.

## Repair

Living State now distinguishes:

- `NODE_OBSERVED`: an independent observation that remains eligible for normal split-brain reconciliation; and
- `NODE_TRANSITIONED`: a later state that explicitly supersedes one exact predecessor fingerprint while preserving both events immutably.

The transition-aware model is exported through the existing `federation.living_state.world_model.LivingWorldModel` compatibility facade, which is already used by `LivingStateStore`. No new store, scheduler, daemon or authority plane is created.

## Transition invariants

A transition fails closed unless:

1. the predecessor fingerprint already exists in the same node history;
2. replacement and predecessor have the same node kind;
3. matter scope is identical;
4. replacement time is strictly later;
5. replacement proof rank is at least as strong as the predecessor;
6. state actually changes; and
7. replacement fingerprint has not already been observed.

A transition never deletes its predecessor. The journal records the replacement plus exact predecessor fingerprint and transition class.

## Split-brain semantics

When selecting the best current state, an older different state is not considered a competitor only when the selected state is an explicit transition descendant of that exact fingerprint.

This is deliberately narrower than “newer wins.”

Consequences:

- ordinary conflicting observations remain split brain;
- two branches that both supersede the same predecessor remain split brain with each other;
- transitive lawful transition lineage can suppress its own ancestors;
- stronger prior proof cannot be erased by weaker transition proof.

## EDPF binding

The first bound lifecycle is the already-admitted EDPF prospective prediction contract.

A resolved `EXPERIMENT` node is automatically treated as a transition only when all of the following match:

- source class `EDPF_PROSPECTIVE_OUTCOME`;
- state is `PREDICTION_RESOLVED_OCCURRED` or `PREDICTION_RESOLVED_NOT_OCCURRED`;
- payload schema is `SOVARA_EDPF_LIVING_STATE_PREDICTION_ADAPTER_V1`;
- `prospective_capture=true`;
- resolution payload exists; and
- exactly one prior `EDPF_PROSPECTIVE_PREDICTION / PREDICTION_OPEN` node matches the prediction, mission, snapshot and matter scope.

Missing or ambiguous predecessor proof fails closed instead of silently declaring supersession.

## Replay compatibility

Historical `NODE_OBSERVED` journals are replayed exactly as written. The new replay path deliberately bypasses automatic EDPF transition recognition for old `NODE_OBSERVED` events so historical event digests and historical semantics are not rewritten.

Only newly emitted `NODE_TRANSITIONED` events carry transition lineage.

## Proof boundary

Source/CI admission can prove:

- deterministic transition validation;
- exact journal replay;
- no false split brain for new lawful EDPF resolution;
- preservation of genuine conflicts and branching conflicts; and
- no authority/effect expansion.

It does not retroactively rewrite old journals, prove provider state, authorize effects, or establish predictor calibration superiority.

## Empirical origin

This repair was triggered by EDPF shadow cohort 001:

- forecast probability: 0.82;
- forecast recorded before canary creation;
- later canary outcome: true;
- prediction and outcome ingress readback: verified;
- derived one-observation Brier score: 0.0324;
- calibration superiority: unproven (`n=1`).

The false split-brain classification was therefore discovered by real chronological evidence rather than a synthetic architecture review.
