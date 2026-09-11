# FUSE Serving Kernel v1

Status: `SOURCE_IMPLEMENTED / EXACT_HEAD_CI_AND_PROVIDER_PROMOTION_PENDING`

## Purpose

FUSE Serving Kernel v1 is a composition facade over already-admitted Federation primitives. It does **not** create another sovereign runtime or duplicate existing organs.

It binds one execution path around:

1. canonical `federation.mission_ir.MissionIR`;
2. mandatory canonical-context preflight;
3. Bubbles Ω3 durable SQLite state and failed-lane-isolating DAG executor;
4. lane-local proof envelopes with deterministic post-DAG aggregation;
5. mandatory effect-policy authorization through a hash-bound policy receipt;
6. concrete SOL 6.2 transactional effect execution through `federation.sol62_effect_adapter_v1`;
7. executable UAS runtime evaluation;
8. proof-bearing terminal checkpoints and idempotent receipts.

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
      +--> READ/INTERNAL lane --> lane-local evidence envelope
      |
      `--> EFFECT lane
              |
              v
        POLICY GATE / OPA ALLOW
              |
              v
         SOL 6.2 PRE-REGISTERED TRANSITION
              |
              v
      GATEWAY + WORKLOAD IDENTITY
              |
              v
      DURABLE EFFECT/INTENT PREPARATION
              |
              v
      EXECUTION FENCE + DISPATCH AUTHORITY
              |
              v
          PROVIDER CALL
              |
              v
      PROVIDER/TARGET READBACK
              |
              v
      SOL VERIFIED TRANSITION COMMIT
              |
              v
        lane-local evidence envelope
              |
              v
DETERMINISTIC EVIDENCE AGGREGATION
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
- `federation/fkpf_omega_v3/policy/federation.rego`
- `sol_61_runtime.sol_62_runtime.Sol62Runtime`
- `sol_61_runtime.fdof_v1.FederationDistributedOperatingFabric` as the broader provider-neutral fabric contract
- existing OpenTelemetry/A2A contracts as the intended telemetry and interoperability planes

## New invariant: retrieve before reasoning

A mission with a `ContextContract` cannot enter execution until every required canonical source is present, verified and, where an expected version is declared, current.

This directly closes the failure class where a system answers from generic knowledge even though the user's canonical prior work materially controls the request.

`HOLD_CONTEXT` is not a completion state and cannot generate a proof-bearing checkpoint.

## New invariant: proof cannot self-satisfy

A lane's `required_proof_axes` are requirements only. They are **not** added to mission proof merely because the lane declares them.

A no-effect/read-only handler must return the axes it actually established. An effectful lane must return them through a verified `EffectReceipt`. Missing lane proof fails the lane closed.

`EffectReceipt` and `PolicyDecisionReceipt` digests are load-bearing; a caller cannot forge the `VERIFIED` or `ALLOW` label while changing the receipt body.

## New invariant: parallel workers do not share mutable proof state

Each parallel lane returns a local FUSE evidence envelope containing its proof axes, proof references and logical tool trajectory. The coordinator aggregates those envelopes only after the DAG has finished.

This means out-of-order worker completion cannot change the final proof projection or logical trajectory. The regression court deliberately finishes independent lanes in a different physical order and requires the final evidence projection to remain identical across repeated runs.

## Policy enforcement

Every `BOUNDED_EFFECT` and `CONSEQUENTIAL_EFFECT` lane requires an `EffectPolicyGate` and a valid `PolicyDecisionReceipt(decision="ALLOW")` **before** the transactional effect executor may run.

`federation.opa_policy_adapter_v1.OPAHTTPPolicyGateV1` is the concrete v1 transport adapter for the existing FKPF Rego package `federation.fkpf_omega_v3`.

The adapter:

- does not reimplement the Rego allow rules;
- POSTs the deployment-supplied input to `/v1/data/federation/fkpf_omega_v3/allow`;
- binds the policy input and raw decision result into a FUSE receipt;
- fails closed on policy `false`, missing result, malformed JSON, timeout or transport failure;
- rejects secret-shaped policy input locally before transport;
- never infers owner approval from `mission.owner_approval_required`.

The helper `mission_effect_input(...)` maps FUSE effect classes into the effect/authority vocabulary already used by `federation.rego`. Identity ceilings and owner-approval evidence remain deployment inputs.

The current `policy_ref` is a configured reference carried into the decision receipt. This source implementation does **not** prove that a serving OPA sidecar has loaded a particular signed bundle revision; provider/runtime bundle readback remains a separate promotion gate.

## SOL 6.2 effect adapter

`federation.sol62_effect_adapter_v1.Sol62EffectExecutorV1` is the concrete v1 implementation of the kernel's `TransactionalEffectExecutor` boundary.

It deliberately does not register missions or transitions and does not create authority leases. The caller/domain owner must pre-register the exact SOL 6.2 mission and transition contract.

For an effectful lane the adapter requires:

1. matching FUSE MissionIR / SOL mission identity;
2. matching operation and pinned source version;
3. transition readiness;
4. gateway admission;
5. short-lived workload identity validation;
6. durable idempotency/effect/intent preparation;
7. an execution fence;
8. SOL dispatch authorization;
9. an actual provider observation with provider reference;
10. exact expected readback;
11. SOL proof verification and transactional state commit.

If provider readback does not match, SOL keeps the mission from advancing and preserves the effect as `FAILED_UNCERTAIN`. If the provider handler fails after dispatch authorization, the adapter attempts to move an uncertain in-flight effect to the same recovery state rather than retrying blindly.

Consequential transitions still require the action-bound SOL authority lease; FUSE cannot mint it.

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

## Regression courts

The repository test discovery tree contains:

- `tests/test_fuse_serving_kernel_v1.py`
  - missing canonical context;
  - stale canonical context;
  - unearned proof rejection;
  - optional-lane failure isolation;
  - mandatory effect policy gate;
  - policy denial before provider execution;
  - mandatory effect executor;
  - policy + verified effect readback;
  - real SOL 6.2 adapter verified transition;
  - SOL readback mismatch / `FAILED_UNCERTAIN` preservation;
  - required cost/latency telemetry;
  - Wilson confidence-bound promotion.
- `tests/test_fuse_serving_kernel_concurrency_v1.py`
  - out-of-order parallel completion with deterministic proof aggregation.
- `tests/test_fuse_opa_policy_adapter_v1.py`
  - FKPF-compatible mission-effect input;
  - OPA allow;
  - policy deny;
  - transport failure;
  - pre-transport secret-shape denial.
- `tests/test_fuse_receipt_integrity_v1.py`
  - effect-receipt digest integrity;
  - policy-receipt digest integrity.

The new `federation/*.py` production paths are intentionally not yet declared as a new ProofOS subsystem. Existing ProofOS default-deny behavior therefore selects the full-federation `test_*.py` fallback for this first admission instead of allowing a new subsystem to self-select a narrower proof court.

## Terminality

A mission reaches `COMPLETE` only when:

1. canonical context preflight passes;
2. every required DAG lane completes;
3. every effectful lane has a valid policy `ALLOW` receipt;
4. effectful lanes have SOL-backed verified target-state receipts;
5. MissionIR proof requirements are observed;
6. declared resource telemetry is present and within bounds;
7. UAS returns `PASS`.

Otherwise the bounded states are `HOLD_CONTEXT` or `HOLD_UAS`.

## Current truth boundary

This branch establishes source implementation and exact-head regression intent. Until the current branch head passes the repository admission controls, the code remains unadmitted source.

Even after deterministic repository admission, this work does **not** establish:

- production cutover;
- provider-hosted continuous serving runtime;
- multi-region consensus;
- universal exactly-once provider semantics;
- live OPA bundle distribution, signed-bundle verification or sidecar runtime readback;
- live OpenTelemetry export/evaluation backend;
- live A2A endpoints;
- market superiority;
- sustained owner-value improvement.

Those are separate promotion gates requiring provider-native readback and sustained empirical evidence on the intended serving surface.
