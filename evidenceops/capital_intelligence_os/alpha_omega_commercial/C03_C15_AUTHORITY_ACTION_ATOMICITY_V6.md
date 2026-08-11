# C03→C15 Authority Action Atomicity v6

## Verified dependency

This slice follows the merged authority action-binding release in PR #126 at
`35331349e2e9f24db96cdc299db3f3f817670ab6`.

## Material defect closed

The v5 control plane correctly required each consequential commercial object to
carry a hash binding to the exact latest durable provider-authority acceptance.
The action itself still crossed several local persistence surfaces before that
binding was complete. A binding or persistence failure could therefore leave a
service request, quote approval, externally promoted outcome study, revenue
record, owner-receipt consumption or evidence-admission record partially
persisted even though the caller received an exception.

## Smallest complete operational slice

`AtomicAuthoritySnapshotCommercialControlPlane` now:

1. automatically accepts a valid candidate snapshot and then holds the provider
   acceptance lock for the complete consequential action;
2. verifies the exact latest accepted snapshot and required domains under that
   lock;
3. captures the commercial state, commercial ledger, governed owner-authority
   state and ledger, and governed external-evidence state and ledger;
4. writes a hash-linked `ACTION_PREPARED` transaction event;
5. performs the governed action and v5 acceptance binding;
6. seals the resulting object to the exact transaction and acceptance entry;
7. writes `ACTION_COMMITTED` only after all state and binding writes succeed;
8. restores every captured surface byte-for-byte and writes
   `ACTION_ROLLED_BACK` if any step fails;
9. rebuilds the external-evidence controller after rollback so long-lived
   workers cannot retain rolled-back in-memory decisions;
10. rejects transaction-ledger tampering and nested authority transactions.

The acceptance transition itself is retained after an action rollback because it
is an internal, reversible authority-state transition and not a customer,
payment, communication, contract or cloud operation.

## Strategy and truth boundary

The service-enabled platform remains first. Self-service SaaS remains held.

This control proves local atomicity, rollback and receipt integrity only. It does
not prove customer demand, a signed contract, payment, revenue, subscription,
invoice, Cloud Run operation, enterprise assurance, partner adoption, an
external customer case study or production scale. Verified live revenue remains
zero.

Financial commitments, contracts, external communications, consequential
releases and revenue recognition remain owner-reserved.
