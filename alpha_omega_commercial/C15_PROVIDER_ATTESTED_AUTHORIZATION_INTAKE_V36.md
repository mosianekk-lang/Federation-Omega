# C15 Phoenix Provider-Attested Authorization Intake v36

## Purpose

This dependency-ordered slice prepares the smallest complete non-executing intake between the provider-authenticated owner-attestation capability and the existing owner/provider-authority-bound cutover. It does not create an attestation, authorization, credential, provider authority or provider mutation.

## Operational slice

The private Ops export gains `provider_attested_authorization.py`, which verifies:

- a hash-valid, fresh, provider-native owner-identity attestation receipt;
- a hash-valid, fresh provider-authority receipt with sufficient repository-administration scope;
- an exact owner authorization decision bound to both receipt hashes, the authenticated owner, repository, comment, authority mode and repository-creation endpoint;
- a maximum five-minute validity window;
- preserved owner authority and unchanged external commercial gates.

The resulting intake receipt is deterministic and hash-bound. It records that no provider request, provider apply, authorization-consumption state, credential value, external communication or commercial-gate advancement occurred.

## Dependency path

`C03 → C06 → C07 → C11 → C14 → C15`

The complete `C01 → C15` order remains preserved. The service-enabled platform remains prioritised and self-service SaaS remains held.

## Truth boundary

This slice does not prove owner-controlled custody, owner execution, a published provider attestation, owner identity authenticity, an owner authorization decision, execution-provider authority, target-repository creation, Cloud Run operation, customer demand, contract, payment, enterprise assurance, partner adoption, production scale, revenue or full commercial maturity.

## Next gate

Exact-head provider proof must pass first. The consequential sequence remains owner execution of the custody ceremony, provider-native publication/readback of the exact attestation, a separate exact short-lived owner authorization bound to fresh provider authority, and only then an owner-reserved apply with provider-native readback.
