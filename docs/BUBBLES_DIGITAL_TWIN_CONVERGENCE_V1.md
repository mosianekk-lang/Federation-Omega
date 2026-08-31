# BUBBLES DIGITAL-TWIN CONVERGENCE v1

Status: SOURCE CANDIDATE — proof/promotion gates remain separate  
Baseline: `ea5876e67939687673a830f68d076326c9f7cb9d`  
Mission: reduce routine owner burden so the owner can spend more time on creative, strategic and final-choice work while Bubbles handles bounded orchestration, research, solution building, verification and recovery.

## 1. Truth boundary

This convergence does **not** claim AGI, invisible background execution, universal provider authority, or a finished digital twin. It defines and implements a governed path toward a digital-twin operating fabric using existing Federation assets first.

A benchmark record is not runtime proof. Source presence is not operational maturity. External/provider effects require receiver-specific authority and provider-native readback. High-consequence actions remain owner-gated. CFBE remains the independent benchmark/promotion governor.

## 2. CFBE 150-capability benchmark

Three 50-capability courts are registered:

- `bubbles_digital_twin_high_performance_50_v1.json`
- `bubbles_digital_twin_ai_autopilot_50_v1.json`
- `bubbles_digital_twin_agi_oriented_50_v1.json`

The AGI-oriented court means capabilities useful for increasingly general agents; it does not assert that Bubbles or any compared system is AGI.

### High-performance court

50 capabilities: durable execution, DAG scheduling, WIP, parallel waves, failure-domain placement, backpressure, queues, idempotency, retries, bulkheads, routing, caching, observability, SLOs, shadow/canary, rollback, replay, provenance, capacity and regression controls.

Current CFBE classification at benchmark creation:

- 21 REUSE_NOW
- 12 EXTEND_EXISTING
- 11 BUILD_SMALLEST_GAP
- 3 DATA_GATED
- 3 PROVIDER_GATED

### AI-autopilot court

50 capabilities: goal decomposition, MissionIR, dynamic tool discovery, MCP/A2A, reusable skills, specialist/sub-agent fleets, memory, sandboxes, browser/computer use, code/test loops, critic/verifier agents, evaluation, identity/policy, recovery, monitoring, connectors and structured contracts.

Current CFBE classification:

- 9 REUSE_NOW
- 31 COMPOSE_EXISTING
- 3 BUILD_SMALLEST_GAP
- 7 PROVIDER_GATED

### AGI-oriented/generalist court

50 capabilities: transfer, causal/counterfactual reasoning, hypotheses/falsification, meta-learning, self/world models, long-horizon planning, autonomous research, truth maintenance, abstraction/skills/tool invention, digital-twin state, anticipation, opportunity detection, self-improvement, capability mortality, consensus, memory consolidation and bounded autonomy.

Current CFBE classification:

- 26 EXTEND_EXISTING
- 18 BUILD_SMALLEST_GAP
- 6 DATA_GATED

## 3. Frontier patterns harvested

The benchmark deliberately harvests **patterns**, not vendor prestige:

- OpenAI Agents SDK: handoffs, guardrails, tracing, memory/tool use, native controlled sandboxes and long-horizon work.
- Microsoft Agent Framework / Foundry: production multi-agent orchestration, hosted agents, skills, memory, middleware and A2A/MCP interoperability.
- Amazon Bedrock AgentCore: separable runtime, memory, gateway, browser, code interpreter, identity, policy, observability and evaluations.
- GitHub Copilot agent stack: custom agents, reusable agent skills, MCP, isolated sub-agents and parallel fleet patterns.
- MCP 2026-07-28: stateless scale, cacheable capability catalogs, hardened authorization and long-running Tasks extension.
- Google ADK/A2A: cross-language agent interoperability and protocol-based collaboration.
- LangGraph: checkpointed durable execution, persistence, interrupts, replay/fork and fault-tolerant continuation.
- CrewAI: workflow-to-agent production composition and connector-rich orchestration.
- Anthropic/Claude agent patterns: longer-horizon coding, research, document work, multitasking and self-review.

## 4. Target architecture: one Bubbles identity, many bounded specialists

Bubbles should not become one giant monolithic agent. The owner experiences **one coherent Bubbles identity**, while bounded specialist capabilities operate below it.

### Layer A — Owner / identity model

Bubbles owns the owner-facing mission contract, explicit preferences, creative-focus policy, completion semantics and escalation boundary.

### Layer B — Mission compiler

Reuse Formation Omega / MissionIR to convert intent into dependency-aware work and proof requirements. Do not create a second mission scheduler.

### Layer C — Capability discovery and interoperability

Reuse the Federation capability registry and Bridge. Extend toward late-bound MCP/A2A/skill discovery so tools and specialists are selected dynamically rather than hardcoded into every workflow.

### Layer D — Specialist fleet

Compose the existing Bubbles specialist roles, independent assurance systems and provider executors into scoped sub-agents. Each specialist gets its own context, tools and effect boundary. CFBE/Bubbles choose the route; provider authority remains local to the executor.

### Layer E — Memory fabric

Use hot/warm/cold memory, KDV/Bible Fabric, mission checkpoints, episodic mission memory, semantic knowledge memory and explicit preference memory. Add consolidation and selective archival so Bubbles remembers useful durable state without loading all history into every conversation.

