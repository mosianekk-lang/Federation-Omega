# Federation Artifact Fabric v3

## Purpose

Federation Artifact Fabric v3 converts artifact delivery from a sequence of chat-managed best-effort writes into a provider-neutral, fail-closed transaction. The owner-private Drive adapter remains the mandatory user-facing delivery target, while the public source core contains no exact private folder IDs, credentials, secret values or provider authority.

## Terminal rule

`DELIVERED` is emitted only after the following cumulative states are committed:

`RECEIVED → QUARANTINED → VALIDATED → DRIVE_WRITE_PENDING → DRIVE_WRITTEN → READBACK_VERIFIED → REGISTRY_COMMITTED → RECEIPT_SIGNED → DELIVERED`

`HOLD`, `FAILED` and `DEAD_LETTER` are explicit non-terminal or adverse states. A successful upload call, file ID, checksum, registry row, HTTP response or background job is not sufficient on its own.

## Core design

1. **Exact-byte admission** — the gateway accepts bytes, a safe artifact name, media type, workstream, version, symbolic destination alias, retention class and sensitivity class.
2. **Quarantine and inspection** — metadata, content, MIME/extension agreement and supported archives are inspected before provider write.
3. **Content-addressed idempotency** — the key binds SHA-256, artifact name, workstream and version. A duplicate resumes or reuses the existing transaction; a collision fails closed.
4. **Transactional ledger** — SQLite provides an atomic local/private-runtime reference implementation, generation fencing and a hash-linked append-only event chain.
5. **Provider adapter** — `put_if_absent` and exact provider readback prevent a crash between write and ledger commit from causing duplicate delivery.
6. **Projection adapter** — the owner dashboard remains a projection. It must be semantically read back before delivery advances.
7. **Detached signing** — production requires a private external or KMS-backed signer. The included HMAC signer is explicitly test-only.
8. **Reconciliation** — independent inspection detects hash, size, parent, MIME, sharing, trash and registry drift. Projection repair is allowed only after exact provider proof.
9. **Merkle anchoring** — the ledger can compute a deterministic delivered-receipt Merkle root. External immutable anchoring is a separate provider gate.
10. **Migration** — v2 records may be imported only when exact provider readback is already verified and the artifact is private. Migration never pretends to rescan unavailable historical bytes or replay the provider write.

## Security controls

- Private keys, access tokens, API keys, bearer tokens, assigned secrets and hidden-reasoning markers are rejected.
- Secret references are allowed only through symbolic `_ref`, `_reference`, `_alias`, `_handle`, `_fingerprint`, `_sha256` or `_id` fields.
- Raw provider IDs are rejected from the public source destination field; private adapters resolve symbolic aliases.
- Macro-enabled and executable artifact types require a separate controlled lane and are rejected here.
- ZIP and OOXML containers are bounded by entry count, per-entry size, total uncompressed size, compression ratio, nesting depth, path traversal, duplicate-name, encryption and symbolic-link checks.
- No email or other external-send surface exists in the gateway core.

## Recovery

A retryable provider or projection failure moves the exact transaction to `HOLD` with its previous state recorded. The next eligible attempt resumes from that state. Repeated unchanged failures move the transaction to `DEAD_LETTER`; rearming is explicit. Security failures do not auto-retry the same bytes.

## Provider deployment ladder

1. Private executor identity and exact owner-private Drive target.
2. Durable transactional store and private signer.
3. Bounded zero-traffic canary.
4. Duplicate, crash, projection-outage and readback-mismatch canaries.
5. Drive change observer and drift repair.
6. Dead-letter replay and exact-byte restoration.
7. Immutable hash-anchor or evidence mirror.
8. Sustained soak and independent JARVIS, CFBE and Sentinel closure.
9. Promotion to `FULLY_ESTABLISHED` only after every applicable gate passes.

## Truth boundary

The source core and deterministic tests prove the transaction model, local persistence, event-chain integrity, idempotency, fault recovery, security scanning and reconciliation logic. They do not create a private provider runtime, cloud identity, immutable bucket, Drive push channel or sustained operational evidence.
