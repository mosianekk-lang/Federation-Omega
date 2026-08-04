# Alpha→Omega Phoenix Authorized Provider Execution v22

## Dependency path

`C03 → C06 → C07 → C11 → C14 → C15`

## Smallest complete operational slice

V22 closes the gap between the v20 exact owner-authorization decision, the v21 durable one-time authorization-consumption record, and the existing Phoenix v3.1 provider cutover controller.

The exported private Ops package now uses `provider_cutover.py` as an authorization-enforcing coordinator. It binds one execution identity to:

- one unexpired `AUTHORIZED_APPLY` owner decision;
- the exact legacy source commit;
- the exact Core and Ops archive SHA-256 values;
- one accepted provider-authority mode;
- one durable authorization-use state record; and
- one hash-bound, semantically verified provider cutover receipt.

## Fail-closed execution contract

Before starting a provider apply, the coordinator verifies the decision, source commit, archive digests, provider authority presence, controller package and execution identity. Missing provider authority does not consume the owner authorization.

Once the durable state reaches `APPLY_STARTED`, a process failure, missing receipt or invalid receipt is classified as `PROVIDER_OUTCOME_RECONCILIATION_REQUIRED`. The same authorization is never retried automatically. A later run may only admit an existing receipt that passes embedded SHA-256 integrity and exact provider semantic readback.

Reconciliation remains possible after the original authorization expires because `APPLY_STARTED` is already bound to the exact prior authorization and archives. An expired authorization cannot start a new apply.

## Provider-proof boundary

This implementation and its mock-provider regression suite do not create repositories, alter GitHub settings, apply a ruleset, deploy Cloud Run, process payment, contact customers or advance any external commercial gate.

The live Core/Ops cutover remains:

`PROVIDER_BLOCKED_FRESH_AUTHORISED_APPLY_REQUIRED`

It requires a fresh exact owner authorization decision and suitable GitHub provider authority in the private Ops execution plane.

## Commercial truth boundary

- Service-enabled platform: prioritised.
- Self-service SaaS: held.
- Core repository: not created by this slice.
- Private Ops repository: not created by this slice.
- Customer demand: `MARKET_PROOF_REQUIRED`.
- Signed customer contract: not proven.
- Payment-provider operation: `PROVIDER_BLOCKED_NO_FRESH_AUTHORITY`.
- Cloud Run operation: not proven.
- Enterprise assurance: unverified.
- Partner adoption: `MARKET_PROOF_REQUIRED`.
- Production scale: `PRODUCTION_PROOF_REQUIRED`.
- Verified live revenue events: `0`.
- Full commercial maturity: not claimed.

Financial commitments, contracts, external communications, consequential releases, execution-plane cutover and revenue recognition remain owner-reserved.
