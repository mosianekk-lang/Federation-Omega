# SOVARA EDPF — Living State Prospective Prediction Intake v1

## Purpose

Close the gap between EDPF source capability and genuinely prospective calibration without creating another prediction database or learning ledger.

The adapter records predictions in the already-admitted Federation Living State event journal as `NodeKind.EXPERIMENT` observations. A later outcome resolves the same node with separate proof. Resolved pairs can then be compiled into the admitted EDPF Shadow Prediction Court.

## Why this is different from retrospective replay

A retrospective blind replay can test historical reasoning mechanics, but the evaluator already exists after the historical outcome. It must not be treated as prospective operational proof.

This adapter captures a prediction **before** its outcome exists in the Living State journal. The later outcome is a second append-only observation. The event-chain order therefore becomes durable evidence of the prediction/outcome chronology.

## Prediction-time contract

Each prospective record binds:

- mission id;
- fixed EDPF/predictor system source head;
- mission-state snapshot digest;
- predictor source-family fingerprint;
- predictor version;
- prediction timestamp;
- prediction receipt/proof ref;
- probability, expected value, latency and owner burden;
- exact pre-outcome evidence refs;
- matter scope and sensitivity.

The predictor probability remains inside the prediction payload. Living State provenance confidence is `1.0` because that field represents confidence that the prediction record itself was observed correctly, not probability that the forecast will occur.

## Outcome contract

Resolution requires:

- a previously open prediction node;
- the same matter scope;
- an outcome timestamp strictly later than prediction time;
- proof maturity above `DECLARED`;
- non-empty outcome proof refs;
- outcome proof disjoint from prediction-time evidence and prediction receipt;
- immutable original prediction payload.

The resolved observation records Brier score, absolute probability error, value error, latency error and owner-burden error.

## Existing-state reuse

No `NodeKind` or `LivingWorldModel` core modification is needed.

- open predictions are `EXPERIMENT / PREDICTION_OPEN`;
- resolved predictions remain the same `EXPERIMENT` node id with a later resolved state;
- `LivingWorldModel.observe_node()` supplies append-only hash-linked journal semantics;
- `LivingWorldModel.replay()` supplies semantic replay proof;
- the adapter compiler converts only valid open->resolved event pairs into EDPF `ShadowPredictionPair` records.

Mission snapshot digests may differ across the cohort while the fixed `system_source_head_sha` identifies the predictor/EDPF implementation version being calibrated. A change in predictor system source head starts a new calibration epoch instead of contaminating the old cohort.

## Matter-wall rule

An outcome cannot resolve a prediction captured in a different matter scope. This prevents evidence or outcome signals from one matter contaminating another matter's calibration.

## Authority boundary

This adapter performs only A1-internal state observations. It cannot:

- call an AI/provider;
- dispatch a route;
- execute an external effect;
- change live predictor weights;
- deploy code or traffic;
- authorize spend;
- publish or communicate externally;
- self-promote a predictor.

## Promotion ladder

`SOURCE_CANDIDATE -> DETERMINISTIC_TESTED -> CI_ADMITTED -> PROSPECTIVE_PREDICTIONS_CAPTURED -> PROSPECTIVE_OUTCOMES_RESOLVED -> REAL_SHADOW_COHORT_SUFFICIENT -> CALIBRATION_POSITIVE -> MATCHED_OWNER_VALUE_PROVEN -> separately governed routing candidate`

No stage inherits the next stage automatically.
