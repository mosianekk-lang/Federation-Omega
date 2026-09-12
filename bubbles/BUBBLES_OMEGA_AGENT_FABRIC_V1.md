# Bubbles Ω Agent Fabric v1

## Purpose

Bubbles Ω Agent Fabric converts a user directive into a dependency-aware mission graph, allocates the minimum useful specialist agents, attaches deterministic workflow bots, keeps unrelated safe lanes moving when one lane fails, and refuses to mark the directive complete until every required task has terminal success proof.

This is an in-place extension of Bubbles Ω2, not a new sovereign control plane.

## Agent layer

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

- Queue Bot — dependency ordering.
- Dedup Bot — mission-scoped idempotency and replay suppression.
- Checkpoint Bot — checkpoint/resume boundaries.
- Proof Bot — terminal receipt/proof capture.
- Retry Bot — failed-route quarantine and changed-route retry control.
- Handoff Bot — dependency release/handoff packets.
- Completion Bot — directive-fruit and final completion gate.

## Mission lifecycle

`DIRECTIVE -> TASK DAG -> WAVES -> AGENT ALLOCATION -> BOT CONTROLS -> EXECUTION -> GUARD -> SEMANTIC VERIFICATION -> RECEIPTS -> COMPLETION GATE`

Key invariants:

1. Empty, cyclic or incomplete dependency graphs fail closed.
2. Safe independent tasks can continue when another lane fails.
3. Ready-work calculation subtracts already-running work and already-running effect lanes.
4. Per-agent `max_parallel` capacity is enforced; unresolved capability gaps are not released as ready work.
5. Replaying a successful idempotency key inside the same mission returns the prior receipt instead of duplicating work; separate missions do not share the same token namespace.
6. A failed route is quarantined until a materially different route is supplied.
7. Every non-internal provider task requires an exact **mission + task + target + effect + route-fingerprint** single-use permit.
8. A non-internal permit is consumed immediately before dispatch so a provider result cannot occur and then become replayable because local result handling failed.
9. Future reversible/consequential write routes require both a pre-dispatch guard and an independent post-result semantic verifier; callback errors fail closed.
10. Provider success is held unless a proof/readback reference is captured.
11. Raw executor payloads are **not written into durable receipts**. Successful task payloads remain process-local and explicitly addressable through `task_output()`; receipts store result-key metadata and proof references only.
12. `directive_complete=true` requires SUCCESS for every required task.
13. Source, tests, local execution, provider execution, provider readback and realized value remain separate proof states.

## Omega-One and CFBE integration

The runtime adopts Omega-One principles without inheriting Omega-One's unresolved source identity: DAG/work allocation, bounded safe parallelism, failure-domain isolation, load/capacity-aware agent selection, changed-route recovery and champion/challenger-compatible telemetry. CFBE may consume observed telemetry and receipts but cannot promote source-only results to provider/runtime maturity.

## RealityGuard and JARVIS integration

The runtime exposes explicit hooks for guard and verifier functions. The default internal/read-only fleet may use these proportionally. Any future provider-write-capable worker is fail-closed unless a guard and independent verifier are both supplied. This prevents a custom executor from acquiring write authority merely by being added to the worker registry.

## Persistence and privacy boundary

The in-package permit set, task state, retry memory, idempotency map and task outputs are process-local. Durable receipts intentionally exclude raw executor payloads. This is sufficient for deterministic source/CI/runtime qualification and internal/read-only orchestration. **Provider-write promotion additionally requires a durable external permit/idempotency/receipt store with restart replay and provider readback.** Do not infer durable exactly-once provider behavior from process-local memory.

## Deployment boundary

Source deployment in Federation-Omega makes the fabric executable by Python callers and available through `bubbles` package exports. It does **not** create native ChatGPT background workers, provider credentials, a 24x7 service, durable provider-write idempotency, or external provider write authority. Those are separate deployment stages requiring exact runtime/provider receipts.
