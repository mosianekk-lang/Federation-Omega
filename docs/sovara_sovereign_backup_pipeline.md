# SOVARA Sovereign Backup Pipeline v1

## Objective

Turn every material admitted SOVARA/Federation state change into a deterministic,
recoverable backup without placing private Drive IDs, Gmail identities, provider
credentials, or secret values in public source.

The public core builds and verifies the backup. A separately authorised private
adapter resolves `SOVARA_PRIVATE_BACKUP_REPOSITORY_V1`, uploads the result,
downloads it for hash verification, checks owner-only permissions, and optionally
sends a Gmail continuity receipt.

## Events

The pipeline accepts these material triggers:

- admitted source release;
- Live Bible revision;
- provider canary;
- deployment;
- rollback;
- material configuration change;
- manual checkpoint.

A first snapshot is full. Later snapshots are deltas containing only new or
changed artifacts plus deletion tombstones. Every seventh snapshot is a full
checkpoint by default. An unchanged event emits a no-change manifest and receipt
rather than another duplicate archive.

## Integrity model

Each artifact receives a SHA-256 digest. The canonical manifest binds the event,
source identity, source version, sequence, previous manifest, previous receipt,
complete current artifact index, changed artifact set, deletion set, and truth
boundary. ZIP members use a stable order and timestamp so the same input produces
the same bytes.

A provider result is not successful until the uploaded archive is downloaded,
rehash-verified, CRC-tested, and checked against the manifest. The destination
must read back as owner-only and private. A changed payload may not reuse an
existing idempotency key.

## Gmail continuity policy

The manifest and checksum may be attached to a continuity email. The archive is
attached only when every selected artifact is explicitly email-eligible and the
archive is under the configured size ceiling. Otherwise the email carries the
integrity receipt and private destination alias, while the exact provider pointer
remains in the private registry.

## Restore

Restore starts from a verified full archive and applies ordered deltas. Every
step must advance the sequence and match the prior-manifest hash. Removed files
are deleted, changed files replace prior bytes, and the reconstructed artifact
set and hashes must exactly match the latest manifest.

## Source/runtime boundary

This source proves deterministic planning, archive construction, restore logic,
idempotency, privacy checks, and the private-adapter contract. It does not prove
that a scheduler is live, a Drive folder was written, Gmail was sent, or a restore
ran in a provider environment. Those claims require provider-native receipts.

## Reuse decision

The pipeline composes existing Federation principles—hash-verified backup,
proof-before-claim, private alias resolution, Airlock admission, exact readback,
route idempotency, and Gmail continuity—rather than creating another orchestration
system or another public workflow.
