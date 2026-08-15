# Bubbles Adaptive Chat Governor Ω3.2

Ω3.2 is the executable middleware evolution of the Bubbles chat-performance governor, extended with bounded cognitive-precision controls.

## Core contract

**Load capability, not history. Retrieve evidence, not entire archives. Activate specialists, not organisations. Think adversarially before converging.**

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
- cognitive route ranking that makes contradiction, evidence quality, risk and owner burden load-bearing
- confidence bands that remain decision aids rather than factual/probability claims
- explicit unresolved-falsifier and high-severity-falsifier gates
- shared-dependency and universal single-point-of-failure detection across competing routes
- counterfactual scenario-stability scoring when scenarios are supplied
- convergence control that prevents premature route selection
- cognitive-load monitoring with `NORMAL`, `WATCH_AND_PRUNE`, and `CHECKPOINT_AND_COMPRESS` states
- direct reuse of the existing EvidenceOps `InformationGainRouteSelector` for highest-information reversible test selection
- deterministic tests for the above controls

## Cognitive Precision target

```text
Objective
   |
MissionCompiler
   |
Candidate routes / hypotheses
   |
CognitivePrecisionKernel
   |-- support vs contradiction
   |-- evidence quality
   |-- open falsifiers
   |-- counterfactual stability
   |-- hidden/shared dependencies
   |-- owner burden / latency / risk
   |-- confidence calibration
   |-- convergence gate
   `-- highest-information reversible test
   |
Authorised route or HOLD_FOR_HIGH_INFORMATION_TEST
   |
DAGExecutor / ConnectorGateway
   |
Exact readback / checkpoint / learning
```

The kernel does not force every task into deep analysis. It is intended for material ambiguity, high-risk decisions, competing explanations, architecture selection and other cases where a wrong early assumption would be expensive.

## Truth boundary

Ω3.2 is **not** claimed to modify hidden ChatGPT context management, model weights, OpenAI serving infrastructure, mobile-client performance or connector calls that bypass this middleware. Cognitive scores, confidence bands and counterfactual stability are decision aids only; they are not legal-success probabilities, verified facts, authority grants or provider-effect proof. Verified maturity remains limited to the code and execution paths that actually route through Ω3.2.

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

Run from repository root:

```bash
python -m unittest bubbles.chat_governor_omega3.test_omega3 -v
python -m unittest bubbles.chat_governor_omega3.test_cognitive_precision -v
```

Promotion beyond deterministic/local verification requires the repository admission gates and independent execution/readback on the intended provider/runtime surface.
