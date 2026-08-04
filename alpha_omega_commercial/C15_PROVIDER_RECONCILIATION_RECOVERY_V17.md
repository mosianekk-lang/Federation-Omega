# Alpha→Omega Provider Reconciliation Recovery v17

## Dependency-ordered scope

`C03 → C06 → C07 → C11 → C14 → C15`

The service-enabled platform remains the priority. Self-service SaaS remains held.

## Defect closed

V16 durably publishes complete reconciliation evidence before changing the provider-dispatch state. A process interruption after publication but before the state commit leaves a valid content-addressed package that is not yet referenced by the claim history. V16 reports that package as an orphan and permits local pruning, which can destroy the only retained evidence needed to complete a previously valid reconciliation.

## Smallest complete operational slice

V17:

- classifies an unreferenced package as recoverable only when it still binds the exact dispatch, unresolved submitted attempt, fencing epoch, current one-time challenge and provider-attempt envelope;
- protects recoverable packages from orphan pruning;
- keeps invalid, altered and rejected packages separately prunable;
- replays the exact vaulted evidence using the observation time already hash-bound inside the challenge evidence;
- allows recovery after wall-clock challenge expiry because the evidence and replay time were established while the challenge was valid;
- returns an idempotent `ALREADY_RESOLVED` result when the same package has already been committed;
- records a hash-bound local recovery receipt;
- preserves the V16 evidence vault, V15 challenge controls, V14 unknown-outcome quarantine and V13 fencing controls.

## Proof boundary

This implementation proves local restart recovery and deterministic mock-provider conformance only. It does not perform or prove a live provider mutation, provider-native reconciliation, distributed exactly-once execution, Cloud Run operation, payment-provider operation, customer demand, a signed contract, revenue, subscriptions, invoices, enterprise assurance, partner adoption, an external customer outcome or production scale.

Verified live revenue remains zero. Full commercial maturity is not claimed.

## Owner authority

Financial commitments, contracts, external communications, consequential releases and revenue recognition remain owner-reserved.
