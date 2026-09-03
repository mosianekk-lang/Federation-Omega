# Sentinel Ω — Autonomic Immune System v2

## Mission

Protect the owner's creative time by moving routine Federation troubleshooting out of interactive work and into an autonomic reliability fabric.

The target behavior is not merely `monitor -> report`. It is:

`PREDICT -> DETECT -> PRESERVE -> FINGERPRINT -> CORRELATE -> BLAST-RADIUS -> RECALL -> FALSIFY -> SELECT SMALLEST SAFE REPAIR -> CANARY -> EXECUTE -> SEMANTIC READBACK -> REGRESSION -> ROLLBACK IF NEEDED -> SOAK -> LEARN -> PREVENT RECURRENCE`.

## 10× design changes

1. **Event identity and deduplication** — stable event keys prevent duplicate incident creation.
2. **Failure fingerprints** — error signature + dependency/provider/source epoch prevents stale troubleshooting loops.
3. **Repair memory** — an unchanged failed route cannot be blindly retried.
4. **Dependency-aware blast radius** — failures are reasoned over downstream Federation dependencies, not isolated components.
5. **Smallest-safe-repair selection** — A0/A1 is preferred before A2; A3 remains owner-reserved.
6. **Safe rerouting** — alternate verified route families are selected before escalating to the owner.
7. **Circuit breakers** — repeated failures open a circuit and stop noisy or harmful retry storms.
8. **Self-test** — Sentinel health is itself measured; a broken watchdog fails closed instead of silently certifying itself.
9. **Creative-Time SLO** — the system measures owner interruptions, protection rate and MTTR rather than calling activity success.
10. **Independent proof contract** — canary, semantic readback and rollback requirements are explicit outputs of the repair decision.

## Layered reliability topology

### Layer 0 — Event producers

GitHub workflow results, queue state, heartbeat records, projection drift, provider readbacks and existing Bubbles/Sentinel observations remain the sources of truth. Event producers do not self-certify repairs.

### Layer 1 — Fast native Sentinel

Reuse the existing provider-side Apps Script/native scheduler route when it is freshly proven. Desired operating intent is sub-five-minute detection and approximately one-minute processing only where the exact provider trigger, project identity, source, idempotency and semantic readback are currently verified.

If that proof is absent, classify `FAST_SENTINEL_DEGRADED`; do not pretend configuration equals continuous liveness.

### Layer 2 — Sentinel Ω autonomic controller

The provider-neutral kernel performs fingerprinting, memory lookup, blast-radius analysis, runbook matching, authority control, rerouting and circuit-breaking.

### Layer 3 — Repair executors

Reuse existing Bubbles, Failure-Win/AutoFIX, Formation Ω, Phoenix, CI/source tooling, queue processors and provider-native routes. Sentinel is not a second executor fleet.

### Layer 4 — Independent assurance

ProofOS/JARVIS/provider-native semantic readback must confirm material repairs. `SOURCE`, `TESTED`, `CI_ADMITTED`, `DEPLOYED`, `PROVIDER_RUNNING`, `WORKFLOW_VERIFIED`, `OPERATIONAL_VERIFIED` and `OWNER_VALUE_PROVEN` stay separate.

### Layer 5 — Hourly supervisory backstop

The ChatGPT `Federation Sentinel Ω` condition-watch remains an independent hourly backstop while fast native persistence is not fully qualified. It should stay silent on healthy/no-change cycles.

## Creative-Time SLO

Targets are goals, not completion claims:

- routine owner interruptions: **0**
- routine incident protection rate: **>= 99%**
- fast native detection target: **<= 60 seconds** where native event/trigger routes support it
- routine repair MTTR target: **<= 300 seconds** where a safe runbook is executable
- every mutating repair: canary + rollback + semantic readback
- owner escalation: only after safe authorized routes are exhausted or A3 authority is truly required

No target may be reported achieved without measured operational samples.

## Authority model

- **A0_OBSERVE** — observation, diagnosis, evidence preservation.
- **A1_INTERNAL** — reversible internal/source/CI/state reconciliation and safe retries.
- **A2_REVERSIBLE_PROVIDER** — reversible provider operation only with exact pre-existing authority, exact target, no new spend/IAM/credential change, canary, semantic readback and proven rollback.
- **A3_OWNER_RESERVED** — destructive effects, credentials/secrets, IAM expansion, paid resource/billing changes, legal/financial commitments, external send/publish/file, identity-sensitive or irreversible actions.

A lower-authority route always wins when it can satisfy the mission with equal or stronger proof.

## Anti-stall rule

A blocked provider edge does not freeze the Federation. Sentinel must preserve the blocker fingerprint, continue unaffected lanes, use an alternate safe route when one exists, and retry only after a meaningful state/provider/source/dependency epoch change.

## Proof boundary

The v2 kernel is deterministic source logic until independently admitted and exercised by real provider/event paths. Passing unit tests proves control semantics only; it does not prove native trigger liveness, real outage prevention, provider repair authority or owner-time value.
