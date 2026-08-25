# SOVARA Sovereign Backup Runtime v1

## Purpose

The admitted backup core already builds and verifies deterministic full, delta,
and no-change snapshots. This runtime adds the missing durable event lifecycle:

`discover → order → reserve → lease → build → upload → read back → commit → recover`

It uses the private alias `SOVARA_PRIVATE_BACKUP_REPOSITORY_V1`. Exact Drive
folders, Gmail identities, credentials, and provider object IDs remain in the
private adapter or KDV. They are not stored in public source.

## Event and state model

Events are at-least-once and carry a strict sequence, type, stable event ID,
source identity/version, due time, and SHA-256 binding for the complete artifact
set. The runtime:

- rejects changed-payload event and idempotency collisions;
- processes only the next sequence;
- holds later events when a sequence is missing;
- uses compare-and-swap state versions;
- leases the single backup lineage;
- recovers expired leases;
- applies bounded retry and dead-letter handling;
- maintains a hash-linked, bounded runtime event window.

## Intelligent code restructuring

The first complete controller prototype exceeded one thousand lines. It was split
before source admission into two bounded components:

- `sovara_sovereign_backup_runtime_state.py` owns events, durable state, hash
  chains, leases, retry timing, sequence selection, and artifact-set binding.
- `sovara_sovereign_backup_runtime.py` owns the private-adapter protocol, provider
  effect reservation, execution, receipt recovery, and compare-and-swap commit.

The compatibility import surface is retained, so callers do not need a second
orchestration layer. Architecture tests cap both modules and prevent the provider
controller from absorbing state-machine responsibilities again.

## Provider-effect contract

Before a provider effect, the private adapter must atomically reserve the
payload-bound idempotency key. Container creation and file upload must themselves
be idempotent and reject changed bytes under an existing logical name.

If the provider receipt exists but the runtime-state commit was lost, the next
cycle imports that receipt and completes state without repeating Drive or Gmail
effects. If provider execution happened but final state compare-and-swap fails,
the runtime reports `PROVIDER_EFFECT_STATE_RECONCILIATION_REQUIRED`; it never
reports the effect as absent.

## Missed-run recovery

An overdue next-sequence event is classified as a missed run. It is processed
before later events and recorded as `MISSED_RUN_RECOVERED`. An unattended
scheduler is operationally proven only after a private adapter detects and
recovers such an event without a chat or owner invocation.

## Security boundary

This runtime does not reuse or modify the security-held monolithic Apps Script
fleet. It does not create Google authority, resolve credentials in public code,
or expose private provider pointers. Existing full and delta provider receipts
remain the recovery baseline while the private adapter is admitted.

## Source/runtime distinction

Source and deterministic tests prove event ordering, leasing, reservation,
idempotency, retry, state reconciliation, and recovery logic. They do not prove
that a private adapter or unattended scheduler is live. Those claims require
provider-native event, upload, download, permission, Gmail, state, retry, and
restore readback.
