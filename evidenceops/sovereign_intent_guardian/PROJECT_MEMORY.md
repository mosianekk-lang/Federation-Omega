# Project memory

## Durable decisions

1. Keep SIG separate from the existing AI ICT durable overlay. That overlay protects encrypted model pause/resume state and approval coverage; SIG has a different lifecycle and uses `sig_*` tables in a separate database.
2. Keep Formation as the only action authority. SIG output is negative-only and never grants release.
3. Compute fifth-output cadence from an idempotent delivered-output ledger. Caller- or provider-supplied counts are rejected.
4. Make stop/resume a generation-fencing event. An active latch blocks every matching version; resume terminally quarantines old work and persists an enqueue/claim minimum-version floor.
5. Store dead-letter codes and hashes only. Raw provider bodies, exceptions, evidence and credentials are excluded.
6. Accept no executable provider. Only data-only, hash/reference advisory receipts may be validated; they cannot lower deterministic severity.
7. Describe current state as `DURABLE_FOUNDATION_IMPLEMENTED_NOT_DEPLOYED`; never infer deployment, persistence proof or autonomy from files, tests or database rows.
8. Convert every reproduced defect into a deduplicated adaptive incident, smallest existing-control patch, failure-first test and healthy-case test. Never self-promote the repair.
9. Treat configured attestation and resume registries as exact local allowlists, not authenticated external authority. Bind the complete request/action capsule and state the missing issuer/signature trust layer truthfully.

## Known future gaps

- no deployed scheduler or supervisor;
- no live multi-host persistence or database migration;
- no production authentication or encryption-at-rest boundary;
- no provider credential route or provider call;
- no deployed worker identity or independent runtime attestation;
- no live stop-race canary;
- no merge or deployment authority.

Any future cycle must reopen current documentation, Formation, OIFA, source and publication gates before changing those states.
