# Alpha→Omega Phoenix Authorization Consumption v21

## Purpose

The v20 owner-authorization gate proves that a short-lived mandate is exact, bounded and free of secret material. It did not durably prevent the same valid decision from being presented to more than one execution attempt. V21 closes that replay gap before any provider apply is permitted.

## Smallest complete operational slice

`phoenix/provider_cutover_authorization_use.py` provides a private execution-plane state machine:

1. validate the exact v20 authorization decision and freshness boundary;
2. atomically reserve its `authorization_sha256` using exclusive file creation;
3. return the original record for an exact retry by the same execution;
4. reject reuse by any different execution;
5. permit only `RESERVED → APPLY_STARTED → VERIFIED|ABORTED`;
6. require a SHA-256-bound provider receipt before `VERIFIED`;
7. keep terminal records immutable;
8. detect altered or unreadable state through an independent record hash;
9. persist files with restrictive permissions, file `fsync`, atomic replacement and directory `fsync`.

The same authorization remains consumed after an aborted attempt. A new attempt therefore requires a newly issued short-lived authorization with a new authorization hash.

## Runtime boundary

The state directory belongs in the private `Federation-Omega-Ops` execution plane and must not be committed to source control. This implementation performs no GitHub provider apply, repository creation, Cloud Run action, credential retrieval, payment operation, external communication, financial commitment, contract action or revenue recognition.

## Dependency path

This advances the internal service-platform path:

`C03 → C06 → C07 → C11 → C14 → C15`

It does not advance any external maturity gate.

## Promotion gate

Promotion requires:

- all authorization-consumption regressions pass through the provider-native Federation Omega Airlock;
- Public Repository Leak Guard passes on the exact pull-request head;
- job steps and the immutable Airlock artifact are inspected;
- the exact merge result is reconciled into the v21 checkpoint;
- the private Google Drive release is created and read back before release reconciliation.

## Commercial truth

The service-enabled platform remains prioritised and self-service SaaS remains held. Customer demand, signed contracts, payment-provider operation, Cloud Run operation, enterprise assurance, partner adoption, customer outcomes, production scale and full commercial maturity remain unproven. Verified live revenue remains zero.

Financial commitments, contracts, external communications, consequential releases, execution-plane cutover and revenue recognition remain owner-reserved.
