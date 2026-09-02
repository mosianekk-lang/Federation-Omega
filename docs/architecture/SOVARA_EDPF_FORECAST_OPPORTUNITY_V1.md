# SOVARA EDPF Forecast Opportunity Compiler v1

Status: SOURCE_CANDIDATE
Authority ceiling: A1_INTERNAL
External effects: none

## Purpose

Remove the remaining manual question-authoring bottleneck in the admitted EDPF prospective calibration path. The compiler turns mission uncertainty signals into a small ranked set of measurable prospective `PredictionQuestion` objects that can be passed to the already-admitted provider-neutral request contract.

It does **not** predict the event. It only decides which uncertainties are worth forecasting.

## Composition

`mission uncertainty signal -> forecast-opportunity score -> measurable PredictionQuestion -> existing EDPF request contract -> predictor response -> existing transactional Living State ingress -> later outcome -> existing Shadow Prediction Court`

The compiler reuses `federation.living_state.edpf_prediction_request.PredictionQuestion` for source-head, chronology, context, matter-scope and sensitivity validation.

## Opportunity score

The opportunity score measures expected decision value from resolving uncertainty. It combines:

- decision-sensitive uncertainty;
- probability that resolving the uncertainty could flip a decision;
- decision impact;
- outcome observability;
- acquisition cost;
- owner burden.

The score is **not a forecast probability**. It must never be transformed into an event probability or used as evidence that an event will occur.

## Anti-duplication

Semantically identical questions within a fixed mission/domain/event/criterion/outcome window collapse to the highest-scoring signal. A bounded question budget prevents cognitive fan-out from becoming another workload amplifier.

## Truth and authority boundary

Always false:

- `opportunity_scores_are_forecast_probabilities`;
- `provider_call_authorized`;
- `dispatch_authorized`;
- `external_effect_authorized`;
- `live_predictor_weight_change_authorized`;
- `stable_self_promotion_allowed`.

The compiler creates no model/provider call, scheduler, daemon, database, registry, world model, proof plane, causal engine, execution route or authority plane.

## Promotion path

`SOURCE_CANDIDATE -> DETERMINISTIC_TESTED -> CI_ADMITTED -> HOST_INVOKED_REAL_FORECAST_QUESTIONS -> PROSPECTIVE_RESPONSES -> RESOLVED_REAL_OUTCOMES -> SHADOW_CALIBRATION -> OWNER_VALUE`

Source/CI admission proves only deterministic opportunity selection and contract composition. It does not prove smarter operational behavior, predictor superiority, calibration quality or owner value.
