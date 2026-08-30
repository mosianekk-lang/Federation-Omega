# Omega Completion Engine Architecture

## 1. Architectural objective

Build one deterministic control plane that allocates work across multiple paths and streams without losing mission identity, proof requirements, authority boundaries or recovery state.

The engine optimizes for verified mission completion, not maximum concurrency.

## 2. Composition

The architecture is a reconciliation of three foundations:

1. Formation Reconciliation Fabric v2 supplies desired/observed state, topology selection, policy decisions, durable replay semantics and independent challenger roles.
2. SOL 6.1 supplies event-sourced mission state, worker/coordinator primitives, queue leases, fencing, backpressure, adaptive provider routing, checkpoints and receipts.
3. Omega-One PR #843 supplies a candidate contiguous proof-maturity compiler and zero-dilution Universal Capability Contract interoperability spine.

Omega-One PR #843 is not merged. Its code is treated as an isolated candidate input, and its proof maturity cannot exceed branch-source/local-test or hosted-check evidence actually observed.

## 3. Logical component map

| Layer | Responsibility | Reused source or target module |
| --- | --- | --- |
| Mission governor | Versioned desired state, requirement state, cancellation and terminal proof contract | Formation mission/reconciliation semantics; omega_one.work_engine |
| Capability registry | Typed capabilities, provider/version flags, effect and maturity ceilings | Omega-One Universal Capability Contract |
| Graph compiler | DAG nodes, dependencies, read/write sets, joins and critical path | omega_one.work_engine |
| Policy kernel | Authority, privacy, cost, preview, proof and rollback vetoes | Formation policy semantics; omega_one.work_engine and omega_one.provider_adapters |
| Topology planner | Deterministic, sequential, parallel, hybrid and builder/falsifier/witness selection | Formation adaptive topology |
| Allocator | Weighted fairness, affinity, capacity, queue depth, latency, cost and reliability | SOL coordinator plus adaptive execution |
| Worker plane | Idempotent enqueue, leases, heartbeats, retries, checkpoint continuation and dead letter | SOL DurableWorkerPlane |
| Transaction store | SQLite WAL record transactions, revisions, idempotency reservations, legacy migration, backups, admission outbox and dispatch-transition claims | omega_one.transaction_store |
| Provider adapters | OpenAI, Gemini and Copilot capability translation | omega_one.provider_adapters; live execution disabled |
| Effect gateway | One serialized, permit-bound effect route with outbox, fencing and reconciliation | SOL provider bridge plus Federation dispatch safety pattern |
| Join and court | Fan-in, contradiction detection, synthesis, falsification and witness decision | omega_one.work_engine plus Omega-One promotion court |
| Telemetry | Correlated spans/events, redaction, audit-chain verification and metrics | omega_one.telemetry |
| CLI | Local deterministic demo and command entry point | omega_one.cli and omega_one.__main__ |

## 4. Mission and task contracts

### Mission

A mission contains:

- stable mission ID and monotonically increasing version;
- objective and terminal fruit;
- active requirements;
- authority, privacy, cost, time and concurrency ceilings;
- required proof types;
- stop and cancellation state;
- current checkpoint;
- provenance and correlation IDs.

### Task

Every task contains:

- task ID and mission/version binding;
- capability ID and typed input/output schemas;
- dependency IDs;
- declared read set and write set;
- effect class: READ, INTERNAL_WRITE or EXTERNAL_EFFECT;
- authority/privacy/cost ceilings;
- idempotency key;
- timeout, attempts, retry class and checkpoint reference;
- completion proof requirements;
- cancellation token and lease epoch.

### Result

Every result contains:

- task and mission identity;
- terminal state;
- output reference and content hash;
- provider/model identity when externally executed;
- trace and parent-span identity;
- cost/latency/attempt metrics;
- evidence references;
- readback or rollback state;
- residual uncertainty and contradictions.

## 5. Control sequence

### Phase A: intake and compilation

1. Accept the latest user-authoritative objective.
2. Compile one current mission version.
3. Invalidate stale actions and dependent descendants.
4. Resolve reusable capabilities before proposing new infrastructure.
5. Compile a typed DAG and calculate its independent frontier.
6. Preflight every task idempotency key against the batch, transactional reservation index and durable-worker index.
7. Commit the mission, task rows, reservations and one durable admission-outbox record atomically under `BEGIN IMMEDIATE` and an expected control revision.
8. Materialize SOL and worker sidecars idempotently from the claimed outbox; restart recovery drains a committed but unapplied admission.
9. Reject duplicate or conflicting keys with zero new mission, task, worker-job or outbox mutation.

