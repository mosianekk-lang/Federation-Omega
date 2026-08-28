# SUPERIOR LOGIC × GEMINI — FRONTIER CONVERGENCE PROGRAM v1

Status: SOURCE IMPLEMENTATION / PROVIDER-DISABLED CANARY READY / PROVIDER-LIVE PROMOTION SEPARATELY GATED  
Authority ceiling: A1_INTERNAL  
External-effect default: false

## 1. Mission

Turn frontier AI innovation into a governed, provider-neutral, empirically tested capability-acquisition loop for Superior Logic and the Federation.

The program is not a one-off Gemini integration. Gemini/Google is the first convergence domain. The program continuously observes the best public mechanisms from Google, Microsoft, AWS, OpenAI, Anthropic, Palantir, ServiceNow and other CFBE challengers; decomposes mechanisms from vendor packaging; forms provider-neutral candidates; compares them against incumbents under an exact experiment identity; and promotes only receiver-local, regression-safe, rollback-proven gains.

## 2. Constitutional split

Owner
→ Superior Logic Cognitive OS: mission semantics, algorithms, experiment identity, proof policy, TerminalTruth, learning
→ SOVARA: route, identity/credential reference, exact-effect authority, provider execution, retries, rollback, provider receipt
→ Frontier Convergence: mechanism harvest, experiment/control contracts, scenario branching, telemetry/value/provenance, convergence admission
→ Gemini / other processors: replaceable cognitive processors
→ Google AI Studio: builder/cockpit/prototyping surface, never canonical authority
→ JARVIS / Sentinel / CFBE / RealityGuard: independent challenge, observability and failure intelligence
→ KDV / Bibles / ledgers: durable canonical projections and provenance

No provider model can promote canonical truth or expand authority by its output.

## 3. Reuse map

The suite deliberately does not rebuild existing Federation components.

- MCE (`formation_omega.mission_convergence`) remains mission closure, proof vector, failure-resolver and hash-ledger authority.
- FCI Omega (`formation_omega.institutional_cognition`) remains evidence-weighted council, independence-domain discounting, minimax-regret scenario selection and staged policy evolution.
- SOVARA provider fabric remains the execution plane with isolated provider cells, credential references and effect admission.
- Federation Orchestration Kernel remains the broad mission/idempotency/lease/checkpoint runtime.
- CFBE-Ω remains the living benchmark/challenger system.
- Secure Capability Box remains the secret-reference and least-privilege control.
- JARVIS, Sentinel and CFBE remain independent completion votes.
- KDV and the Live Bibles remain deterministic material-delta projections.

Frontier Convergence adds only the missing cross-cutting contracts and orchestration.

## 4. Core convergence loop

OBSERVE
→ SOURCE/EVIDENCE BIND
→ DECOMPOSE VENDOR FEATURE INTO MECHANISM
→ MATCH INCUMBENT
→ FORM PROVIDER-NEUTRAL CANDIDATE
→ COMPILE EXPERIMENT IDENTITY
→ SHADOW / SCENARIO BRANCH
→ ROBUSTNESS COURT
→ INDEPENDENT QUORUM
→ SOVARA CANARY
→ PROVIDER SEMANTIC READBACK
→ VALUE / COST / OWNER-BURDEN RECEIPT
→ PROMOTE / HYBRIDIZE / HOLD / REJECT
→ LEARNING + CAPABILITY LEASE
→ CFBE REBENCHMARK

A candidate is not comparable to its incumbent when experiment fingerprints differ materially.

## 5. Production capabilities

### FC-01 Federation Agent Identity
Provider-neutral identity contract: agent, trust domain, provider subject reference, authority ceiling, allowed actions/resources, issue/expiry, evidence, delegation and revocation. Provider identities may map to Google Agent Identity, cloud workload identity, SPIFFE-style identities or another implementation without changing the constitutional contract.

