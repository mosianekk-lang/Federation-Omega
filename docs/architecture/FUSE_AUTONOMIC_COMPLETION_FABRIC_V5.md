# FUSE Autonomic Completion Fabric v5.0.2


## Core change


v5 moves recurrence out of prose and into an explicit state machine.  v3/v4-style prompts can describe continuation, but only a runtime can persist a checkpoint and re-enter execution.  v5 therefore has three modes: current-run continuation, persistent-runner reentry, and resume-capsule fallback.


## Components


- `autonomic_completion_v5.py`: non-terminal progress semantics, DAG-ready waves, current-run loop, persistent-runner queue, resume capsule, commercial terminality.
- `run_store_v1.py`: SQLite WAL checkpoint/CAS store and re-entry queue.
- `prompt_scientist_v2.py`: automatic telemetry-backed prompt-gene diagnosis, matched evaluation and promotion.
- `federation_learning_v1.py`: privacy-minimised hash-linked learning ledger plus compatibility-gated propagation.
- `federation_n_directive_v4.yaml`: compact user continuation contract.


## Federation composition


This does not replace CFBE vNext, Formation, SOL 6.2, ProofOS or provider executors.  It is an orchestration/learning layer above them.  External effects remain separately authorized and provider-native readback remains mandatory.


## 10x semantics


The first v5 benchmark is deliberately narrow: synthetic missions with repeated internal waves compare a handoff-style policy that requires another user turn per wave against a runtime-owned internal loop.  A 20-wave mission can reduce assistant/user handoff turns from 20 to 1 (20x), but this is not a claim of 20x model intelligence, end-to-end wall-clock speed or production throughput.




## v5.0.1 maturity integrity


Packet completion and commercial maturity are now separate state domains. Completing the current DAG never promotes `COMMERCIAL_READY_VERIFIED` unless the commercial maturity court passes every applicable evidence gate. Missing/failed gates emit `recompile_required`; an available mission recompiler may materialize the missing gates and continue within the same run.


## v5.0.2 No-False-Finality integrity

A second state domain now protects owner-facing finality:

- packet completion is execution progress, not mission acceptance;
- non-commercial success requires an explicit terminal acceptance court;
- a terminal report requires a non-empty terminal proof reference;
- progress outputs are classified as `ACTIVE_BUILD` and cannot use completion-style presentation;
- commercial success emits a deterministic maturity-court proof reference before terminal-style output is legal;
- owner-decision and resume states remain active mission boundaries rather than completion success.

The guard is implemented in `federation/finality_guard_v1.py` and is invoked inside
`AutonomicCompletionKernel.run_cycle`. This moves the rule out of prose and into the
runtime path that produces the mission state.

A successful tranche therefore does not end the parent mission. It either releases the
next ready wave, triggers mission recompilation for unresolved terminal predicates, queues
persistent re-entry, or emits an exact resume/owner boundary. Only a verified terminal
court may stop the mission as success.

**Invariant:** `GREEN != DONE`, `CHECKPOINT != TERMINAL`, and
`PACKETS_DONE != MISSION_ACCEPTED`.

## Durable terminal debt / zero-debt finality

The existing AAREK, MBMPC-PILF closure bridge, Master Bible Portfolio Compiler and commercial maturity courts may discover declarative terminal/stage/gap debt. FUSE Autonomic Completion must preserve applicable mandatory debt through `TerminalDebtLedger` rather than relying on a single chat/client to remember it.

For governed missions with a terminal-debt profile:

1. reconcile mandatory terminal predicates into durable RunStore debt;
2. preserve a maturity vector per predicate;
3. compute dependency-ready debt;
4. compile a collision-safe `AutonomousDebtBurner` wave;
5. use existing authority/routing/executor organs to close the debt;
6. require semantic/proof evidence before maturity is marked passed;
7. recompile after every material outcome;
8. continue automatically while safe machine-ready debt exists.

Hard floor:

`OPEN_MANDATORY_TERMINAL_DEBT == 0`

before `COMPLETE_VERIFIED`, `PRODUCTION_VERIFIED` or `COMMERCIAL_READY_VERIFIED` may be presented for a profile that requires terminal debt.

Packet completion, source admission, CI success, installer creation, artifact upload, provider ACK or one successful runtime cannot silently clear unrelated maturity debt.

A blocked debt is scoped to its causal intersection. Disjoint READY debt must continue.

A debt that lacks an executor/handler becomes an explicit capability gap and is routed through reuse -> rebind -> repair -> extend -> compose -> lawful harvest -> minimum residual build. It is not discarded.

For the Local Sovereign AI product mission, load `governance/fuse_local_sovereign_ai_finality_v2.json`.

