# ADR-0002 — Immutable transactional host
Status: ACCEPTED FOR V0.1 CANDIDATE

## Decision
Separate immutable OS image/state from mutable application/data state. Updates are staged as complete versioned system artifacts and require health verification before commitment.

## Required behavior
- A/B or equivalent versioned deployments.
- Staged update, reboot/activation, health court, commit or rollback.
- Recovery environment independent of the active root.
- Persistent data volumes are versioned, backed up and migration-tested.
- Update metadata binds source tree, build manifest, artifact digests and signatures.

## V0.1 proof scope
Build/test harness proves manifest structure and rollback state-machine behavior. Real block-device/firmware rollback remains a later hardware gate.
