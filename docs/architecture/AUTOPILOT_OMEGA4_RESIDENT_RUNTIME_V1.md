# AutoPilot Omega4 Resident Runtime v1

Status: `SOURCE_CANDIDATE / UNATTENDED_SAFE_CYCLE / NO_FULL_AUTOPILOT_CLAIM`

## Purpose

AutoPilot Omega4 closes the first practical gap between Federation work selection and unattended execution. The existing scheduler can identify work and the existing Bubbles AutoPilot can select safe work, but neither is itself a background executor. This tranche adds a hosted resident-cycle worker for an explicitly allow-listed subset of `NO_EFFECT` / read-only maintenance work.

## Control loop

`WAKE -> RESTORE STATE -> RECONCILE REGISTRY -> EXECUTE DUE SAFE HANDLERS -> EMIT PROOF -> PERSIST STATE -> PARK`

The workflow wakes hourly, after a successful `Bubbles Command Bus` push run on `main`, or by explicit manual dispatch. Pull requests execute the contract tests only; resident execution is not enabled from an unadmitted branch.

## Admitted handlers

The first version reuses existing implementation owners:

- `EXT-001` lane dependency/blocker watch;
- `EXT-004` continuity checkpoint;
- `EXT-011` cross-system capability heartbeat;
- `EXT-012` objective-completion continuity evaluation;
- `EXT-013` cloud-capability inheritance audit.

Unknown READY tasks are held with `NO_RESIDENT_SAFE_HANDLER_ADMITTED`. Any handler whose effect class is not `NO_EFFECT` is held with `RESIDENT_EFFECT_CLASS_NOT_ALLOWED`.

## Durability

Each successful hosted cycle emits:

- `resident-receipt.json` — immutable cycle evidence;
- `resident-state.json` — generation and task-cursor state.

The latest state artifact is restored on the next cycle. Cadence buckets make recurring work idempotent inside its execution window. If durable state is unavailable or expired, the worker safely starts a new generation; restoration never grants effect authority.

GitHub artifact persistence is the v1 hosted continuity substrate. It is intentionally not presented as the final durable workflow substrate. A later Temporal/DBOS/Restate/Dapr-class provider may replace the persistence/parking layer without replacing CFBE, Bubbles, ProofOS or the mission registry.

## Effect boundary

This resident worker does not send mail, merge pull requests, deploy services, mutate Google/Microsoft systems, alter branch protections, promote traffic or execute high-consequence decisions. Its application handlers are read-only/no-effect.

The hosting workflow necessarily writes its own GitHub Actions proof/state artifacts so that unattended cycles can resume. Those operational artifacts are infrastructure continuity records, not application/provider-effect authority.

## Proof classes

A source merge proves only that the runtime exists on admitted source. A successful scheduled/event-triggered workflow with its provider-native run record and emitted receipt can prove an unattended host cycle. Cross-run restoration additionally requires a later run whose receipt records `previous_state_restored=true`.

The following remain separate and **must not be inferred** from v1:

- continuously resident daemon;
- zero-compute external-event wait;
- provider-effect autonomy;
- production business-action execution;
- full AutoPilot runtime;
- stable promotion authority.

## Promotion ladder

1. `SOURCE_CANDIDATE`
2. `SOURCE_ADMITTED_CURRENT_MAIN`
3. `UNATTENDED_HOST_CYCLE_PROVIDER_VERIFIED`
4. `CROSS_RUN_STATE_RESUME_PROVIDER_VERIFIED`
5. `DURABLE_EVENT_WAIT_RESUME_PROVIDER_VERIFIED`
6. `BOUNDED_REVERSIBLE_EXTERNAL_AUTONOMY_VERIFIED`
7. `DURABLE_UNATTENDED_MULTI_MISSION_RUNTIME_PROVIDER_VERIFIED`

Each state requires its own evidence and cannot be promoted by narrative or synthetic tests alone.

## Next frontier

After v1 is operationally witnessed, the next tranche is a true durable mission substrate with event queues, durable sleeps/waits, worker crash recovery, mission leases, read-before-retry effect journals, owner-decision inboxes, resource budgets, multi-project arbitration and observed owner-burden/value cohorts.
