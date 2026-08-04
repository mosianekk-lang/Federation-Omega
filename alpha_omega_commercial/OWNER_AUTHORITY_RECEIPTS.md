# Owner Authority Receipts

## Purpose

Owner-reserved commercial gates must not be advanced by a caller-supplied boolean. A signed contract, payment recognition, partner adoption or external case-study publication can affect programme maturity only when the evidence envelope references a fresh, provider-backed owner decision receipt.

## Required receipt binding

Each receipt binds exactly one owner decision to:

- the canonical owner identity;
- one commercial maturity gate;
- one evidence identifier;
- the evidence content SHA-256;
- an `APPROVE` decision;
- a provider and immutable locator;
- an issuance and expiry window of no more than 30 days;
- a nonce and deterministic receipt SHA-256.

The admission controller also requires fresh `owner_decision` provider authority. Reference-provider or mock conformance cannot grant live owner authority.

## Fail-closed rules

The controller rejects:

- `owner_confirmed=true` without a receipt;
- absent, expired, future-dated or over-long receipts;
- altered receipt hashes;
- wrong owner, gate, evidence ID or evidence hash;
- non-provider-native owner decisions;
- denied decisions;
- receipt reuse for a different evidence item;
- owner receipts when provider authority is not freshly verified.

## Operational boundary

This control strengthens C12, C13 and C15 but does not establish customer demand, a contract, payment, revenue, Cloud Run operation, enterprise attestation, partner adoption, an external case study or production scale. Financial commitments, contracts, external communications, consequential releases and revenue-recognition confirmation remain owner-reserved.
