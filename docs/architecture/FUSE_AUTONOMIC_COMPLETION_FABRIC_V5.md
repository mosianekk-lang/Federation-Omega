# FUSE Autonomic Completion Fabric v5.0.1


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