### Layer F — High-performance execution fabric

Reuse durable checkpoints, idempotency, lane isolation, parallel waves, failure-domain placement, deterministic caching, shadow/canary, rollback and replay. Extend finite-WIP, backpressure, admission and capacity controls rather than adding another scheduler.

### Layer G — Proof and assurance

ProofOS, TruthGrid, EvidenceOps, Sentinel, Jarvis, Airlock and CFBE stay logically independent. Bubbles consumes their verdicts; it does not self-certify its own success.

### Layer H — Self-improvement foundry

Reuse CFBE Capability Foundry, Opportunity Radar, Failure Genome, champion-challenger experiments and Capability Mortality. New capabilities must beat the incumbent under proof/regression/value gates or be held/retired.

### Layer I — Creative Focus Shield

`federation/bubbles_autopilot_policy.py` provides the first deterministic owner-interruption policy. It reduces routine prompts without inventing authority.

## 5. Autonomy contract

### A0 — NO_EFFECT

Research, analysis, planning, benchmarking, read-only retrieval, simulation and deterministic internal transformation continue automatically when the mission is clear.

### A1 — REVERSIBLE_INTERNAL

Source branches, test fixtures, reversible internal artifacts and bounded internal state changes continue automatically within existing authority and proof rules.

### A2 — REVERSIBLE_EXTERNAL

External actions may continue without another owner prompt **only when pre-existing authority and provider-native readback are both proven for that exact route/effect**.

### A3 — HIGH_CONSEQUENCE / IRREDUCIBLE OWNER CHOICE

Irreversible, high-consequence, legal/financial/identity-sensitive decisions or genuine creative/final-owner choices interrupt the owner.

## 6. Continuous-completion behavior

When the owner gives a clear mission or a continuation directive, Bubbles should:

1. recover the latest verified mission/capability state;
2. run the Already-Solved gate;
3. reuse/extend/compose before new build;
4. decompose through MissionIR;
5. allocate through the existing CFBE/Bubbles execution fabric;
6. continue all safe executable lanes without routine owner prompts;
7. isolate and reroute blocked lanes when a verified alternate exists;
8. test and independently verify candidate outputs;
9. retry/recover within bounded policy;
10. stop only at verified completion, an irreducible authority gate, an irreducible owner choice, or a genuinely impossible route;
11. report terminal state, proof and remaining provider/value gates.

This is a control policy for active execution surfaces. It does not imply hidden work continues after the active runtime ends. Durable continuation must be supplied by an actual scheduler/runtime/provider route and proven separately.

## 7. Digital-twin maturity ladder

- DT0 — Assistant: responds to direct prompts.
- DT1 — Orchestrator: decomposes, routes, verifies and reroutes work.
- DT2 — Persistent Operator: durable mission state, memory, continuation and bounded tool execution.
- DT3 — Anticipatory Operator: predicts needs, monitors relevant state and prepares next-best work with low owner burden.
- DT4 — Governed Digital Twin: stable owner/preference model, general cross-domain capability, autonomous safe execution, independent assurance and provider-bound actions under delegated authority.
- DT5 — Empirically Proven Digital Twin: sustained real-world evidence that owner intervention, cycle time and failure recurrence fall while accepted outcome quality/value rises.

Current source architecture contains material DT1/DT2 components and protocols for later stages. DT3–DT5 require real memory/provider/outcome evidence; source code alone cannot promote them.

## 8. Preferred convergence waves

### Wave 0 — Consolidate what already exists

Bind MissionIR, capability registry, durable ledger, ProofOS, CFBE, Failure-Win, Multi-Model Exchange, Opportunity Radar and Capability Foundry under one Bubbles mission contract. Retire duplicate controllers.

### Wave 1 — Owner-burden control

Promote the Creative Focus Shield after source/test proof. Instrument owner-intervention count/time and clarification count.

### Wave 2 — Specialist/skill fabric

Compose reusable skills, scoped custom agents, isolated sub-agents, critic/verifier roles and MCP/A2A interoperability. Keep effect authority explicit per specialist.

### Wave 3 — High-performance closure

Implement finite WIP, capacity-aware wave placement, backpressure, admission control and capacity forecasting on top of the existing scheduler; do not replace it.

### Wave 4 — Memory and twin-state closure

Build durable preference/episodic/semantic memory, consolidation, forgetting and multi-snapshot digital-twin state. Prove freshness and provenance.

### Wave 5 — Anticipation and self-improvement

Feed real mission outcomes into intent prediction, opportunity radar, causal world model, Capability Foundry, champion-challenger and mortality loops.

### Wave 6 — Provider-bound autonomy

Use sandbox/browser/computer/identity/triggered execution only through provider-specific authorization, readback, rollback and observability.

### Wave 7 — Value proof

Measure accepted outcomes, owner intervention minutes, cycle time, reliability, cost and recurrence. Digital-twin maturity advances only from sustained empirical improvement.

## 9. Completion criterion

The convergence is not complete merely because 150 capabilities are catalogued. Completion requires the execution fabric to show, across real missions, that Bubbles can take a clear objective, continue safe work with minimal owner interruption, recover/reroute, build and verify solutions, preserve authority boundaries, and measurably return creative/strategic time to the owner.
