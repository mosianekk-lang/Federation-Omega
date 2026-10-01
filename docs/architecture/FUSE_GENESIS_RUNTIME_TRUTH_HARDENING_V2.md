# FUSE Genesis Runtime Truth Hardening v2

## Purpose

F325 hardens the F324 runtime-continuity contract against three false-green classes without creating a scheduler, controller, authority root, or second effect system.

### 1. Signed Google Apps Script dispatch

A dispatch remains bound to `scheduler_id=GOOGLE_APPS_SCRIPT`, but provider/event readback is no longer sufficient by itself.

The envelope now carries:

- `signature_key_id`
- `signature_algorithm=RSA_SHA256`
- `signature_b64`

Genesis verifies the canonical dispatch bytes with a configured public key. The corresponding private key stays outside Genesis. The intended Apps Script implementation may keep the private key in provider-side secret storage such as Script Properties; it must never be written to Sheets, GitHub, logs, or receipts.

Admission therefore requires BOTH:

1. cryptographic signature verification; and
2. exact provider-native authority/event readback.

A truthy string/object is not accepted as either proof.

### 2. Strict effect readback semantics

F324 used Python truthiness on provider `applied` values. A value such as the string `"false"` is truthy in Python and could therefore create a false-positive effect result.

F325 requires the provider adapter to return the literal boolean `true` or `false`.

Any other value is rejected as `APPLIED_FLAG_MUST_BE_BOOLEAN`.

### 3. Effect-boundary fence guard

A heartbeat guard proves liveness but does not, on its own, prove that an external effect still owns a current execution fence.

F325 allows effect execution to require an explicit `execution_guard`.

When guard enforcement is enabled:

- stale/missing fence blocks the external effect before invocation;
- fence loss after the provider call forces effect readback;
- a positive readback closes the effect without replay;
- a negative readback returns the effect to retryable PREPARED state;
- ambiguous readback remains non-retryable.

This narrows the race where a long-running handler loses its host/source fence while an external effect is in flight.

## Scheduler boundary

Google Apps Script remains the only scheduling authority.

PX116/PX122 and Genesis are workers/watchdogs/executors only.

F325 does not install a GAS trigger or activate a physical resident host.

## Proof boundary

F325 is source/runtime-contract hardening only until provider-native runtime evidence exists.

It does not prove:

- current Apps Script source installation;
- a live singleton `gasSchedulerRunV3` trigger;
- possession of a valid GAS signing private key;
- GAS-to-Genesis dispatch in production;
- physical owner-host residency;
- cross-host recovery; or
- owner-value improvement.

Those remain separate runtime and behavioural predicates.
