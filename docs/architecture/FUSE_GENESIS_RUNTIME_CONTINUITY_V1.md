# FUSE Genesis Runtime Continuity v1

## Purpose

F324 closes the next measured runtime bottlenecks after F322 convergence and F323 resident execution.

It does not create a scheduler or controller. Google Apps Script remains the only scheduling authority. Genesis remains an execution substrate.

## 1. Scheduler-authenticated dispatch ingress

A `DispatchEnvelope` binds each admitted task to:

- `scheduler_id=GOOGLE_APPS_SCRIPT`;
- mission identity;
- task and idempotency identities;
- the current Genesis source-epoch digest;
- canonical payload SHA-256;
- provider-native authority/readback reference;
- provider event identity;
- issue/expiry interval; and
- bounded effect class.

`DispatchIngress` fails closed when:

- a non-Apps-Script scheduler attempts dispatch;
- the source epoch changed;
- the payload hash changed;
- the dispatch expired or is not yet valid;
- the provider adapter cannot verify authority/readback; or
- an idempotency identity is reused with different semantics.

The ingress does not manufacture authentication. The adapter must verify the provider-native authority/event references before admission.

## 2. Crash-safe effect journal

`EffectJournal` persists one effect identity and idempotency key with explicit states:

`PREPARED -> EXECUTING -> APPLIED -> READBACK_VERIFIED`

and recovery states:

`EXECUTING/UNKNOWN -> READBACK -> PREPARED or READBACK_VERIFIED`

A process crash or transport exception never means "no effect". `UNKNOWN` and interrupted `EXECUTING` require effect readback before retry.

A positive readback closes the effect without replay. A verified negative readback returns it to PREPARED so the same semantic effect can be retried safely. Idempotency collisions fail closed.

## 3. Independent task heartbeat

The Resident Host now starts a separate `HostHeartbeatGuard` connection while a task handler is executing.

This prevents a long-running handler from making an otherwise healthy resident host look dead merely because the main worker loop is blocked.

If the heartbeat guard loses the host fence, task completion fails closed and the persisted RUNNING task remains available for recovery.

## 4. Watchdog semantics

The reference watchdog distinguishes:

- heartbeat stale;
- queue stalled; and
- unknown effect.

Process heartbeat alone is not work consumption or semantic success.

## Scheduling boundary

The estate scheduling contract is:

`GOOGLE APPS SCRIPT MASTER CLOCK -> authenticated dispatch -> GENESIS RESIDENT EXECUTOR -> effect journal/readback -> semantic receipt`

PX116/PX122 may supply worker or watchdog evidence. They are not scheduler authority. ChatGPT recurring Genesis schedules are disabled.

## Proof boundary

F324 is source/runtime-contract work only until provider-native deployment evidence exists.

It does not prove:

- a current Apps Script singleton trigger;
- Apps Script Projects API source installation;
- live Apps Script-to-owner-PC delivery;
- owner PC current connectivity;
- 24x7 physical-host uptime;
- production provider effects;
- provider-loss survival; or
- owner-value improvement.

Those remain separate runtime/behaviour/value predicates.