For dispatch, the scheduler computes a bounded READY-frontier wave, simulates fairness and worker capacity, then atomically commits all control leases plus one durable `DISPATCH_WAVE` transition intent. The inherited worker journal is materialized idempotently after that commit. Restart accepts an already matching partial lease and finishes the remaining intent. Proof completions and effectful tasks stay on their existing single-item transaction paths.

### Phase B: policy before optimization

Hard vetoes run before scoring:

- mission/version mismatch;
- inactive or cancelled requirement;
- authority ceiling exceeded;
- privacy classification mismatch;
- unknown incremental cost;
- unverified provider capability;
- preview feature disabled;
- missing rollback for a write;
- shared-write conflict;
- stale lease or checkpoint;
- missing completion proof contract.

A denied candidate never reaches a provider adapter.

### Phase C: topology and allocation

The scheduler chooses:

- DETERMINISTIC for purely mechanical transformations;
- SINGLE_CONTROLLER for tightly coupled or consequential work;
- PARALLEL_CELLS for high independent width and low shared-state coupling;
- HYBRID for independent research/build branches followed by serialized synthesis;
- BUILDER_FALSIFIER_WITNESS for high-consequence claims or promotion.

The root orchestrator owns fan-out and fan-in. A child may not recursively expand concurrency unless its task contract explicitly grants a smaller bounded child budget.

Utility is evaluated only after vetoes. A representative provider-neutral score considers:

- expected mission-value reduction;
- information gain;
- proof gain;
- reliability and route confidence;
- cost, latency, risk and active load;
- dependency criticality;
- contention and owner burden.

The exact weights are configuration and benchmark subjects, not immutable doctrine.

### Phase D: branch-isolated execution

- Parallel tasks receive only their bounded context envelope.
- Each lane writes to its own result namespace.
- Shared mutable state is read-only during fan-out.
- Every branch emits a successful result, typed failure, cancellation or timeout.
- Missing branch output is a failed join precondition.

### Phase E: fan-in

The join barrier:

1. verifies required predecessor identities and hashes;
2. rejects stale mission versions and fenced workers;
3. checks schema and proof completeness;
4. detects contradictions and overlapping writes;
5. invokes a falsifier/witness when required;
6. compiles one deterministic synthesis candidate;
7. forwards at most one effect request to the effect gateway.

### Phase F: effect and closure

External delivery is at-least-once. Safety comes from:

- a durable outbox;
- stable provider idempotency keys;
- bounded claim leases;
- monotonic fencing;
- an exact provider snapshot;
- semantic readback;
- uncertain-outcome quarantine;
- reconciliation before retry;
- rollback when supported.

Exactly-once remote mutation is never inferred.

Mission closure requires the contiguous proof contract. Later-stage evidence cannot skip a missing predecessor.

## 6. Load balancing

Load management has three layers:

1. Workload admission limits queue growth and rejects unaffordable or unauthorized work.
2. Task allocation applies tenant/workstream fairness, capability affinity and dependency priority.
3. Provider routing applies concurrency, quota, latency, reliability, breaker and cost constraints.

Required runtime measurements:

- queue depth and oldest age;
- ready/running/held/dead-letter counts;
- worker capacity, active leases and heartbeat age;
- provider concurrency, quota and reset time;
- per-route success rate, latency and unit cost;
- retry, timeout and cancellation rates;
- proof age and completion defect rate.

OpenAI adapter advisory concurrency starts at 3. It is neither a provider guarantee nor an entitlement. Gemini and Copilot limits must be discovered from their current adapters and can reduce the global wave to one.

## 7. Provider boundaries

### OpenAI adapter

- Translates a task envelope to the supported OpenAI agent/tool surface.
- Returns observed model, result, usage, status and trace references.
- Uses root-owned bounded delegation.
- Does not expose hidden reasoning or infer platform internals.

### Gemini adapter

- Uses isolated branch state and explicit joins/checkpoints.
- Requires a current model/version capability flag.
- Managed agents, A2A and preview routes are disabled by default.
- Conversation state and execution-environment state remain separate.

### Copilot adapter

- Treats semantic delegation and deterministic flows as separate capabilities.
- Does not treat Copilot routing as a least-loaded scheduler.
- Prohibits autonomous execution under maker credentials.
- Requires explicit environment, identity, licensing/cost and telemetry state.

## 8. Authority and privacy

### Authority

| Class | Engine meaning |
| --- | --- |
| A0 | Observation and read-only verification |
| A1 | Internal planning, code and reversible local state |
| A2 | Bounded external effect with exact permit and rollback/readback |
| A3+ | Consequential action; owner-reserved unless a later explicit contract states otherwise |

