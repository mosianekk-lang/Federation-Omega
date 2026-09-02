# SOVARA EDPF — Prediction Request Contract v1

## Purpose

Standardize how the Federation asks a predictor for a prospective probability without granting that request any dispatch, provider, spend, routing or effect authority.

The contract exists because EDPF requires genuine probabilities that can later be scored against outcomes. Cognitive Policy Market robust scores, route ranks, utility values and consensus counts are useful decision-support quantities, but they are not calibrated event probabilities and must not be transformed into them.

## Request question

Each request binds:

- request and mission identity;
- fixed EDPF/predictor system source head;
- mission snapshot digest;
- prediction domain and exact event;
- explicit outcome criterion;
- request creation time;
- prediction deadline;
- outcome observation window beginning strictly after the prediction deadline;
- evidence refs available before prediction;
- sanitized context;
- matter scope and sensitivity.

The temporal contract is:

`created_at < prediction_deadline_at < outcome_not_before_at <= outcome_deadline_at`

This prevents outcome-period evidence from being part of the request-time state.

## Predictor allocation

Candidate predictors are ranked with the admitted EDPF `predictor_allocation_weight()` using:

- empirical trust from resolved prior predictions;
- domain relevance;
- source independence;
- expected information gain;
- cost; and
- latency.

Selection prefers independent source families first, then fills remaining capacity by allocation score. Multiple model names sharing one source family do not satisfy the independent-source requirement.

Allocation is advisory. It does not authorize dispatch.

## Packet contract

Each selected candidate receives its own deterministic packet and receipt. The packet instructs the predictor to return:

- one explicit probability in `[0,1]` for the defined event;
- expected value;
- expected normalized latency;
- expected normalized owner burden;
- evidence refs available before the prediction deadline; and
- `probability_basis=EXPLICIT_FORECAST_NOT_POLICY_SCORE_TRANSFORM`.

The packet explicitly prohibits deriving probability from policy-market robust scores, route ranks, utility scores or consensus counts.

Every packet carries:

- `provider_call_authorized=false`;
- `dispatch_authorized=false`;
- `external_effect_authorized=false`; and
- `stable_self_promotion_allowed=false`.

## Response contract

A response must bind the exact packet id, request id and request receipt. Predictor id, source-family fingerprint and version must also match the packet.

The response must arrive inside the prediction window and include non-empty evidence refs plus source-readback-or-stronger proof.

For a provider-backed predictor, source readback is insufficient. The response must carry `PROVIDER_READBACK` or `RECEIPT_VERIFIED` proof so a model/provider output cannot be promoted from a caller assertion.

The explicit-probability attestation is a protocol compliance check; it is not proof that a model internally used a particular reasoning process. Later empirical calibration remains the real quality test.

## Ingress conversion

A valid response can be converted into the already-admitted `EDPF_PREDICTION` ingress envelope. Conversion:

- preserves the explicit probability;
- unions request-time and response-time evidence refs;
- carries fixed source head and mission snapshot;
- preserves proof maturity;
- creates a deterministic prediction id and ingress event id; and
- performs no write by itself.

A separate caller must submit the envelope to `LivingStateIngress`. The request contract therefore cannot bypass ingress proof, matter-wall, idempotency, CAS or semantic-readback controls.

## Anti-sprawl

This tranche adds no new model/provider client, scheduler/daemon, prediction database/event store, world model, causal engine, proof plane or authority plane.

## Promotion ladder

`SOURCE_CANDIDATE -> DETERMINISTIC_TESTED -> CI_ADMITTED -> SEPARATELY_AUTHORIZED_REQUEST_DISPATCH -> PROVIDER_OR_INTERNAL_RESPONSE_VERIFIED -> TRANSACTIONAL_PREDICTION_CAPTURED -> LATER_OUTCOME_RESOLVED -> CALIBRATION_POSITIVE -> MATCHED_OWNER_VALUE_PROVEN`

No stage inherits the next stage automatically.
