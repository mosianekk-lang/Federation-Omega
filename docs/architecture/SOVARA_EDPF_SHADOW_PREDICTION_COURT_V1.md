# SOVARA EDPF — Shadow Prediction Court v1

## Purpose

Measure whether Federation predictors are actually useful on later-observed outcomes without leaking future evidence into prediction-time state.

This court extends EDPF v1. It does not create a new predictor, model, world model, scheduler, memory root, provider executor, proof plane, or authority plane.

## Chronological contract

Every `ShadowPredictionPair` binds:

1. a prediction cutoff;
2. evidence available before that cutoff;
3. a later outcome-observation time;
4. separate outcome-proof references;
5. one source head;
6. predictor identity, domain, and source-family fingerprint.

The court rejects:

- prediction cutoff at or after outcome observation;
- outcome-proof references present in the prediction evidence set;
- prediction evidence not declared pre-outcome;
- mixed source heads;
- mixed real and synthetic evidence modes;
- invalid chronological train/holdout splits.

## Real versus synthetic

`SYNTHETIC_TEST` may prove implementation behavior only. It can never establish empirical predictor quality.

`REAL_MISSION` is required for empirical calibration. A positive real-shadow result additionally requires:

- at least 30 real prediction/outcome pairs;
- at least 10 chronological holdout pairs;
- at least 3 predictor identities;
- at least 2 independent predictor source fingerprints;
- positive holdout Brier gain of at least 0.01 versus the training-only domain base-rate baseline.

The baseline is learned from training outcomes only. Holdout outcomes never influence the baseline or predictor trust used before holdout scoring.

## Metrics

For each predictor/domain cell the court reports:

- training pair count;
- chronological holdout pair count;
- training Brier score;
- holdout Brier score;
- holdout absolute calibration error;
- holdout classification accuracy;
- EDPF trust weight after training only;
- holdout value MAE;
- holdout latency MAE;
- holdout owner-burden MAE.

The court also reports pooled training-base-rate Brier, pooled prediction Brier, Brier gain, and the lowest-holdout-Brier predictor for each observed domain.

## Anti-gaming rules

Model agreement is not evidence independence. Source-family fingerprints are counted separately from predictor names.

A predictor may rank first and still receive no live authority. The court measures forecasting quality; it does not authorize routing changes.

Negative results remain durable evidence and must not be suppressed merely because a challenger underperforms.

## Authority boundary

Always false in this court:

- `live_predictor_weights_changed`
- `live_predictor_weight_change_authorized`
- `dispatch_authorized`
- `external_effect_authorized`
- `stable_self_promotion_allowed`

No provider call, deployment, IAM/WIF mutation, traffic change, publication, communication, billing action, or destructive effect is part of this court.

## Promotion ladder

`SOURCE_CANDIDATE -> DETERMINISTIC_TESTED -> CI_ADMITTED -> REAL_SHADOW_OBSERVED -> CALIBRATION_POSITIVE -> MATCHED_OWNER_VALUE_PROVEN -> separately governed routing candidate`

No stage inherits the next stage automatically.