The default is A1. Capabilities and provider adapters never raise authority.

### Privacy

- Context is minimized per task.
- Conversation history is not passed by default.
- Secrets are references, never payload values.
- Telemetry recursively redacts secret-like keys and bounds payload sizes.
- Provider-specific retention and data-use terms are adapter admission conditions.
- Legal, identity, case and sensitive-person data require a separate matter boundary.

## 9. Cost control

- No paid route is eligible without a finite cost envelope.
- Unknown price or quota is a hold, not zero.
- Interactive, scheduled and autonomous traffic have separate budgets.
- Retries consume the same mission budget and cannot silently expand it.
- The scheduler may downgrade intelligence only when proof and quality thresholds remain satisfied.
- Provider cost reports require observed usage/readback, not catalogue prices alone.

## 10. Cancellation

A cancellation is a state transition, not a message:

1. set the mission or task cancellation token;
2. stop new leases;
3. cancel queued descendants;
4. signal cooperative workers;
5. fence late results by mission version and lease epoch;
6. preserve completed independent proof;
7. reconcile any in-flight external outcome;
8. checkpoint the cancelled state.

External cancellation does not imply reversal of an already-completed provider effect.

## 11. Recovery

Recovery order:

1. verify SQLite integrity, foreign-key state, record digests and control-event hash chains;
2. reload the current transactional revision;
3. recover stale outbox claims and idempotently materialize committed admissions;
4. verify SOL and worker sidecars against control tasks and reservations;
5. recover expired execution leases;
6. classify unfinished work as safe replay, outcome unknown or dead letter;
7. reconcile provider-native status before retrying an uncertain effect;
8. recompile the ready frontier and resume only current-version tasks;
9. record recovery proof.

Repeated identical failures open a circuit and require a materially different route or changed precondition.

## 12. Observability

All mission, task, worker, model, tool, provider, join and effect events carry:

- correlation ID;
- mission/task/attempt identity;
- traceparent or equivalent trace context;
- event time and duration;
- authority/privacy/effect class;
- provider/model when observed;
- status, failure class and retry disposition;
- redacted evidence references;
- hash-chain link where durable.

Payload contents are excluded by default.

## 13. Proof maturity

The intended contiguous maturity order is:

DESIGNED → SOURCE_IMPLEMENTED → DETERMINISTIC_TESTED → CI_ADMITTED → DEPLOYED → PROVIDER_EXECUTED → SEMANTIC_READBACK_VERIFIED → REPEATED_SUCCESS → SOAKED → VALUE_VERIFIED

Current integrated engine state is SOURCE_IMPLEMENTED / DETERMINISTIC_TESTED, represented by the contract ceiling `TESTED_LOCAL`. The 72-test court, 16/16 actual-engine invariant court, same-host contention/crash/partial-transition-recovery courts, five-boundary H2-P process-kill canary and local CLI demo do not transfer to CI admission, live-provider execution, multi-host distributed operation, deployment, soak or owner value.

## 14. Provenance and unresolved risks

Current main:

- commit: 4f29813935a71f3d2fd344cf9075cfe4184a7e40
- tree: 3,137 non-truncated entries
- observed required-check enforcement: disabled

PR #843:

- state: open draft
- head: b1ccae6833410899ca07aada218a6b585d3c9f5e
- divergence: 28 commits ahead / 8 behind current main
- hosted checks: three exact-head checks passed
- scope: 23 changed files, 2,749 additions and 6 deletions
- proof boundary: branch-only, non-effect and not promoted

Open risks:

- live OpenAI, Gemini and Copilot clients are not authorized or provider-read back;
- SQLite WAL persistence has same-host cross-instance revision/idempotency contention proof, but no multi-host consensus, shared-datastore or leader-election proof;
- actual-engine CFBE remains `SHADOW_ONLY`: 16/16 invariants passed across eight paired workloads through 240 tasks, all measured P3/P1 workload ratios were 1.134x–2.648x and quality/fairness held, but live-provider, multi-host, hidden-suite, soak and real-media courts are absent;
- H2-P recovered 100/100 candidate missions across five real process-kill boundaries at 2.3080140919098455x versus its identical baseline and projected 260.98887359985383 seconds for 10,000 missions, but proof completion replayed two SOL proof receipts; full H2 is held pending transactional, idempotent proof finalization;
- main protection and required-check enforcement are not enabled;
- provider-specific costs, quotas and data handling are not runtime verified;
- no deployment, repeated-success, soak or owner-value proof exists.
