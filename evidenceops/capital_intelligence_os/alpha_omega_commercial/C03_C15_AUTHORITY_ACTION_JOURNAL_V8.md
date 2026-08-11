# Alpha→Omega Commercial Authority Action Journal v8

## Dependency order

This slice follows the verified C03 → C11 → C12 → C13 → C15 v7 crash-recovery release in PR #130. It does not reopen or reorder C01–C15.

## Material defect

The v7 control plane writes a durable recovery bundle before `ACTION_PREPARED` and restores any prepared transaction that lacks a terminal event after restart. The transaction history itself remained one append-only JSONL file. An abrupt process exit during `ACTION_PREPARED`, `ACTION_COMMITTED`, or `ACTION_ROLLED_BACK` append could leave a partial final JSON line. That is safe from unsupported commercial promotion because startup fails closed, but it can prevent deterministic recovery and make the service-enabled platform unavailable.

## Smallest complete operational slice

`JournalSafeAtomicAuthoritySnapshotCommercialControlPlane` preserves the complete v7 recovery model and adds:

- a frozen, verified legacy JSONL prefix;
- one independently published file for every new transaction event;
- exact sequence and previous-event chain continuity across legacy and v8 records;
- event SHA-256 binding in both the file name and JSON payload;
- exclusive temporary-file creation;
- file flush and `fsync` before publication;
- atomic rename into the journal;
- journal-directory `fsync` after publication;
- removal of incomplete temporary publications before restart recovery;
- rollback of any durable prepared transaction that lacks a durable terminal event;
- fail-closed handling of malformed names, unreadable entries, sequence drift, hash drift, gaps and tampering;
- restart-safe readback of legacy, atomic and incomplete event counts.

A process crash can now expose either the preceding valid journal or the complete new event. It cannot expose a partially published v8 transaction event.

## Service-first boundary

This hardening improves the local managed-service control plane. It does not promote self-service SaaS or perform external provider effects. It does not send a quotation, execute a contract, create a financial commitment, recognise revenue, invoke Cloud Run, operate a payment provider, publish a customer case study or claim production scale.

## External maturity boundary

The following remain unproven or blocked:

- customer demand and price acceptance — `MARKET_PROOF_REQUIRED`;
- signed customer contract — not proven;
- payment-provider operation or revenue receipt — `PROVIDER_BLOCKED_NO_FRESH_AUTHORITY`;
- Cloud Run operation — `PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE`;
- enterprise attestation — unverified;
- partner adoption — `MARKET_PROOF_REQUIRED`;
- external customer outcome — `MARKET_PROOF_REQUIRED`;
- production scale and distributed provider atomicity — `PRODUCTION_PROOF_REQUIRED`.

Verified live revenue remains zero. Financial commitments, contracts, external communications, consequential releases and revenue-recognition confirmation remain owner-reserved.

## Promotion gate

Promote v8 only after provider-native CI compiles the package, passes the v8 adversarial suite and all triggered commercial regressions, executes the deterministic proof, validates the contract and checkpoint, passes repository safety controls, and publishes an inspected immutable artifact. A separate external release/readback cycle is required before any new Google Drive release claim.
