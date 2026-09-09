# Formation Specification

## Outcome contract

Produce a runnable local kernel that makes the CFBE vNext state distinctions
mechanical. The terminal fruit is a named regression court proving that stale
work, false automatic waiting, false completion, duplicate effects, proof
transfer, malformed coordination, and zero-test success all fail closed.

Phase 2 extends that contract with maximum safe parallelism: one immutable DAG
may expose multiple independent streams and alternate paths, while SQLite
transactions preserve global cost, concurrency, collision and effect-winner
invariants. Parallel work never changes sovereign mission authority.

## Architecture tournament

- Native-only: rejected for Phase 1 because provider deployment is not
  authorized and no single native service owns the cross-provider mission.
- Minimal patch to the legacy convergence engine: rejected because it would
  mix a new versioned denominator and permit model into an admitted v1 surface.
- Independent portable core: viable, but duplicates existing hash-chain and
  durability mechanisms.
- Hybrid (selected): reuse Python/SQLite and the Federation's event-chain,
  idempotency, maturity and proof-before-claim patterns behind a new isolated
  CFBE vNext contract.

## Components

- `MissionContract`: finite versioned owner outcome and exclusions.
- `_SQLiteMissionStore`: append-only events, optimistic concurrency, permits,
  effects, and wait registrations.
- `MissionExecutionKernel`: projection, reconciliation, authority decisions,
  proof invalidation, terminality and cancellation.
- Regression utilities: test-count, Git change and coordination-record guards.
- `ExecutionGraph`: frozen stream dependencies, paths, budgets and Formation
  plan hash.
- `MultiStreamExecutionBridge`: durable dispatch, claims, fencing,
  cancellation, shared proof and sovereign fan-in.
- Logical agents: route, builder, falsifier, evidence, witness, sentinel and
  recovery roles, all effect-free and unable to self-certify.
- Throughput claim gate: at least 30 paired observations plus a deterministic
  one-sided 95% bootstrap lower bound, with equal-or-better quality, proof,
  security and cost.

Frontend, remote API, cache, provider queue, hosted effectful worker and
authentication are `NOT_APPLICABLE` to this local Phase 2 release. Provider
adapters and a durable external event bus require separate authority.

## Security and recovery

Secret-shaped payloads fail closed. Events are hash-linked per mission. Writes
use SQLite transactions and compare-and-swap head checks. Mission revision and
cancellation deactivate stale permits and wait jobs. Rollback is removal of the
additive package or discard of the isolated branch; no provider state changes.

Every verified path binds the result producer to the current fenced claim and
binds a distinct verifier identity to the proof authority fingerprint. A
failed logical worker returns a failure fingerprint while healthy siblings
continue. Only `VERIFIED_LIVE` capability attestations enter an automatically
constructed capability snapshot.

## Promotion

This package may reach only `DETERMINISTIC_TESTED_LOCAL` in this phase. Source
admission, registration, provider readiness, deployment, behavioural operation,
and value proof remain distinct future states.
