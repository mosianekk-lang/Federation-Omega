# Alpha→Omega Phoenix Cutover Authorization Gate v20

## Purpose

This release adds the final fail-closed owner-authority gate before the Phoenix provider cutover can enter apply mode. It does not create repositories, invoke Cloud Run, contact customers, process payments, execute contracts or recognise revenue.

## Dependency path

`C03 → C06 → C07 → C11 → C14 → C15`

The service-enabled platform remains prioritised. Self-service SaaS remains held.

## Operational slice

`phoenix/provider_cutover_authorization.py` validates a short-lived owner-issued authorization capsule against:

- the exact 40-character source commit SHA;
- the exact Core and Ops archive SHA-256 values;
- the exact GitHub account and repository names;
- the selected `USER_SCOPED` or `INSTALLATION_TEMPLATE` authority route;
- explicit Core visibility and mandatory private Ops visibility;
- an authorization lifetime no longer than 30 minutes;
- exact authorization for provider apply and Core/Ops creation;
- explicit denial of Cloud Run, payment, external communication, financial commitment, contract and revenue-recognition actions;
- absence of raw or secret-shaped credentials.

The verifier emits a hash-bound `AUTHORIZED_APPLY` decision receipt only when every condition passes. It performs no provider mutation.

## Provider-native proof route

The regression file is named `tests/test_phoenix_provider_cutover_v3_authorization.py`, so the existing allowlisted Federation Omega Airlock executes it without adding or changing a workflow. Public Repository Leak Guard remains mandatory. Merge is prohibited unless the exact PR head passes both checks and job-step inspection.

## Truth boundary

The code and tests can be promoted independently. The actual provider apply remains:

`OWNER_RESERVED` and `PROVIDER_BLOCKED_FRESH_AUTHORISED_APPLY_REQUIRED`.

No authorization capsule is committed. No credential value is accepted, printed or persisted. Customer demand, signed contracts, payment-provider operation, Cloud Run operation, enterprise assurance, partner adoption, customer outcomes, production scale and full commercial maturity remain unproven. Verified live revenue remains zero.
