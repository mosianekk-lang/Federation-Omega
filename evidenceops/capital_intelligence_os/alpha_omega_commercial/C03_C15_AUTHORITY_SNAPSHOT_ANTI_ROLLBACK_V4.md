# C03→C15 Authority Snapshot Anti-Rollback v4

## Operational defect closed

A provider-native authority snapshot could be hash-valid, correctly scoped and
still unexpired while also being older than a snapshot already accepted by the
commercial control plane. Without durable ordering, that older snapshot could be
replayed after authority had advanced.

## Smallest complete operational slice

The canonical `AuthoritySnapshotCommercialControlPlane` now persists each accepted
live-authority snapshot in a hash-linked, restart-safe ledger. Acceptance is:

- idempotent for the exact same snapshot hash;
- monotonic by `generated_at`;
- fail-closed for equal-time conflicting snapshots;
- fail-closed when a snapshot ID is reused with different content;
- fail-closed when a superseded source-ledger head is reintroduced;
- bound to the existing snapshot, domain, scope, provider-evidence, freshness and
  expiry validation;
- exposed through deterministic readback.

The acceptance operation is internal only. It does not send communications, create
a contract, make a financial commitment, recognize revenue, operate Cloud Run or
advance any external commercial gate.

## Dependency projection

| Stage | Effective control |
|---|---|
| C03 | Provider authority snapshots are hash-valid, fresh and monotonic |
| C11 | Service-enabled actions reject superseded authority |
| C12 | External evidence promotion rejects superseded market authority |
| C13 | Quote and revenue controls reject superseded owner/payment authority |
| C15 | Commercial succession state includes restart-safe anti-rollback receipts |

## Strategy and truth boundary

The service-enabled platform remains first. Self-service SaaS remains held.

This control does **not** prove customer demand, a signed customer contract,
payment, revenue, subscriptions, invoices, Cloud Run operation, enterprise
assurance, partner adoption, an external customer case study or production scale.
Financial commitments, contracts, external communications, consequential releases
and revenue recognition remain owner-reserved.
