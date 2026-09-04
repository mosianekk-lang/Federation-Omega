# CFBE-Ω Ultimate Execution Spine v1

Status: **source candidate / no provider effect**.

## Purpose

Compose existing Federation controls into one bounded mission runner rather than add another sovereign scheduler, memory root, proof plane or provider router.

## Execution model

`DIRECTIVE -> MISSION -> DEPENDENCY WAVES -> PARALLEL SAFE LANES -> FAN-IN -> FAILURE LEARNING/RECOVERY -> CHECKPOINT -> VERIFIED LOCAL RESULT`

The runner uses the existing `BubblesControlPlane` before every task. Any non-read task therefore inherits the existing route proof requirements plus the one-use external execution lease requirement. The execution spine does not mint or widen authority.

## Persistent failure learning

Failures are preserved through the existing EvidenceOps/Formation AAA path. The task route fingerprint and precondition fingerprint are fed into `evaluate_failure_with_aaa`, so unchanged failed routes can be suppressed on later cycles. The updated recovery checkpoint remains in the mission capsule.

When a `LivingStateIngress` instance is supplied, every failure also becomes a `LEARNING` event with `LearningClass=FAILURE`. That provides durable cross-cycle learning without creating another database or memory root. If Living State persistence itself fails, the primary task failure remains visible and the capsule records `LEARNING_PERSISTENCE_DEGRADED` rather than losing the mission result.

## Smart workarounds

The workaround table is conservative and authority-neutral:

- stale source -> **REANCHOR_AND_REPLAN**;
- transient provider -> **BOUNDED_RETRY** only when AAA permits it;
- rate limit/tool unavailable -> **ALTERNATE_READ_ROUTE**;
- semantic mismatch -> **QUARANTINE_AND_VERIFY**;
- conflict -> **SERIALIZE_AND_REFRESH**;
- authority failure -> **HOLD_EFFECT_CONTINUE_SAFE_LANES**;
- invalid/unknown input -> **DIAGNOSTIC_FALLBACK**.

Automatic alternate executors are allowed only for read tasks. A workaround can never convert a blocked effect lane into an unapproved write.

## Pending-work preservation

A completed task result is keyed to the deterministic task fingerprint. On resume, the same successful task becomes `RESUME_HIT` and its executor is not called again. A failed sibling therefore does not force completed independent work to rerun.

## Performance behavior

Independent dependency-ready tasks are executed with `asyncio.gather`. Dependent work waits only for its actual predecessors. Optional work below the mission information-gain floor is skipped unless a required downstream task depends on it.

Trace records use OpenTelemetry-compatible semantic names where useful (`gen_ai.operation.name`, `tool.name`) and preserve route, effect class, duration, source anchor, failure class and workaround.

## Promotion boundary

This source candidate must pass the normal Federation Omega Airlock/ProofOS, Bubbles Command Bus and Public Repository Leak Guard on its exact head. Green CI is not provider-runtime or owner-value proof. Stable promotion also requires the existing prospective matched-mission value gate.
