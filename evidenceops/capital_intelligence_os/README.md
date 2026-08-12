# EvidenceOps Capital Intelligence OS — v1.0.0-rc6

CIOS rc6 advances the internally executable maturity lanes while provider production remains separately blocked and proof-gated.

## Current states

- Internal product route: **rc5 admitted**
- Scientific state: **`SYNTHETIC_DETERMINISTIC_QUALIFICATION_CANDIDATE`**
- Portfolio state: **`PORTFOLIO_DEMONSTRABLE_CANDIDATE`**
- Provider maturity: **`PROVIDER_BINDING_READY`**
- Production claim: **false**

The states are intentionally independent. A strong synthetic qualification or portfolio demonstration cannot be used as evidence of provider deployment or real-world investment performance.

## rc5 product route retained

`tenant auth → bounded document ingestion → integrity hash → classified vault → dedupe/version → search → diligence → digest-bound workspace export`

Reference ingestion supports text/CSV, JSON, RFC822 email, DOCX and XLSX. PDF remains fail-closed unless an explicit external extracted-text source is supplied and labelled.

## rc6 qualification court

`InternalQualificationCourt` applies transparent independent expected values and counterfactual checks across:

- DCF analytic value;
- WACC monotonicity;
- terminal-growth monotonicity;
- IRR and MOIC analytic values;
- enterprise-to-equity bridge;
- evidence-thresholded QoE adjustments;
- working-capital normalisation;
- debt-like item inclusion;
- diligence empty/partial/full boundaries;
- acquisition-thesis hard gates;
- final-decision/live-order/private-to-market authority controls;
- full synthetic journey invariants;
- missing-evidence counterfactual;
- off-thesis counterfactual;
- deterministic replay of economic/decision fields.

Every check is fatal for the synthetic qualification receipt. The receipt is deterministic and digest-bound.

### Scientific truth boundary

This qualification proves transparent deterministic/synthetic behavior only. It is **not** historical-deal calibration, investment-performance validation, accounting assurance, legal/tax advice or production provider proof.

## rc6 proof-safe demonstration pack

`CIOSDemoPackBuilder` will generate a complete synthetic portfolio bundle only when both the synthetic MVP journey and qualification court pass:

- `manifest.json`
- `decision_brief.json`
- `qualification_receipt.json`
- `case_study.md`
- `dashboard.html`
- `pack_receipt.json` when written to disk

The pack is explicitly labelled `PUBLIC_SAFE_SYNTHETIC_DEMONSTRATION`. It preserves visible evidence contradictions, requires human final decision authority, denies live orders and denies private-M&A-to-public-market export.

The case study may only describe implemented/proven software behavior. It explicitly disclaims real customer, company, transaction, investment-performance or production claims.

## Runtime authority remains unchanged

Authenticated/default-deny product routes remain:

- `GET /health`
- `GET /ready`
- `GET /v1/verify`
- `POST /v1/events`
- `POST /v1/documents`
- `POST /v1/search`
- `GET /v1/diligence`
- `GET /v1/workspace`

Trade, orders, transfers, withdrawals, payments, signing and regulatory-filing route families remain unexposed.

## Next finish gates after rc6

Without waiting for Google/provider authority, CIOS should next pursue:

1. generate/read back the exact-source demo pack as an actual user-visible artifact;
2. build representative historical/public transaction calibration datasets with explicit source/licensing provenance;
3. compare deterministic reference models against independently sourced deal/financial outcomes;
4. add false-positive/false-negative and calibration-error reporting;
5. conduct product pilot/value measurement with real consenting users when available.

The separate Sparks lane remains:

`authorised private provider → canary → provider readback → enterprise controls → ProductionQualificationGate → PRODUCTION_VERIFIED`