### FC-02 Sovereign Tool / MCP Gateway contract
All model-generated action proposals must become an exact `EffectContract`: mission, target, action, public-safe parameters, action mode, authority class, idempotency key, expected semantic result, readback plan, rollback plan and privacy envelope. SOVARA remains the executor.

### FC-03 Mission Scenario Branching
Consequential proposals can be applied to an isolated state branch. The branch produces a deterministic diff and never mutates canonical state. Promotion of a scenario delta is a separate effect transaction.

### FC-04 Durable Convergence State
The suite ships a small SQLite/WAL append-only convergence store for signals, events, assets and idempotency reservations. It complements rather than replaces the Federation mission ledger.

### FC-05 Unified Mission / Model / Tool / Effect Telemetry
Trace records carry mission ID, run ID, provider, model, tool, effect ID, latency, token counts, cost, semantic state, readback state and proof references. Production adapters should map these fields onto OpenTelemetry GenAI conventions where available.

### FC-06 AI Control Tower
Inventory object types: agents, models, tools, MCP servers, runtimes, datasets, credential references, prompts and applications. Every asset has owner, purpose, lifecycle, authority ceiling, proof level, proof references, dependencies, observed time and optional expiry. Stale assets degrade automatically.

### FC-07 FinOps + Value Pareto Router
CFBE/SOVARA should compare only measured candidates above a minimum quality/reliability floor. Pareto selection favors options that are not dominated across quality, reliability, latency, cost, owner burden and outcome value. Cost may never silently reduce the required quality floor.

### FC-08 Supply-chain / Capability Provenance
Build/capability attestations bind subject digest, source revision, builder, material digests, build parameters and environment. This is compatible in spirit with SLSA/in-toto/Sigstore provenance without claiming a signature or transparency-log entry unless those providers actually issue one.

### FC-09 Robustness Court
Required gates: HOLDOUT; PARAMETER_PERTURBATION; ADVERSE_COST_OR_LATENCY; CROSS_REGIME_OR_ENVIRONMENT; SIMPLE_BENCHMARK; INPUT_PROVENANCE. A passed gate requires evidence.

### FC-10 Capability Leases
Proof is receiver-local and expiring. One model/provider/runtime success cannot silently become another receiver's maturity and old proof cannot remain live indefinitely.

### FC-11 Privacy Envelopes
Minimum-necessary field allowlists, explicit prohibited fields, classification, retention duration, raw-evidence policy and provider-reuse policy travel with the mission/tool call.

### FC-12 Budget Leases
Finite currency/amount/expiry/provider envelope. Positive spend is not allowed simply because a route exists. The existing pre-revenue cost governor remains authoritative.

### FC-13 Schema Compatibility Handshake
MIC/SER/telemetry/tool/provider adapters must check producer/consumer contract versions and required fields before exchange. Schema drift is a typed failure rather than an implicit retry.

### FC-14 Replay Fence + Idempotency
Stable payload hash plus idempotency key. Reuse with an identical payload becomes replay; reuse with a changed payload fails closed.

### FC-15 Connector Intent Guard
Every connector/tool is preclassified READ or MUTATE. A read-intent workflow calling a mutation action fails closed before execution. This directly hardens against operator/tool-selection mistakes.

## 6. High-leverage innovations added beyond the initial proposal

### Correlation-aware quorum
Do not count three models routed through one provider/account/toolchain as three independent witnesses. FCI already discounts same-domain repetition. Provider, execution substrate, source and verifier domains should all be represented in production independence metadata.

### Champion anchor
Every experiment has an immutable incumbent/champion identity and benchmark dataset/fixture hash. A candidate cannot win by changing the test during the tournament.

### State epoch / single-writer fence
Effectful state has an epoch/revision. A mutation compiled against an older epoch is rejected or recompiled. This prevents stale candidate promotion and conflicting provider effects.

### Ambiguous-effect hold
Transport success without unambiguous semantic state enters HOLD, not retry. The system first reads current source state to avoid duplicate effects.

