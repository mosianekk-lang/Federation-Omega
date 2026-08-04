# Alpha→Omega Provider Reconciliation Challenge v15

## Dependency-ordered stage path

`C03 → C06 → C07 → C11 → C14 → C15`

This slice follows the verified v14 provider-dispatch unknown-outcome release in PR #151 and preserves the Alpha→Omega v3 P13/P15 institution boundary.

## Material control defect

V14 correctly quarantines a submitted attempt whose result is unknown and refuses retry until exact reconciliation evidence is supplied. Its mock reconciliation evidence is hash-bound to the quarantined attempt, but no durable one-time request boundary distinguishes fresh lookup evidence from evidence prepared before the current reconciliation request. Live provider reconciliation remains correctly rejected, yet the managed-service contract still needed a replay-resistant challenge layer before a provider-native verifier can be attached safely.

## Smallest complete operational slice

V15 adds:

- a durable, hash-chained reconciliation-challenge history per dispatch;
- exact binding to the unresolved outcome event, dispatch, provider idempotency key, claim, attempt envelope and fencing epoch;
- bounded 5–900 second challenge validity;
- idempotent return of the current unexpired challenge;
- deterministic supersession after expiry;
- rejection of unchallenged, stale, future-dated, mismatched or tampered evidence;
- atomic one-time challenge consumption with the outcome-resolution state write;
- restart-safe readback and challenge-to-resolution integrity verification;
- deterministic mock-provider conformance without external mutation.

## Provider boundary

The implementation does not grant provider authority. A live reconciliation verifier must still supply fresh provider-native identity, scope, lookup provenance and receipt evidence before `LIVE_PROVIDER_NATIVE_RECONCILIATION` can be admitted.

Current classification:

- mock-provider challenge conformance: implemented;
- provider-native reconciliation: `PROVIDER_BLOCKED_NO_FRESH_AUTHORITY`;
- distributed provider exactly-once: `PROVIDER_PROOF_REQUIRED`;
- Cloud Run operation: not proven;
- payment-provider operation: not proven.

## Commercial truth boundary

The service-enabled platform remains first and self-service SaaS remains held. No customer demand, signed customer contract, payment, subscription, invoice, revenue, Cloud Run operation, enterprise assurance, partner adoption, external customer outcome, production-scale operation or full commercial maturity is claimed. Verified live revenue remains zero.

Financial commitments, contracts, external communications, consequential releases and revenue recognition remain owner-reserved.
