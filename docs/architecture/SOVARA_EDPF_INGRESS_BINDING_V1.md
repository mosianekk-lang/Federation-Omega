# SOVARA EDPF — Transactional Living State Ingress Binding v1

## Purpose

Allow existing Federation hosts and sensors to submit explicit prospective predictions and later observed outcomes through the already-admitted Living State ingress.

This is a binding, not a predictor and not a scheduler. It does not call Gemini, Copilot, OpenAI, OpenRouter or any other model/provider.

## Why ingress is the seam

`LivingStateIngress` already provides:

- host/event invocation rather than a background daemon;
- envelope validation;
- public-safe secret-shape rejection;
- matter-scope isolation;
- durable idempotency receipts;
- compare-and-swap journal-head fencing;
- atomic event + snapshot + receipt commit; and
- semantic store readback.

EDPF therefore reuses that transaction path rather than creating a second intake service.

## Event classes

### `EDPF_PREDICTION`

Requires:

- `object_kind=EXPERIMENT`;
- `state=PREDICTION_OPEN`;
- explicit `probability` supplied by the predictor/host;
- proof maturity of `SOURCE_READBACK` or stronger;
- mission id;
- fixed EDPF/predictor source head;
- mission snapshot digest;
- predictor id, source-family fingerprint and version;
- forecast event/domain;
- expected value, latency and owner burden;
- optional prediction-time evidence refs;
- prediction receipt/proof ref in the ingress envelope.

The proof-maturity floor is deliberate. The admitted prospective adapter records prediction capture as source-readback evidence; ingress therefore refuses `UNKNOWN` or `DECLARED` prediction proof so a weak host assertion can never be silently uplifted to stronger evidence.

The binding does **not** convert Cognitive Policy Market robust scores, strategy quality scores, ranking scores or other utilities into forecast probability.

### `EDPF_OUTCOME`

Requires:

- the same raw prediction id;
- `object_kind=EXPERIMENT`;
- an explicit boolean `occurred`;
- a resolved state consistent with `occurred`;
- realised value, latency and owner burden;
- later outcome proof refs;
- proof maturity above declared-only;
- the same matter scope as the original prediction.

The admitted prospective adapter enforces later timestamp, separate proof and immutable prediction semantics.

## Transaction semantics

Both event classes run inside the existing Living State ingress transaction. Duplicate event delivery is idempotent. Conflicting event-id reuse and journal-head drift fail closed. Successful writes are restored and semantically read back before the ingress receipt is returned.

## Authority boundary

The binding cannot:

- invoke a model or provider;
- manufacture a prediction probability;
- uplift weak prediction proof maturity;
- dispatch a route;
- change live predictor weights;
- authorize an external effect;
- mutate IAM/WIF;
- deploy traffic;
- spend funds;
- publish or communicate externally; or
- prove predictor superiority.

It only makes genuinely prospective prediction/outcome evidence easier to capture through infrastructure that already exists.
