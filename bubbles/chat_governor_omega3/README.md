# Bubbles Adaptive Chat Governor Ω3.6

Ω3.6 keeps the Ω3.4 completion/cognitive-precision core and adds a CFBE frontier performance tranche aimed directly at the current chat's remaining bottlenecks: owner-attention noise, hot-context inflation, repeated provider discovery, non-durable nondeterministic calls, fixed concurrency, weak cross-agent protocol identity, and one-off integrity failures.

## Core contract

**Load capability, not history. Retrieve evidence, not entire archives. Activate specialists, not organisations. Think adversarially before converging. Mission completion outranks turn completion. Solve before reporting recoverable problems.**

## Existing Ω3.4 foundation retained

- SQLite WAL durable mission, evidence, receipt, checkpoint, metrics and circuit-breaker state
- mission classification and minimum-specialist/minimum-connector compilation
- evidence pointer reuse with source-version/modified-state staleness checks
- connector relevance gating, idempotency receipts and semantic readback
- bounded exponential-backoff retries and per-connector circuit breakers
- EWMA latency/failure metrics and adaptive retrieval/result budgets
- HOT-0 / HOT-1 / WARM / COLD memory classification
- dependency-aware bounded-concurrency DAG executor with failed-lane isolation
- proof-bearing crash-safe checkpoints
- contradiction/evidence/risk/owner-burden route ranking
- falsifier, counterfactual-stability and convergence gates
- PRE_FINAL_RESPONSE Stop gate and maturity-language proof gate
- composable terminal states and mandatory-control coverage checks

## Ω3.6 CFBE frontier tranche

### LifecycleHookBus
Deterministic lifecycle events for `PRE_TOOL_USE`, `POST_TOOL_USE`, `POST_TOOL_FAILURE`, `PRE_COMPACT`, `POST_COMPACT`, `STOP`, `SUBAGENT_START`, `SUBAGENT_STOP`, `TASK_CREATED` and `TASK_COMPLETED`. Hooks can block before an action, transform the in-memory request, inject bounded context or record an external observation. They do not execute tools or grant provider authority.

### OwnerAttentionGovernor
Operationalizes Human-First `SOLVE_BEFORE_REPORT`: routine progress, retries and recoverable diagnostics remain internal. Verified milestones, terminal outcomes, material unresolved risk and genuine owner-only decisions are surfaced. Failed proof and material risk cannot be hidden.

### ContextIsolationBroker
Compiles hard-budget side-task packets and permits only summary/decision/proof/artifact/metric pointers to merge back. Raw tool dumps, provider dumps and full side-task transcripts are prohibited from re-entering the hot parent context.

### CapabilityCatalogCache
Deterministic provider capability ordering plus TTL/cache-scope/source-fingerprint checks. This avoids repeated broad tool discovery while explicitly refusing to infer authentication or authority from a cached capability list.

### DurableActivityBoundary
Separates deterministic control flow from nondeterministic provider/tool activity. A semantically verified prior result is replayed by durable reference instead of re-executing the provider call. Effectful activities require explicit authorization and semantic readback. The boundary itself never performs an external effect.

### AdaptiveParallelismController
Scales independent read-only fan-out according to context pressure, connector failure EWMA and latency while forcing effectful lanes to single-flight execution. This targets lower wall-clock time without creating effect storms.

### StablePrefixCompiler
Keeps invariant doctrine/schema/tool-contract context in a deterministic prefix and volatile evidence behind it, improving cacheability and reducing churn without claiming control over provider-native prompt caching.

### Performance controls
- producer-signed, freshness/generation/coverage-bound Recovery Snapshot;
- fenced O(1) SQLite task head with compare-and-swap, stale-writer rejection and hash-chain verification;
- hard Context Capsule with explicit omission manifest;
- executor-side stream guard for payload overflow, retry storms, concurrency overflow, raw serialization, secrets, unchanged-route retries and owner-attention overflow.

### Protocol-neutral interoperability
`CapabilityAdvertisement`, `AgentTaskEnvelope` and `MCPRequestMetadata` provide deterministic skill/task/context/trace/cache identities inspired by current A2A/MCP contracts. They are local projections, not claims of wire-level A2A or MCP certification. Authentication and authority remain explicit.

### TraceToRegressionBridge
Observed integrity failures become durable replay candidates instead of one-off explanations. F19-F27 map premature termination, proof conflation, orphaned mandatory controls, outcome-first violations, maturity overclaim, owner-attention noise, context contamination and provider re-execution into named deterministic regressions.

## Target hot path

```text
User objective
  -> MissionCompiler
  -> StablePrefix + hard Context Capsule
  -> capability-cache lookup / exact discovery only on miss
  -> Lifecycle PRE_TOOL gates
  -> Context-isolated specialist DAG
       -> adaptive read-only parallelism
       -> effectful single-flight
       -> DurableActivityBoundary
       -> ConnectorGateway / SOVARA authority gate
       -> semantic provider readback
  -> side-task summary + proof-pointer merge only
  -> PRE_FINAL_RESPONSE integrity gate
  -> OwnerAttentionGovernor
  -> verified outcome / exact owner decision only
  -> durable checkpoint + regression learning
```

## Truth boundary

Ω3.6 is **source/runtime middleware**, not a modification of hidden ChatGPT context management, model weights, OpenAI serving infrastructure, browser/mobile clients or connector calls that bypass this package. Local SQLite is not represented as multi-instance distributed durability. Lifecycle hooks are enforceable only where the host invokes the bus. Protocol-neutral envelopes are not wire certification. Prompt-prefix stability is not proof of a provider cache hit. Provider effects remain Human-First/SOVARA/authorization/readback bound.

## Verification

Run from repository root:

```bash
python -m unittest bubbles.chat_governor_omega3.test_omega3 -v
python -m unittest bubbles.chat_governor_omega3.test_cognitive_precision -v
python -m unittest bubbles.chat_governor_omega3.test_pre_final -v
python -m unittest bubbles.chat_governor_omega3.test_frontier_runtime -v
python -m unittest bubbles.chat_governor_omega3.test_performance_controls -v
python -m unittest bubbles.chat_governor_omega3.test_interop_frontier -v
python -m unittest bubbles.chat_governor_omega3.test_regression -v
```

Promotion beyond deterministic/source verification requires exact-head repository admission and prospective matched observations on the intended host/provider surface.
