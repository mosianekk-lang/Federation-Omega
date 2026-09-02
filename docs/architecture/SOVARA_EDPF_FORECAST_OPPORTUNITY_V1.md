# SOVARA EDPF Forecast Opportunity Compiler v1.1

Status: SOURCE_CANDIDATE_CONVERGENCE  
Authority ceiling: A1_INTERNAL  
External effects: none

## Purpose

Remove manual prospective-question authoring without creating a second epistemic scoring model.

The v1.0 compiler correctly preserved the boundary between opportunity score and event probability, but duplicated part of EDPF's already-admitted information-value doctrine. v1.1 converges that responsibility back to the canonical `EvidenceCandidate` object in `benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1`.

## Canonical composition

`EDPF EvidenceCandidate -> canonical information_value() -> forecast measurability gate -> bounded PredictionQuestion -> existing EDPF request contract -> predictor response -> existing transactional Living State ingress -> later outcome -> existing Shadow Prediction Court`

The forecast layer does **not** define its own decision-value weights.

Canonical EDPF owns:

- decision-flip probability;
- uncertainty reduction;
- acquisition cost;
- acquisition risk;
- freshness gain;
- the information-value weighting and decision-sensitivity floor.

The forecast layer owns only:

- event/outcome wording;
- prospective prediction and outcome windows;
- outcome observability;
- semantic question de-duplication;
- bounded question budget;
- compilation into the admitted `PredictionQuestion` contract.

## Information-value boundary

`ForecastOpportunity.score` is exactly `EvidenceCandidate.information_value()` and carries the explicit basis:

`EDPF_EVIDENCE_CANDIDATE_INFORMATION_VALUE`

The compiler sets `local_information_value_model_present=false`.

The score is **not an event probability** and must never be transformed into one. `decision_flip_probability` inside `EvidenceCandidate` describes the chance that resolving evidence changes the decision, not the chance that the forecast event occurs.

## Measurability gate

A prospective forecast is useful for calibration only if its later outcome can be observed and proven. v1.1 therefore requires an explicit `outcome_observability` value and applies a separate floor before compiling a question.

A high canonical information value with poor outcome observability is held rather than admitted into the calibration cohort.

## Anti-duplication

Semantically identical questions within a fixed mission/domain/event/criterion/outcome window collapse to the signal with the strongest canonical EDPF information value, then outcome observability, then deterministic signal ID.

A bounded question budget prevents cognitive fan-out from becoming another workload amplifier.

## Truth and authority boundary

Always false:

- `local_information_value_model_present`;
- `opportunity_scores_are_forecast_probabilities`;
- `provider_call_authorized`;
- `dispatch_authorized`;
- `external_effect_authorized`;
- `live_predictor_weight_change_authorized`;
- `stable_self_promotion_allowed`.

The compiler creates no model/provider call, scheduler, daemon, database, registry, world model, proof plane, causal engine, execution route or authority plane.

## Promotion path

`SOURCE_CANDIDATE_CONVERGENCE -> DETERMINISTIC_TESTED -> CI_ADMITTED -> HOST_INVOKED_REAL_FORECAST_QUESTIONS -> PROSPECTIVE_RESPONSES -> RESOLVED_REAL_OUTCOMES -> SHADOW_CALIBRATION -> OWNER_VALUE`

Source/CI admission proves only canonical information-value reuse, forecast measurability gating and deterministic contract composition. It does not prove smarter operational behavior, predictor superiority, calibration quality or owner value.
