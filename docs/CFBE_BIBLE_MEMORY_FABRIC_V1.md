# CFBE Bible Memory Fabric v1

Status: SHADOW CANDIDATE. No canonical Bible, provider runtime, native ChatGPT capture, external effect, or model-weight learning is claimed.

## Mission
Turn the existing Federation Bible estate into continuous, ever-growing, proof-bounded operational memory without turning Bibles into an ever-heavier machine database.

## Core decision
**Immutable machine memory becomes the operational source of truth. Bibles become human-readable projections over that memory, while doctrine prose remains separately human-governed.**

The existing three-layer law remains controlling:
1. Immutable Event Truth
2. Current Verified Projection
3. Derived Interpretation

## Target plane

### 1. Immutable Memory Event Log
Every material directive, mission transition, decision, correction, result, failure, proof, capability adoption, conflict and supersession becomes a typed event. Events carry stream identity, stream version, recorded time, valid time, idempotency key, privacy/truth class, source/proof references and causal lineage.

### 2. CQRS / projection compiler
Commands append events through governed writers. Systems registry, current mission, blocker views, next-action views, dashboards and dynamic Bible sections become rebuildable materialized projections. Projection failure must never rewrite event truth.

### 3. Temporal memory
Store both recorded/system time and valid/domain time. Queries must support CURRENT and AS-OF reconstruction. This generalizes existing EVENTDATE and observed-at controls.

### 4. Directive and mission lineage
Each owner directive links to intent, objective, MissionIR, execution DAG, decisions, tool/provider observations, failures, repairs, proofs, accepted result, corrections and successor directives.

### 5. Durable workflow history
Reuse Bubbles, Omega-One and ChatBridge. The memory plane records workflow history, checkpoints, retries, version identity and replay/shadow evidence; it does not become a second orchestrator.

### 6. Hybrid retrieval
Combine exact keyword/full-text matching, semantic/vector similarity, graph/dependency traversal, temporal filters, source/proof filters and workstream/privacy scope. Existing SemanticMemory becomes an input gene, not the final system.

### 7. Hot / warm / cold / archive tiers
- HOT: current mission capsule and blockers
- WARM: active workstream memory and recent events
- COLD: immutable full history and superseded state
- ARCHIVE: large/raw payloads in authorized object stores

Summaries and capsules point to full history and never replace it.

### 8. Privacy envelope
Global memory stores minimum necessary portable fields and pointers. Sensitive raw payloads remain in authorized domain stores. Global memory rejects secrets/private raw content. Redaction/tombstone/key-destruction policy must be designed before provider deployment.

### 9. Idempotency and concurrency
Safe retries are resolved before optimistic version conflicts. Same idempotency key with different material parameters fails closed. Appends use expected stream versions. Cross-stream logical commits use atomic transactions where available or PREPARED -> COMMITTED plus independent readback.

### 10. Schema evolution
Every event binds a schema version. Historical events are immutable. Readers use tested upcasters/migrations and exact instrument/version replay obligations.

### 11. Provenance and attestation
Every derived projection and rendered Bible section binds event range/hash, source refs, compiler/version and proof refs. Software/build artifacts use signed provenance/attestation where available.

### 12. Bible renderer
Human-facing Bibles keep stable identity, doctrine, constitution and curated narrative. Dynamic sections such as Current State, Timeline, Directives, Decisions, Failures, Proof, Blockers and Next Action are generated from verified memory projections.

### 13. Memory SRE
Measure capture lag, projection lag, stale-read rate, duplicate suppression, replay RTO, recovery point objective, lost-tail rate, contradiction rate, retrieval quality, owner reconstruction rate and memory cost per mission.

### 14. Disaster recovery
Snapshots accelerate restore but are disposable. Event truth must replay into clean projections. Restore drills verify integrity, snapshot compatibility, projection rebuilding and bounded RTO/RPO.

## CFBE target
The deterministic benchmark rates the current architecture at 66.43/100 design and 50.49/100 proof-adjusted operational maturity, versus a 96.66/100 target. These are CFBE heuristic architecture scores, not vendor-certified superiority metrics.

## Harvested capability genes
BMF-001..BMF-024 cover event sourcing, CQRS, materialized views, transactional outbox/idempotent consumers, optimistic concurrency, durable workflow history/replay, hybrid retrieval, bitemporal state, provenance attestations, uniform idempotency, change-stream fanout, memory tiers, snapshots, schema upcasting, directive lineage, ADRs, privacy, SLOs, PITR/restore drills, Bible rendering, memory API/SDK, quality courts and continuous CFBE harvest.

## Migration rule
No big-bang rewrite.

1. Shadow-capture one active workstream into typed events.
2. Rebuild its current state and Bible operational section from events.
3. Compare against the existing Bible/heartbeat/KDV truth.
4. Run restore/as-of/conflict/idempotency/privacy tests.
5. Measure owner burden and stale-state reduction.
6. Only after value proof, make generated projection authoritative for that operational slice.
7. Repeat by workstream/system; keep legacy Bibles as historical/canonical doctrine surfaces until migrated.

## Hard boundaries
- No flattening domain authority.
- No raw private transcript corpus in global memory.
- No model-weight learning claim.
- No provider-live claim from source/tests.
- No summary replacing immutable event truth.
- No external effect authority inherited from memory state.
