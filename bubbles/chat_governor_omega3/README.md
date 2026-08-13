# Bubbles Adaptive Chat Governor Ω3

Ω3 is the executable middleware evolution of the Bubbles chat-performance governor.

## Core contract

**Load capability, not history. Retrieve evidence, not entire archives. Activate specialists, not organisations.**

## Implemented in this package

- SQLite WAL durable mission, evidence, receipt, checkpoint, metrics and circuit-breaker state
- mission classification and minimum-specialist/minimum-connector compilation
- Legal Team Integration default: `Lex + LabourProcedure + Ledger`, `Gmail + Google Drive`
- evidence pointer reuse with source-version/modified-state staleness checks
- enforced connector relevance gating for calls routed through `ConnectorGateway`
- persistent idempotency receipts
- semantic-readback hooks
- retry with bounded exponential backoff
- per-connector circuit breakers
- EWMA latency/failure metrics and adaptive retrieval/result budgets
- HOT-0 / HOT-1 / WARM / COLD memory classification
- dependency-aware bounded-concurrency DAG executor
- proof-bearing crash-safe checkpoints
- failed-lane isolation: an unavailable policy does not freeze independent email/chronology work
- deterministic tests for the above controls

## Truth boundary

Ω3 is **not** claimed to modify hidden ChatGPT context management, OpenAI serving infrastructure, mobile-client performance or connector calls that bypass this middleware. Its verified maturity is limited to the code and execution paths that actually route through Ω3.

## Legal Team Integration target

```text
User request
   |
MissionCompiler
   |
Lex + LabourProcedure + Ledger
   |
Gmail + Google Drive only
   |
ConnectorGateway
   |-- cache / idempotency
   |-- retry / circuit breaker
   |-- semantic readback
   |
DAGExecutor
   |-- Joel email lane
   |-- Pule email lane
   |-- controlling-policy lane
   |-- chronology lane
   `-- legal-synthesis lane

A failed policy lane blocks only dependent synthesis; independent lanes continue.
```

## Verification

Run from repository root with Python's standard library only:

```bash
python -m unittest bubbles.chat_governor_omega3.test_omega3 -v
```

Promotion beyond deterministic/local verification requires independent execution/readback on the intended provider/runtime surface.
