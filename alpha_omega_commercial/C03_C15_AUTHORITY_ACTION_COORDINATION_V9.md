# Alpha→Omega Commercial Authority-Action Coordination v9

## Dependency path

`C03 → C11 → C12 → C13 → C15`

This slice follows the verified journal-v8 checkpoint in PR #133 at `0b0ee4a14f6a514707690f085b8af5d25031486f` and the private Google Drive readback `1XXfR6s8g76tFlqZrEofmy4x7eSet1WsEg1sE8iGQh9Q`.

## Material defect

V8 guarantees atomic publication of transaction events. A different worker could still start while a live worker had published `ACTION_PREPARED` but had not yet published its terminal event. Startup recovery could therefore classify a live transaction as crashed and restore its recovery bundle while the original worker was still operating.

## Smallest complete operational slice

`CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane` adds one provider-process coordination lock around:

- journal cleanup during startup;
- durable restart recovery during startup;
- every live governed commercial action;
- transaction and governed-authority integrity readback.

The lock uses a process-local reentrant lock and a POSIX provider-process file lock. A concurrent startup waits for the active transaction's durable terminal event. A real process crash releases the operating-system lock, allowing the next worker to recover before admitting new work.

## Preserved controls

- v8 atomic, filename-bound transaction event publication;
- v7 durable recovery bundles and exact restart restoration;
- v6 atomic prepare/commit/rollback and state restoration;
- v5 exact latest provider-authority acceptance binding;
- provider-backed owner decision receipts;
- service-enabled platform priority before self-service SaaS.

## Proof gate

Promotion requires production compilation, adversarial coordination tests, deterministic proof receipt, all commercial and authority regression workflows, repository control-plane enforcement, leak checks, job-step inspection and retained artifact inspection.

## Truth boundary

This control proves local multi-worker coordination only. It does not prove distributed provider atomicity, Cloud Run operation, customer demand, contracts, payment, revenue, subscriptions, invoices, enterprise assurance, partner adoption, external customer outcomes or production scale. Verified live revenue remains zero. Self-service SaaS remains held. Financial commitments, contracts, external communications, consequential releases and revenue recognition remain owner-reserved.
