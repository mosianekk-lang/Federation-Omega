# CFBE Parallel Prompt Fabric v4

## Purpose

CFBE Parallel Prompt Fabric v4 converts high-level owner intent into a finite,
proof-oriented mission graph, uses the existing CFBE vNext multistream kernel
for effect-free parallel work, and evaluates prompt refinements through a
bounded Prompt Scientist. It is an orchestration layer, not a new sovereign
scheduler, authority root, provider executor or proof plane.

## Composition, not duplication

The repository already contains `MissionExecutionKernel`, `ExecutionGraph` and
`MultiStreamExecutionBridge` under
`benchmarking/cfbe_omega/mission_execution_kernel_vnext`. Those components own
mission durability, logical-path fencing and effect-free multistream fan-out /
fan-in. v4 adds the missing layer above them:

1. compile owner intent into deterministic work packets;
2. compute a critical path and collision-safe waves;
3. hold provider/external-effect work under the A1 ceiling;
4. adapt eligible effect-free packets into the existing vNext graph;
5. enforce a proof ladder for terminal claims;
6. circuit-break repeated deterministic failures after the second identical
   fingerprint;
7. plan compatibility-gated version propagation;
8. evaluate prompt variants using measured mission outcomes.

## Parallelism boundary

Read-only independent packets may run concurrently when dependency and
collision keys permit. Canonical writes, shared-target mutations, A1 internal
mutations, provider mutations and external effects never gain authority from
parallel scheduling. Canonical/internal writes are serialized. Provider and
external-effect packets are held until a separately authorized provider route
exists and can produce native readback.

## Prompt Scientist

The Prompt Scientist treats prompt refinement as an experiment. It preserves the
incumbent, diagnoses concrete execution failure modes, forms P1/P2/P3
challengers and scores them against completion, correctness, proof, execution
efficiency, parallel utilization, owner burden, recovery, context efficiency
and creative freedom. A critical constitutional/security/proof regression is an
absolute veto even if the aggregate score is higher.

The system may improve orchestration, routing, prompt structure, context use,
packet sizing, tool selection and algorithm portfolios. It does not claim to
retrain model weights or to have become more intelligent merely because source
or prompt text changed.

## `n` v3

`FEDOMEGA-N-DIRECTIVE-V3` preserves v2.1 semantics and adds an explicit mission
compiler, dependency DAG, collision-safe parallel scheduler, repeated-failure
circuit breaker, Prompt Scientist evaluation and compact completion receipt.
The predecessor remains available as rollback/historical compatibility.

## Proof states

`HYPOTHESIS -> DESIGNED -> SOURCE_PRESENT -> TESTED -> ADMITTED -> MERGED -> DEPLOYED -> RUNTIME_VERIFIED -> BEHAVIOR_VERIFIED -> PRODUCTION_VERIFIED`

Each state is monotonic and separately evidenced. Source admission does not
prove provider deployment. Runtime and production labels require the applicable
runtime/provider-native readback, health/persistence evidence and rollback proof.

## Performance semantics

“10x” remains an empirical target. Promotion requires matched workload evidence
showing improved completion/correctness/throughput or reduced latency/owner
burden without proof, security or quality regression. This source tranche does
not claim such a measured gain by itself.

## Rollback

The source change is additive. `FEDOMEGA-N-DIRECTIVE-V2@2.1.0` remains the
rollback contract. Prompt candidates preserve the incumbent and can be rejected
without mutating constitutional invariants. No provider state is changed by
this package.
