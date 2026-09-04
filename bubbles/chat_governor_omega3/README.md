# Bubbles Adaptive Chat Governor Ω3.4

Ω3.4 is the executable middleware evolution of the Bubbles chat-performance governor, adding a deterministic PRE_FINAL_RESPONSE integrity gate to the existing continuity, completion-witness and cognitive-precision controls.

## Core contract

**Load capability, not history. Retrieve evidence, not entire archives. Activate specialists, not organisations. Think adversarially before converging. Mission completion outranks turn completion.**

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
- PRE_FINAL_RESPONSE Stop gate: a known safe, authorised, available material gap blocks finalization and requires continued work
- composable terminal states: `VERIFIED_COMPLETE`, precise `OWNER_DECISION_REQUIRED`, proven `BLOCKED_IRREDUCIBLY`, `LEGAL_OR_SAFETY_PROHIBITION`, or checkpointed `ACTIVE_TURN_BOUNDARY`
- claim-integrity adapter that consumes existing RealityGuard/claim-proof verdicts instead of duplicating a truth engine
- material maturity language gate for words such as `implemented`, `operational`, `deployed`, `resolved`, `verified`, `fully`, and `universal`
- mandatory-control coverage checks that detect rules declared mandatory but missing at required enforcement points or lacking regression proof
- durable pre-final decision receipts and EWMA metrics for blocked finalizations, actionable gaps, rewrite demand and genuine owner decisions
- deterministic regressions for the above controls

## PRE_FINAL_RESPONSE integrity target

```text
Candidate final response
   |
MissionClosureState
   |-- objective satisfied?
   |-- material unfinished gaps?
   |-- safe + authorised + available route remains?
   |-- genuine owner-only decision?
   |-- objective-level exhaustion proven?
   `-- resumable host boundary proven?
   |
ClaimScanSnapshot(s)
   |-- RealityGuard / admitted claim-proof verdict
   |-- claimed lifecycle vs proven lifecycle
   `-- bounded safe statement
   |
ControlBinding coverage
   |-- required enforcement points
   |-- actual bound points
   `-- regression proof
   |
PreFinalGate
   |-- BLOCK_FINAL_CONTINUE_WORK
   |-- ALLOW_VERIFIED_COMPLETE
   |-- ALLOW_PRECISE_OWNER_DECISION
   |-- ALLOW_PROVEN_IRREDUCIBLE_BLOCKER
   `-- ALLOW_RESUMABLE_ACTIVE_TURN_BOUNDARY
   |
Durable checkpoint + decision metrics
```

This is the ChatGov analogue of a deterministic agent Stop/termination hook. It prevents a routed host from treating “I know what remains” as a valid completion state when the system can still safely act.

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

Ω3.4 is **not** claimed to modify hidden ChatGPT context management, model weights, OpenAI serving infrastructure, mobile-client performance or connector calls that bypass this middleware. `PRE_FINAL_RESPONSE` is enforceable only in hosts/executors that actually call the interlock. A source-level Stop gate is not proof that native ChatGPT, Gemini, Copilot or any other unbound provider is mechanically controlled by it. Cognitive scores and claim snapshots remain bounded decision/proof inputs, not authority grants or provider-effect proof.

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
python -m unittest bubbles.chat_governor_omega3.test_pre_final -v
```

Promotion beyond deterministic/source verification requires repository admission gates and independent execution/readback on the intended host/provider runtime surface.
