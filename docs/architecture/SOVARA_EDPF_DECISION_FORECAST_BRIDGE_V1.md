# SOVARA EDPF Decision → Forecast Bridge v1

Status: SOURCE_CANDIDATE  
Authority ceiling: A1_INTERNAL  
External effects: none

## Purpose

Convert an already-admitted EDPF `SEEK_EVIDENCE` decision into a measurable prospective forecast question without manually re-ranking evidence or reconstructing epistemic metrics.

The bridge only acts on `EpistemicDecisionReceipt.next_evidence_candidate_id`. It cannot choose a different evidence candidate.

## Composition

`EDPF decide() -> SEEK_EVIDENCE + next_evidence_candidate_id -> exact EvidenceCandidate -> evidence-backed ForecastOutcomeContract -> admitted Forecast Opportunity Compiler -> PredictionQuestion`

This is still pre-dispatch. Predictor allocation, provider/model invocation, response capture, Living State ingress and later outcome resolution remain separate admitted layers.

## Source-epoch binding

The bridge requires `receipt.source_version == context.system_source_head_sha`.

A mismatch produces `HOLD / SOURCE_EPOCH_MISMATCH`. The bridge never silently transfers a decision or evidence candidate across source epochs.

## Decision/claim binding

The supplied canonical evidence candidate must:

- exactly match `next_evidence_candidate_id`;
- be unique in the supplied candidate set;
- resolve only claims present in the decision receipt.

Missing or mismatched candidates hold rather than falling back to another candidate.

## Measurable outcome contract

The host supplies a `ForecastOutcomeContract` for the canonical evidence candidate. It contains:

- event;
- outcome criterion;
- prospective prediction deadline;
- later outcome-observation window;
- explicit outcome observability;
- pre-outcome evidence refs;
- evidence refs supporting the observability assessment.

Outcome observability without evidence basis is rejected. A low-observability contract is passed through the admitted Forecast Opportunity Compiler and held by its independent measurability floor.

## Probability boundary

The bridge never generates an event probability. It only creates the question that a later admitted predictor may answer with an explicit probability.

`forecast_probability_generated=false` is invariant.

Canonical EDPF `EvidenceCandidate.decision_flip_probability` remains about whether resolving evidence changes a decision. It is not the forecast event probability.

## Anti-sprawl

No new evidence-ranking model, predictor, provider client, scheduler, daemon, database, registry, world model, causal engine, proof plane, route or authority layer is created.

The bridge composes:

- `EpistemicDecisionReceipt`;
- `EvidenceCandidate`;
- `SOVARA_EDPF_FORECAST_OPPORTUNITY_V1`;
- `PredictionQuestion` through the existing forecast compiler.

## Authority boundary

Always false:

- `forecast_probability_generated`;
- `provider_call_authorized`;
- `dispatch_authorized`;
- `external_effect_authorized`;
- `live_predictor_weight_change_authorized`;
- `stable_self_promotion_allowed`.

## Promotion path

`SOURCE_CANDIDATE -> DETERMINISTIC_TESTED -> CI_ADMITTED -> HOST_INVOKED_SEEK_EVIDENCE_DECISIONS -> PROSPECTIVE_QUESTIONS -> PREDICTOR_RESPONSES -> LIVING_STATE_CAPTURE -> RESOLVED_REAL_OUTCOMES -> SHADOW_CALIBRATION -> OWNER_VALUE`

Source/CI admission proves only deterministic composition and fail-closed binding. It does not prove real prospective usage, predictor superiority, calibration quality, operational intelligence gain or owner value.
