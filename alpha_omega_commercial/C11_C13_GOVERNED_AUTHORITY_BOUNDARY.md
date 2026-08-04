# C11–C13 Governed Commercial Authority Boundary

## Material defect repaired

The historical `CommercialAssuranceControlPlane` contains reference-only methods that accept caller-supplied approval booleans or arbitrary approval references. Those methods remain for deterministic regression compatibility, but they are not a safe canonical interface for consequential commercial action.

`GovernedCommercialAssuranceControlPlane` is now the canonical C10–C15 API. It removes those caller shortcuts from its public signatures and binds owner-reserved decisions to provider-backed, evidence-bound receipts.

## Canonical controls

### C11 — consequential service requests

`subscription.change` and `tenant.suspend` require an owner decision receipt bound to the exact request identity and payload hash. Accepted requests remain reference-execution-only and set `external_effects_allowed` to `false`.

### C12 — external customer outcomes

A caller cannot promote a study by labelling its evidence external. External publication requires a prior admitted `external_case_study` evidence envelope, live customer-market authority and live owner-decision authority. Otherwise the exact status remains `MARKET_PROOF_REQUIRED`.

### C13 — quote and revenue authority

Quote presentation requires an owner receipt bound to the exact quote terms. Approval does not send the quote and does not create a financial commitment.

Revenue recognition requires all of the following:

- fresh live payment-provider authority;
- provider-native settled-payment evidence;
- exact contract, amount and currency matching;
- a fresh owner decision receipt bound to the payment evidence;
- hash-linked receipt consumption and restart-safe readback.

Mock-provider conformance may exercise the complete contract, but its events are labelled `MOCK_PAYMENT_PROVIDER_CONFORMANCE_ONLY` and are never counted as revenue.

## C15 truth boundary

This slice strengthens succession and canonical API controls. It does not establish customer demand, a signed contract, payment, revenue, subscription, invoice, Cloud Run operation, enterprise assurance, partner adoption, an external customer case study or production-scale reliability.

Owner final authority remains reserved for financial commitments, contracts, external communications, consequential releases and revenue-recognition confirmation.
