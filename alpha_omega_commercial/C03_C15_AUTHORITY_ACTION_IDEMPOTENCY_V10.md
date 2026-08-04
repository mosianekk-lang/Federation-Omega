# Alpha→Omega Commercial Authority-Action Idempotency v10

## Dependency path

This slice follows the verified C03 → C11 → C12 → C13 → C15 coordination-v9 release in PR #135 at `bc0982c176ea543799b9a12b98e136b3f0fc0285`.

The preceding private Google Drive release `18vFykuY7E6okU33SJuOxn4hg9z-Cnh-pDCg6xhiZyEw` was read back before implementation. Its modified time is `2026-08-04T08:18:49.639Z`; it remains owner-only and unshared.

## Material managed-service defect

Provider-process serialization prevents concurrent workers from recovering or mutating the same local commercial state at the same time. It does not by itself make a caller retry safe after an uncertain response. A request can be fully committed while the client misses the response and retries the same owner-reserved operation. Without a durable intent binding, the retry can consume authority again or create another transaction.

## Smallest complete operational slice

V10 adds an exact-request replay boundary to the existing atomic authority-action transaction:

- the stable commercial object identity is the idempotency key;
- a canonical SHA-256 intent binds the complete consequential request excluding retry time;
- the intent seal is written to the same state object inside the existing atomic transaction;
- the seal binds the object, action, transaction, accepted authority snapshot and acceptance entry;
- an exact retry returns the previously committed record;
- an exact retry creates no new transaction and consumes no owner authority again;
- reuse of the same object identity with a different intent fails closed;
- restart readback preserves exact-retry behavior;
- a historical committed object without a v10 seal is not silently replayed;
- seal tampering fails closed.

The implementation remains local managed-service control proof. It does not prove exactly-once execution across an external cloud, payment, customer, partner or messaging provider.

## Strategy and authority boundary

The service-enabled platform remains first. Self-service SaaS remains held.

Financial commitments, contracts, external communications, consequential releases and revenue recognition remain owner-reserved. V10 does not create, infer or claim customer demand, contracts, subscriptions, invoices, payment, revenue, Cloud Run operation, enterprise assurance, partner adoption, an external customer case study or production scale.

## Promotion gate

Promote only after provider-native CI verifies compilation, adversarial exact-retry tests, coordination/journal/crash-recovery regressions, deterministic proof, immutable artifact publication, repository safety controls and all triggered commercial stage workflows. Until then the checkpoint remains `AUTHORITY_ACTION_IDEMPOTENCY_IMPLEMENTED_PROVIDER_PROOF_REQUIRED`.
