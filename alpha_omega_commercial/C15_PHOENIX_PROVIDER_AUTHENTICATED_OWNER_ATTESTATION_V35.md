# C15 Phoenix Provider-Authenticated Owner Attestation v35

## Purpose

This dependency-ordered slice prepares the smallest complete provider-authenticated owner-attestation readback route after the v34 custody-attestation intake. It does not publish an attestation, execute an owner-reserved decision, grant provider authority or perform provider apply.

## Operational slice

The private Ops export gains `provider_authenticated_owner_attestation.py`, which:

- verifies the exact v34 challenge, self-attestation, custody receipt and copied packet before preparing any provider message;
- produces a deterministic, low-disclosure GitHub attestation message containing only the challenge and attestation hashes plus explicit non-authorization statements;
- captures GitHub state through GET-only calls to the authenticated user, repository and exact issue-comment endpoints;
- verifies the authenticated account, repository owner, exact comment author, `OWNER` association, exact body, unedited timestamp, challenge window and five-minute readback freshness;
- records no credential value and performs no provider mutation;
- permanently classifies injected transports as `MOCK_CONFORMANCE`, which cannot prove owner identity;
- creates a hash-bound owner-identity receipt only after all route, actor, body, time and freshness checks pass;
- keeps owner authorization, provider authority, provider apply and every external commercial gate separate and false.

## Provider and owner boundary

Provider-native readback can authenticate who published the exact attestation. It cannot independently prove owner control of the destination, create an authorization decision, grant target-provider authority, or prove Cloud Run operation, customer demand, contract, payment, enterprise assurance, partner adoption, production scale or revenue.

Publishing the attestation is an external communication and remains owner-reserved. This repository slice prepares and verifies the route but does not post anything.

## Dependency path

`C03 → C06 → C07 → C11 → C14 → C15`

The complete `C01 → C15` order remains preserved. The service-enabled platform remains prioritised and self-service SaaS remains held.

## Next gate

Exact-head provider proof must pass first. The consequential gate then remains owner execution of the custody ceremony and provider-native publication/readback of the exact attestation message. A separate exact short-lived owner authorization bound to fresh provider authority is still required before any provider apply.
