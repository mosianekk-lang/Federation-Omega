# SOVARA EDPF — Prospective Cohort Census v1

## Purpose

Provide a read-only answer to one operational question:

> Does the existing Living State journal contain enough genuinely prospective, resolved prediction/outcome evidence to enter the admitted EDPF Shadow Prediction Court?

The census does not score calibration quality and does not create another store, scheduler, predictor, proof plane or authority layer.

## Cohort identity

A cohort is isolated by:

- fixed EDPF/predictor system source head; and
- matter scope.

A source-head change starts a new calibration epoch. A matter-scope change starts a separate evidence cohort. Counts are never pooled across either boundary.

## Counted states

The census consumes the existing Living State event journal and recognizes only the admitted EDPF prospective-intake schema.

For each cohort it reports:

- unresolved/open prediction count;
- resolved prediction/outcome count;
- occurred / not-occurred outcome counts;
- predictor identities;
- independent predictor source-family fingerprints;
- observed domains;
- possible chronological holdout count;
- additional resolutions, predictors and independent sources still required.

Resolved observations are compiled through the existing `compile_real_shadow_pairs()` validator before they count. Prediction mutation, bad event order or malformed prospective chronology fails closed.

## Readiness versus proof

`count_ready_for_shadow_court=true` means only that a cohort satisfies the current structural floors:

- at least 30 resolved real prospective pairs;
- at least 10 pairs available for chronological holdout;
- at least 3 predictor identities; and
- at least 2 independent source-family fingerprints.

It does **not** mean that prediction quality is positive.

The census therefore always emits:

- `empirical_calibration_evaluated=false`;
- `empirical_calibration_proven=false`;
- `owner_value_proven=false`;
- `live_predictor_weights_changed=false`;
- `live_predictor_weight_change_authorized=false`;
- `dispatch_authorized=false`;
- `external_effect_authorized=false`;
- `stable_self_promotion_allowed=false`.

Actual calibration quality remains the responsibility of the admitted Shadow Prediction Court, including Brier gain against the training-only baseline.

## Anti-sprawl rule

The census is a pure projection over `LivingWorldModel.export_event_log()`. It persists nothing.

## Promotion significance

The census closes an observability gap between prospective intake and empirical evaluation. It allows the Federation to know exactly when enough real observations exist for a statistically bounded shadow court without mistaking mere sample accumulation for intelligence gain.
