# FUSE Serving Kernel v1

Status: `SOURCE_IMPLEMENTED / CI_AND_PROVIDER_PROMOTION_PENDING`

## Purpose

FUSE Serving Kernel v1 is a composition facade over already-admitted Federation primitives. It does **not** create another sovereign runtime or duplicate existing organs.

It binds one execution path around:

1. canonical `federation.mission_ir.MissionIR`;
2. mandatory canonical-context preflight;
3. Bubbles Ω3 durable SQLite state and failed-lane-isolating DAG executor;
4. an injected transactional effect boundary intended for SOL 6.2/FDOF;
5. executable UAS runtime evaluation;
6. proof-bearing terminal checkpoints and idempotent receipts.

## Control flow

```text
OWNER OBJECTIVE
      |
      v
CANONICAL MissionIR
      |
      v
CANONICAL CONTEXT PREFLIGHT
      |
      v
DURABLE PLAN + DAG
      |
  independent lanes
      |
      v
TRANSACTIONAL EFFECT ADAPTER (only when needed)
      |
      v
PROVIDER/TARGET READBACK
      |
      v
UAS RUNTIME EVALUATION
      |
      v
PROOF-BEARING TERMINAL CHECKPOINT
```

## Non-duplication rule

The kernel deliberately reuses, rather than replaces:

- `bubbles.chat_governor_omega3.state.DurableState`
- `bubbles.chat_governor_omega3.dag.DAGExecutor`
- `federation.mission_ir.MissionIR`
- `sol_61_runtime.sol_62_runtime.Sol62Runtime` through an effect adapter boundary
- `sol_61_runtime.fdof_v1.FederationDistributedOperatingFabric` for provider-neutral executor routing
- FKPF/OPA policy as the intended policy plane
- existing OpenTelemetry/A2A contracts as the intended telemetry and interoperability planes

## New invariant: retrieve before reasoning

A mission with a `ContextContract` cannot enter execution until every required canonical source is present, verified and, where an expected version is declared, current.

This directly closes the failure class where a system answers from generic knowledge even though the user's canonical prior work materially controls the request.

`HOLD_CONTEXT` is not a completion state and cannot generate a proof-bearing checkpoint.

## New invariant: proof cannot self-satisfy

A lane's `required_proof_axes` are requirements only. They are **not** added to mission proof merely because the lane declares them.

A no-effect/read-only handler must return the axes it actually established. An effectful lane must return them through a verified `EffectReceipt`. Missing lane proof fails the lane closed.

## Effect boundary

`BOUNDED_EFFECT` and `CONSEQUENTIAL_EFFECT` lanes require an injected `TransactionalEffectExecutor`.

The kernel does not infer authority from MissionIR and does not perform provider effects on its own. The intended production adapter is SOL 6.2/FDOF, which already owns fencing, idempotency, target-state verification and provider-readback semantics.

## UAS runtime court

`federation.uas_runtime_v1.UASRuntimeEvaluator` evaluates:

- outcome;
- required proof coverage;
- expected tool trajectory;
- security violations;
- regression failures;
- cost ceilings;
- latency targets;
- owner intervention burden.

Declared cost or latency targets require actual observations. Missing telemetry fails closed.

The same module provides a Wilson lower confidence-bound gate for promotion so a candidate cannot graduate from a small number of lucky runs.

## Terminality

A mission reaches `COMPLETE` only when:

1. canonical context preflight passes;
2. every required DAG lane completes;
3. effectful lanes have verified target-state receipts;
4. MissionIR proof requirements are observed;
5. UAS returns `PASS`.

Otherwise the bounded states are `HOLD_CONTEXT` or `HOLD_UAS`.

## Current truth boundary

This branch establishes source implementation and deterministic regression intent only.

It does **not** establish:

- production cutover;
- provider-hosted serving runtime;
- multi-region consensus;
- universal exactly-once provider semantics;
- current OPA bundle distribution/runtime enforcement;
- live OpenTelemetry export/evaluation backend;
- live A2A endpoints;
- market superiority;
- sustained owner-value improvement.

Those are separate promotion gates requiring exact-head CI and, where relevant, provider-native readback and sustained empirical evidence.
