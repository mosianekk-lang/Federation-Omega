# Formation specification — transactional persistence court

Date: 2026-08-30  
Mission: `MISSION-CFBE-TRANSACTIONAL-PERSISTENCE-2026-08-30` v1  
Authority: `A1_INTERNAL`  
Cost ceiling: zero new recurring cost  
External effects: prohibited for this mission

## Owner intent

Reconcile the existing Omega completion engine with an incremental transactional persistence foundation, then prove crash recovery, contention safety, migration safety, backup restore and bounded multi-stream behavior. Preserve proof, authority, privacy, creative freedom, inherited source and zero-dilution boundaries. Do not rebuild the inherited SOL 6.1 runtime.

## Governed requirements

| ID | Requirement | Proof state |
|---|---|---|
| R1 | Replace whole-state JSON persistence with an incremental transactional backend | PROVEN locally |
| R2 | Preserve legacy JSON input without destroying or rewriting its source | PROVEN locally |
| R3 | Recover a committed admission interrupted before inherited-sidecar publication | PROVEN locally |
| R4 | Admit exactly one same-host contender for a shared idempotency key | PROVEN locally |
| R5 | Re-run actual-engine CFBE with persistence, backup and scale courts | PROVEN locally |
| R6 | Publish a source-anchored report, contract and proof bundle | Pending until exact remote readback |

## Transaction boundary

One SQLite `BEGIN IMMEDIATE` transaction owns the control-state revision, changed state rows, append-only control events, idempotency reservations and admission-outbox entry. The inherited SOL worker and audit sidecars are materialized idempotently after commit. An interrupted post-commit materialization is resumed from the durable outbox at startup.

## Effect routes

- Local code, tests, benchmark, documentation and archive: A1 internal.
- Persistent artifact upload: permitted only after local proof completion, through one authenticated connector path with exact metadata readback.
- Live OpenAI, Gemini, Copilot or media-provider calls: not authorized by this mission.
- Deployment, repository mutation, recurring infrastructure and multi-host activation: not authorized.

## Stop and rollback

Fail closed on stale revisions, malformed migration input, integrity failure, duplicate/conflicting idempotency keys, uncertain provider state, absent proof or authority expansion. Preserve the legacy source and SQLite database or online backup. No deployment rollback exists because nothing was deployed.

## Release boundary

Maximum release is `SHADOW_ONLY` / `LOCAL_SHADOW_TESTING_ONLY`. `READY`, `DEPLOYED`, `PROVEN_IN_PRODUCTION` and `CFBE-GOLD` are not claimed. Remaining gates are live-provider readback, multi-host coordination, 10,000-mission/seven-day soak, hidden-suite evidence and real photo/video quality plus export-lineage evidence.
