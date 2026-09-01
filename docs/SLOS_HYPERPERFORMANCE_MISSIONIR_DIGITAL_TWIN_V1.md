# SLOS Hyperperformance MissionIR + Digital Twin v1

## Status

`SOURCE_CANDIDATE / R4_ADMISSION_PENDING / PROVIDER_EFFECTS_HELD`

This release converts the highest-value opportunities from the full-chat audit into one bounded execution fabric. It does not introduce another cognitive sovereign. SLOS remains mission-semantic and terminal-truth authority, SOL 6.2 remains the transactional execution kernel, and SOVARA remains the provider/effect plane.

## MissionIR

Human/owner intent is compiled into a deterministic `SLOS_MISSION_IR_V1` containing:

- objective and source version;
- initial and target state;
- constraints and authority ceiling;
- typed transitions and dependency DAG;
- required semantic capabilities;
- effect class and reversibility;
- risk, value, uncertainty reduction, latency and cost estimates;
- conflict domains;
- proof obligations;
- mission budgets;
- a content-addressed compiled hash.

Cycles, duplicate transition IDs, unknown dependencies, negative budgets and speculative mutation are rejected before scheduling.

## Capability graph

`SLOS_CAPABILITY_GRAPH_V1` separates semantic capability from provider implementation. Routes carry empirical reliability/proof/latency/cost/owner-burden characteristics. Provider-backed routes may require a fresh `ProviderAttestationStore` record, so a paid account, historical success or static source flag cannot silently become current provider authority.

## Parallel hyperperformance scheduler

`CP_VOI_BOUNDED_BEAM_V1` uses multiple algorithms together:

1. critical-path depth to protect overall completion latency;
2. value-of-information scoring to resolve uncertainty early;
3. empirical route scoring through the existing SOL 6.2 champion/challenger primitive;
4. bounded beam search with branch pruning rather than exhaustive combinatorics;
5. conflict-domain fencing for parallel safety;
6. token-bucket admission for bounded fan-out/economic pressure;
7. work stealing for idle worker capacity;
8. read-only speculative route races when independent alternatives exist;
9. read-only straggler hedging beyond latency thresholds;
10. semantic first-winner fan-in requiring valid proof.

### Non-negotiable performance/safety rule

Speculation never duplicates a provider mutation. Mutating transitions may execute concurrently only when their conflict domains do not overlap, and the actual provider effect remains a single SOL 6.2/SOVARA transaction.

## Federation digital twin

`FEDERATION_DIGITAL_TWIN_V1` models missions, capabilities, providers, artifacts, authority, proofs, runtimes and workers as nodes/edges with content-addressed snapshots. Counterfactual interventions are applied to a cloned twin and explicitly report `provider_effect_performed=false`.

The controller ranks intervention, no-action and reversible alternatives by target-state match, expected value, uncertainty reduction, risk, cost and latency before real authority is spent.

## Empirical self-improvement

`ShadowEvolutionLab` reuses SOL 6.2 `ChampionChallenger` and `LearningPromotionGate`. Challengers are evaluated from recorded shadow outcomes and cannot promote unless they have:

- enough samples;
- at least two independent evidence sources;
- the configured measured performance gain;
- no open contradictions;
- zero critical regressions.

A promotion decision is evidence, not provider authority. Normal SOL/SLOS admission still applies.

## Automatic opportunity discovery

`OpportunityScanner` mines mission telemetry for recurring high-latency work, owner intervention burden, failures/timeouts and repeated deterministic operation signatures. It emits optimisation candidates rather than silently rewriting the system. Only low-risk compute-efficiency opportunities such as content-addressed memoization may be marked automatically executable; structural/provider changes remain governed.

## Execution-fabric facade

`HyperperformanceExecutionFabric` is the only high-level entry point introduced by this release. It compiles MissionIR, projects the mission into the digital twin, resolves the capability graph and generates a safe parallel plan. It deliberately performs no provider effect.

The constitutional chain remains:

```text
Owner Intent
  -> SLOS mission semantics / MissionIR
    -> Hyperperformance plan + digital-twin simulation
      -> SOL 6.2 transaction kernel
        -> SOVARA provider/effect plane
          -> provider-native readback
        -> SOL proof commit
    -> SLOS terminal truth / learning
```

## Proof boundary

A green R4 source court proves deterministic compiler, planner, simulation and shadow-evolution invariants. It does not prove external 24x7 deployment, provider-live effects, multi-region consensus, universal exactly-once provider semantics, stable-release promotion or sustained owner value. Those remain separate empirical/provider gates.