### Failure-domain circuit and degraded modes
A failed provider cell opens only its own circuit. Safe independent lanes continue. Degraded operating states are S0 full federation; S1 multi-provider degraded; S2 single-provider/cloud degraded; S3 provider-disabled private core; S4 recovery.

### Control-plane anti-drift
Asset/identity/capability leases have freshness. Provider, source and canonical projections can disagree without silent overwrite; the freshest higher-authority evidence wins current routing while conflicts remain recorded.

### Evidence economics
Experiments should be selected by expected information gain per unit cost/latency/owner burden, not just predicted success. Negative results are valuable and preserved.

### Semantic effect firewall
Natural-language proposals are not executable. Only structured effect contracts with target, action, bounded parameters, identity, readback and rollback can enter SOVARA's effect lane.

### Kill switches
Circuit state supports CLOSED, OPEN, HALF_OPEN and KILLED. KILLED requires an explicit recovery path before any effect resumes.

## 7. Gemini first convergence domain

`GeminiAdapter` compiles a provider call plan. It does not call Google.

The call plan contains mission ID, provider/protocol, exact model reference, credential reference name only, public-safe request body, tool allowlist, required provider readback fields, privacy envelope, explicit provider-authority requirement, billed-project identity requirement and semantic nonce requirement.

Required Gemini readback: provider request ID, model identity, semantic nonce, finish state, usage, latency, provider identity.

A Gemini result cannot become canonical truth and cannot prove AI Studio inventory or Google Cloud deployment.

## 8. Cockpit

The bundled web cockpit is an internal control UI for runtime health, frontier signal registration and isolated scenario materialization. It intentionally does not execute provider effects. Google AI Studio can be used as a richer builder/front end later, while SOVARA/Google agent infrastructure remains the production execution plane.

## 9. Faults converted into permanent controls during genesis

Two real build-time faults were observed during this workstream:

1. A repeated connector invocation created a duplicate GitHub control issue. Containment: duplicate closed; #663 remains canonical. Permanent control: stable workstream identity + idempotency reservation + payload conflict rejection.
2. A wrong Drive action created a throwaway spreadsheet while a read was intended. Containment: throwaway artifact deleted; no canonical Federation file altered. Permanent control: `ConnectorIntentGuard` requires declared READ/MUTATE mode to match the callable mode before execution.

These are regression fixtures, not merely incident notes.

## 10. Production acceptance ladder

### SOURCE_READY
- branch source exists;
- deterministic tests pass;
- secret-field rejection passes;
- provider-disabled canary passes;
- source readback/hash available.

### AIRLOCK_ADMITTED
- pull request opened;
- exact PR head passes Airlock/source provenance/leak guard and required tests;
- merge result read back.

### INTERNAL_RUNTIME_VERIFIED
- container starts;
- `/health` returns expected version/state;
- durable store survives restart where configured;
- event-chain and idempotency tests pass;
- rollback/restoration of convergence state passes.

### GEMINI_CANARY_VERIFIED
- provider identity and billed project resolved without exposing secret;
- exact model resolved;
- semantic nonce round-trip;
- usage/latency/readback captured;
- privacy/cost controls pass;
- no ambiguous effect;
- rollback/kill path verified.

### BIDIRECTIONAL_WORKSPACE_VERIFIED
- one bounded authorized Workspace read/write path;
- exact target readback;
- duplicate suppression;
- failure isolation;
- rollback;
- independent observation.

### PRODUCTION_QUALIFIED
- sustained soak;
- operational telemetry;
- SLOs;
- cost/value measurements;
- failure injection/recovery;
- JARVIS + Sentinel + CFBE independent closure;
- strict maturity gate allows the exact label.

No stage inherits from source, configuration, another provider cell or historical success.

## 11. Current truth boundary

The source suite can be production-ready as software before external Gemini/Google production is provider-proven. Source/CI/canary success must not be reported as Google deployment, Gemini provider authority, AI Studio inventory access, background autonomy or production traffic.
