# Formation Ω Mission Convergence Engine v1

## Purpose

Mission Convergence Engine (MCE) is an additive Formation Ω / SOVARA convergence layer. It keeps a material owner directive bound to one immutable closure contract while design, source, runtime, proof, resilience and learning progress through a dependency graph.

MCE does **not** create provider credentials, external-effect authority, owner approval, runtime deployment or proof by itself.

## Why it exists

The Federation already contains strong design, routing, proof, failure-learning and source-admission systems. The recurring gap is terminal convergence: a valid implementation can become stale while other source work merges; new design ideas can pre-empt an unfinished implementation; append-only provenance can preserve history while leaving current state expensive to infer.

MCE adds the missing closure layer without replacing existing systems.

## Reused estate components

- Federation Omega v2 `MissionContract` and intent-compiler semantics.
- Event-sourced current-state projection semantics.
- Formation Ω route portfolios, bounded parallelism, current-head proof and release gates.
- SOVARA execution routing/effect control.
- DPF full-capture-first provenance and Design Gene learning.
- JARVIS independent assurance.
- CFBE benchmarking and anti-regression.
- Sentinel freshness/stall observation.
- Failure-Win / Superior Logic failure-to-infrastructure controls.
- GitHub Airlock, Bubbles Command Bus and Public Repository Leak Guard.

## Core lifecycle

```text
DIRECTIVE
  -> MISSION CONTRACT
  -> DEPENDENCY DAG
  -> READY WORK WAVES
  -> SOURCE CONVERGENCE / RUNTIME EXECUTION
  -> PROOF VECTOR
  -> INDEPENDENT VERIFICATION
  -> CLOSURE RECEIPT
  -> DPF RECONCILIATION / DESIGN GENE
```

## Proof vector

MCE keeps these dimensions separate:

`design`, `source`, `installation`, `identity`, `authentication`,
`authorization`, `execution`, `semantic_proof`, `independent_proof`,
`resilience`, `rollback`, `closure`.

Statuses are `OPEN`, `PARTIAL`, `HELD`, `PROVEN`, or `NOT_APPLICABLE`.

A source merge cannot promote installation or runtime proof.

## Closure Lock

Once implementation begins, the mission target does not silently move:

- `P0`: correctness/security/proof defect — may interrupt closure.
- `P1`: material challenger — run/record in parallel.
- `P2`: optimization — Improvement Inbox.
- `P3`: future idea — backlog.

## Failure resolver

A repeated failure fingerprint maps to one durable resolver with exact gap, diagnosis, immediate workaround, permanent fix, alternate route, retry condition, proof test and closure test.

The same failure updates the resolver instead of restarting discovery.

## Source convergence

A `ChangeCapsule` is stable source intent independent of branch ancestry. It includes exact base/candidate blob identities and proof/rollback contracts.

Classification against fresh main:

- `CURRENT_BASE`
- `ALREADY_APPLIED`
- `DISJOINT_STALE_BY_ANCESTRY`
- `STRUCTURALLY_COMPATIBLE`
- `SEMANTIC_CONFLICT`

Automatic exact-blob re-anchoring is allowed only for the first three. Compatible overlap requires an explicitly reconciled candidate. Semantic conflict fails closed.

## Admission train

```text
fresh signed main
-> convergence classification
-> current-main candidate
-> focused tests
-> affected regressions
-> Airlock
-> Bubbles Command Bus
-> Leak Guard
-> fresh main recheck
-> expected-head merge
-> signed-main readback
```

If main moves after checks, the candidate returns to reclassification against only the new delta.

## Event ledger

The public-safe v1 engine contains an append-only hash-chained mission ledger with optional JSONL persistence. It projects current state from mission events and rejects obvious secret-bearing fields.

Provider-native durable stores are adapters; they do not change the MCE semantic contract.

## First canary

PR #628 — BEF native encrypted provenance courier.

The canary must prove that a stale-by-ancestry source change can be carried to fresh main without semantic dilution, admitted through exact-head controls, and read back on signed main.

Only after source closure does the mission move to live Edge Agent/native-host binding and current-chat full-observable-capture proof.

## Deployment states

`DESIGNED -> LOCALLY_TESTED -> SOURCE_CANDIDATE -> SOURCE_ADMITTED -> PRIVATE_RUNTIME_BOUND -> LIVE_CANARY -> RESILIENT -> FULLY_ESTABLISHED`

No stage inherits from a prior stage without its own evidence.

## Initial implementation

Source files:

- `formation_omega/mission_convergence.py`
- `formation_omega/source_convergence.py`
- `governance/formation_omega_mission_convergence_engine_v1.json`
- `tests/test_formation_omega_mission_convergence.py`
- `tests/test_formation_omega_source_convergence.py`

Initial focused local result: **16/16 PASS**.

This is local source validation only until hosted admission and signed-main readback complete.
