# Alpha→Omega Provider Dispatch Outbox v11

## Stage path

C03 → C06 → C07 → C11 → C14 → C15.

## Purpose

V10 proves crash-safe exact retry for owner-reserved managed-service actions inside the local commercial control plane. V11 adds the next smallest operational slice: a durable provider-command outbox whose provider idempotency key is derived from the committed V10 action, accepted provider-authority snapshot, exact provider domain, operation and command payload.

The service-enabled platform remains the priority. Self-service SaaS remains held.

## Operational controls

- a committed V10 idempotency-sealed action is required before dispatch preparation;
- the provider command is hash-bound to the action intent, transaction, authority snapshot and acceptance entry;
- exact preparation retry returns the existing record;
- altered command reuse fails closed;
- a deterministic reference-provider adapter proves stable-key and exact-retry conformance without any external mutation;
- mock receipts are hash-bound, restart-safe and permanently excluded from live provider evidence;
- live provider receipts cannot be admitted until a concrete provider-native verifier and fresh external evidence are available;
- state and receipt tampering fail closed.

## Proof boundary

Passing the v11 workflow proves production code, tests, deterministic reference-provider conformance, receipt integrity and repository safety. It does not prove Cloud Run execution, payment-provider operation, a customer action, distributed provider exactly-once execution, production scale, customer demand, contracts, subscriptions, invoices, revenue, enterprise assurance, partner adoption or an external customer outcome.

Cloud Run remains `PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE`. Payment-provider operation remains `PROVIDER_BLOCKED_NO_FRESH_AUTHORITY`. Distributed provider exactly-once execution remains `PROVIDER_PROOF_REQUIRED`. Verified live revenue remains zero.

Financial commitments, contracts, external communications, consequential releases and revenue recognition remain owner-reserved.
