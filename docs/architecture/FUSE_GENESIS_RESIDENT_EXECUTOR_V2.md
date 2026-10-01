# FUSE Genesis Resident Executor v2

## Purpose

F323 closes two source-level causes of recurring FUSE execution bottlenecks without introducing a second scheduler, controller, truth root, memory root or Judge.

1. Genesis cold boot previously embedded one historical GitHub main SHA, writer ID and fencing token in source and regression tests.
2. The Resident Host command parsed `--once` but always executed exactly one heartbeat and released, so its default CLI was not actually resident.

## Currentness contract

`SourceEpoch` is now explicit, validated and hash-addressed. It contains:

- signed/current source main SHA;
- active source writer identity;
- fencing token; and
- mission identity.

There is no baked-in fallback epoch. Callers must supply the epoch directly or through:

- `FUSE_GENESIS_SOURCE_MAIN`
- `FUSE_GENESIS_SOURCE_WRITER`
- `FUSE_GENESIS_SOURCE_FENCE`
- optional `FUSE_GENESIS_MISSION_ID`

Missing or invalid currentness fails closed.

Cold-boot state, mission checkpoint, event evidence and session admission all bind to the same epoch digest.

## Resident execution contract

The default Resident Host mode is now a continuous executor loop. It:

- binds one source epoch;
- claims the host under that epoch's fencing token;
- heartbeats continuously;
- can resume persisted PENDING/RUNNING tasks;
- checkpoints before execution;
- commits task results;
- retains idempotency guards;
- requires a newer fence for stale takeover; and
- releases on graceful exit.

`--once` is retained only as an explicit one-heartbeat canary.

## Scheduling boundary

This executor does **not** create schedules.

Scheduling remains external to the Resident Host. For the owner's FUSE estate, Google Apps Script remains the scheduling authority. The host consumes work that an authorized ingress/bridge has already placed into its task queue.

A queued task without an executor handler remains PENDING; the resident host does not invent or self-authorize task effects.

## Proof boundary

Local F323 court: 95/95 PASS.

This proves deterministic source behavior only. It does not prove:

- deployment on a 24x7 owner-controlled host;
- current DriveBus/Windows transport liveness;
- Apps Script-to-host delivery;
- reboot recovery on a physical host;
- provider-loss recovery;
- owner-value improvement; or
- COMPLETE maturity.

Those require separate runtime readback and Judge evidence.
