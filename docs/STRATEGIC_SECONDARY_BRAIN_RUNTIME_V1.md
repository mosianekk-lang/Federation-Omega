# Strategic FUSE Secondary Brain — Durable Provider Runtime Contract v1

## Purpose
This contract separates **source admission** from **provider runtime maturity**. The Strategic Secondary Brain is not RUNNING merely because its compiler, tests, scheduler metadata or a generic cloud health endpoint exists.

The runtime kernel is provider-neutral and effect-free. A private provider adapter may bind it only after independently proving the capabilities below.

## Required provider binding
A qualifying runtime must prove all of the following on the exact bound source epoch:

1. **Private provider identity** — exact runtime/project/service identity with no anonymous privileged surface.
2. **Durable checkpoint store** — checkpoint survives worker restart and records source epoch, cursor, dedupe window, packet fingerprint, next due time and failure fingerprint.
3. **Event/poll signal source** — new material input is discoverable without an open ChatGPT conversation.
4. **Scheduled reconciliation** — a provider-native timer wakes the runtime even when no event arrives.
5. **Heartbeat and health** — liveness receipt is distinct from semantic work proof.
6. **Idempotent dedupe** — replay of the same provider event cannot execute the strategic action twice.
7. **Missed-run recovery** — an overdue checkpoint is detected and resumed.
8. **Crash-resume safety** — failed work cannot advance the durable cursor; the next run resumes from the unchanged checkpoint.
9. **FSED six-ledger access** — exact private read/write/readback for signal, hypothesis, opportunity, calibration, action and proof ledgers.
10. **Semantic execution receipt** — each material run records exact input event IDs, StrategicPacket fingerprint, disposition, authority, source main and checkpoint fingerprint.
11. **Post-write provider readback** — persisted strategic state is independently read back before promotion.
12. **Forecast calibration receipt** — resolved forecasts update calibration without overwriting historical probability claims.
13. **Authority ceiling** — A0/A1 safe internal work may auto-queue; A2 remains HOLD_AUTHORITY absent exact current authority.

## Recovery semantics
`StrategicRuntimeKernel` provides deterministic state transitions for:
- event fingerprinting and bounded dedupe memory;
- source-epoch reconciliation;
- missed-run detection;
- failure checkpoint preservation;
- restart/resume without cursor advance;
- liveness sequence increments that do not manufacture semantic proof;
- A2 hold propagation from the Strategic compiler.

A provider adapter owns transport and persistence. The kernel never handles credentials, sends communications, creates cloud resources, changes IAM, or publishes private strategy.

## Current route constraints
At source-admission time, existing Federation provider infrastructure includes Google Apps Script queue processing and an `architron9` Cloud Run carrier. Those infrastructure facts do **not** establish this runtime binding. Promotion requires an action-specific Strategic FUSE canary and exact FSED readback.

Known invalid shortcuts remain invalid:
- scheduler metadata ≠ execution;
- heartbeat ≠ semantic cognition;
- generic HTTP 200 ≠ action-specific readback;
- source/tests ≠ provider deployment;
- a stale queued command ≠ live queue-drain proof.

## Promotion ladder
`SOURCE_ADMITTED` → `ADAPTER_BOUND` → `PROVIDER_CANARY_VERIFIED` → `DURABLE_RECOVERY_VERIFIED` → `FSED_SEMANTIC_READBACK_VERIFIED` → `SOAK_VERIFIED` → `COMPLETE_VERIFIED`.

No layer inherits maturity from the layer before it.
