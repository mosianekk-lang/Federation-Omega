# SOVARA EDPF — Predictor Evidence Projection v1

## Purpose

Use genuinely prospective, later-resolved Living State predictions to reconstruct EDPF `PredictorProfile` trust for future request allocation without creating a persistent predictor registry or inventing competence scores.

## Exact identity boundary

Empirical evidence is isolated by the full tuple:

`system source head + matter scope + predictor id + domain + source-family fingerprint + predictor version`

Evidence never transfers implicitly across any element of that tuple. A new source epoch, matter, version or source family starts neutral until it produces its own resolved prospective evidence.

## Evidence source

The projection first reuses `compile_real_shadow_pairs()` from the admitted prospective prediction adapter. This preserves the existing chronology, immutable prediction, pre-outcome evidence and later outcome-proof rules.

Synthetic fixtures, retrospective model opinions and unverified historical claims do not enter the empirical profile.

## Profile math

The projection reuses the admitted EDPF `PredictorProfile` and `update_predictor()` implementation. It does not introduce a second calibration formula.

Evidence states are descriptive:

- `NEUTRAL_UNSEEN` — no exact-identity resolved prospective samples; trust remains the existing neutral prior of 0.5.
- `THIN_PROSPECTIVE` — 1–9 resolved samples.
- `OBSERVED_PROSPECTIVE` — 10–29 resolved samples.
- `SHADOW_COUNT_ELIGIBLE` — 30+ resolved samples.

`SHADOW_COUNT_ELIGIBLE` is only a count condition. It does not mean positive calibration. Actual calibration quality remains the responsibility of the admitted EDPF Shadow Prediction Court, including its chronological holdout and Brier-gain gate.

## Request-candidate projection

An explicit `PredictorDefinition` supplies stable identity, provider-backed status and supported domains.

An explicit `MissionPredictorFit` supplies mission-local:

- relevance;
- independence;
- expected information gain;
- cost; and
- latency.

Those fit values are not inferred from historical accuracy. If a mission fit is absent, the candidate is omitted rather than fabricated.

For an exact empirical match, the projected `PredictorCandidate` receives the reconstructed empirical profile. For an unseen exact identity, it receives a fresh neutral `PredictorProfile`.

The existing Prediction Request Contract then remains responsible for source-family diversity and packet compilation.

## Authority boundary

This projection cannot:

- call a model/provider;
- dispatch a request;
- write Living State;
- change live predictor weights;
- prove calibration-positive status;
- prove provider liveness;
- prove owner value;
- authorize an external effect; or
- self-promote a predictor.

## Anti-sprawl

The projection is a pure read over the existing Living State journal. It adds no database, registry store, scheduler, provider executor, world model, causal engine, proof plane or authority plane.
