# Bubbles Ω Agent Fabric v1

## Purpose

Bubbles Ω Agent Fabric converts a user directive into a dependency-aware mission graph, allocates the minimum useful specialist agents, attaches deterministic workflow bots, keeps unrelated safe lanes moving when one lane fails, and refuses to mark the directive complete until every required task has terminal success proof.

This is an in-place extension of Bubbles Ω2, not a new sovereign control plane.

## Agent layer

The default agent fleet is deliberately small and role-aligned:

- **Bubbles Ω Controller** — mission decomposition, orchestration, synthesis and completion control.
- **Forge** — software, testing, runtime and implementation.
- **Scout** — research, discovery, source analysis and hypothesis formation.
- **Bridge** — integration, connectors, provider-read routes, automation and routing.
- **Ledger** — evidence, provenance, proof, readback and claim discipline.
- **Patch** — recovery, materially different retries, rollback and anti-stall.
- **Sentinel** — security, privacy, preflight, integrity and risk.
- **Pulse** — CFBE-style benchmark, metrics, evaluation and optimisation.
- **Prism** — presentation, explainability and output quality.
- **Beacon** — handoff, coordination, checkpoints and next action.

The default fleet has **no provider-write authority**. Write-capable executor workers must be separately bound with explicit effect scope and provider proof.

## Bot layer

Bots are deterministic workflow controls rather than independent reasoning authorities:

- Queue Bot — dependency ordering.
- Dedup Bot — idempotency/replay suppression.
- Checkpoint Bot — checkpoint/resume boundaries.
- Proof Bot — terminal receipt/proof capture.
- Retry Bot — failed-route quarantine and changed-route retry control.
- Handoff Bot — dependency release/handoff packets.
- Completion Bot — directive-fruit and final completion gate.

## Mission lifecycle

`DIRECTIVE -> TASK DAG -> WAVES -> AGENT ALLOCATION -> BOT CONTROLS -> EXECUTION -> GUARD -> SEMANTIC VERIFICATION -> RECEIPTS -> COMPLETION GATE`

Key invariants:

1. Cyclic or incomplete dependency graphs fail closed.
2. Safe independent tasks can continue when another lane fails.
3. Replaying a successful idempotency key returns the prior receipt instead of duplicating work.
4. A failed route is quarantined until a materially different route is supplied.
5. Provider effects require an exact single-use permit and an injected provider executor.
6. RealityGuard-style preflight may hold dispatch.
7. JARVIS-style independent semantic verification may downgrade apparent success to CONSTRAINT.
8. `directive_complete=true` requires SUCCESS for every required task.
9. Source, tests, local execution, provider execution, provider readback and realized value remain separate proof states.

## Omega-One and CFBE integration

The runtime adopts Omega-One principles without inheriting Omega-One's unresolved source identity:

- DAG/work allocation;
- bounded safe parallelism;
- failure-domain isolation;
- load-aware agent selection using observed reliability telemetry;
- changed-route recovery;
- champion/challenger-compatible benchmark snapshots.

CFBE consumes observed telemetry and receipts; it does not promote source-only results to provider/runtime maturity.

## Deployment boundary

Source deployment in Federation-Omega makes the fabric executable by Python callers and available through `bubbles` package exports. It does **not** create native ChatGPT background workers, provider credentials, a 24x7 service, or external provider write authority. Those are separate deployment stages requiring exact runtime/provider receipts.
