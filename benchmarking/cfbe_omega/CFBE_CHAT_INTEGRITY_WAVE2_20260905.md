# CFBE Ω — Chat Integrity Frontier Wave 2 — 5 September 2026

Status: SOURCE CANDIDATE. CI/admission, provider/runtime enforcement and measured owner-value improvement remain separate proof gates.

## Mission

Audit the active ChatGPT/Federation workstream against current frontier agent engineering and harvest the highest-value mechanisms that reduce misleading maturity claims, premature mission termination, repeated owner debugging and recovery noise.

## Current estate baseline

Current main already contains the first remediation tranche:

- deterministic `PRE_FINAL_RESPONSE` Stop gate;
- mission terminal-state contract;
- claim-versus-proof scan adapter;
- mandatory-control binding coverage;
- durable decision checkpointing/metrics;
- Human-First Outcome-First recovery;
- RealityGuard/ChatBridge/ChatGov composition.

That closes the largest enforcement-placement defect for hosts that actually route through ChatGov, but leaves four material frontier gaps:

1. **TOCTOU final-output gap** — a candidate can be changed after approval unless the emitter binds the exact approved response and mission state.
2. **Observed-failure learning gap** — blocked real failures are not yet automatically normalized into reusable regression fixtures.
3. **Trace interoperability gap** — decision telemetry is durable internally but not yet normalized for external OpenTelemetry-style collection.
4. **Host bypass gap** — native or external hosts that do not route through ChatGov can still bypass these controls; source cannot truthfully claim universal enforcement.

## Frontier benchmark mechanisms harvested

### OpenAI Agents SDK

Current public SDK docs expose final-output guardrails, tool guardrails, resumable `RunState`, persistent sessions and tracing across agent/tool/handoff/guardrail events.

Harvested mechanisms:
- final-output validation at workflow boundary;
- fail-closed resume provenance;
- traceable guardrail decisions;
- serialized run-state continuity.

### Anthropic Claude Code

Current public hooks architecture exposes deterministic lifecycle enforcement around stopping/task completion.

Harvested mechanism:
- stopping is a policy decision, not merely model prose.

### Microsoft AutoGen

Termination is modeled as a stateful composable `TerminationCondition`.

Harvested mechanism:
- typed, resettable, composable terminal-state contracts.

### LangGraph

Persistence/checkpointing, interrupts, pending-write preservation and fault-tolerant resume are first-class. Side effects before interrupts are expected to be idempotent.

Harvested mechanisms:
- checkpointed interruption/resume;
- do not rerun already-completed work after failure;
- idempotent side-effect discipline.

### Temporal

Durable workflows survive process/network/infrastructure failure and resume from persisted history.

Harvested mechanism:
- mission lifetime must be independent of a single chat turn/process lifetime.

### Open Policy Agent

OPA separates Policy Decision Point from Policy Enforcement Point, recommends placing policy close to enforcement, issues decision IDs and supports decision logs/OpenTelemetry.

Harvested mechanisms:
- exact enforcement-point binding;
- deterministic decision identity;
- auditable policy-decision telemetry;
- prevent time-of-check/time-of-use drift between policy approval and effect/emission.

### Google ADK / Agents CLI

Current public tooling emphasizes structured evaluation, trace grading, iterative eval/fix cycles, deployment and production observability.

Harvested mechanism:
- every material behavior change needs a repeatable eval dataset, not only one-off tests.

### W&B Weave / Braintrust

Current agent-eval guidance evaluates whole trajectories/tool usage, not merely final strings, and production failures can seed ongoing regression datasets.

Harvested mechanism:
- observed failure -> structured replay case -> recurring release gate.

### MCP 2026-07 / A2A v1.0

Current MCP adds hardened authorization/task semantics and cache metadata; A2A v1.0 provides vendor-neutral agent discovery/delegation contracts.

Harvested mechanisms:
- capability contracts should remain transport/provider neutral;
- authorization provenance must survive delegation;
- agent-to-agent delegation must not erase mission/authority state.

### OpenTelemetry GenAI semantic conventions

Current conventions standardize trace attributes across LLM generations/tool calls and allow correlation through distributed traces.

Harvested mechanism:
- ChatGov decision/permit events should emit vendor-neutral trace attributes when a collector is present.

## Wave-2 implementation

### 1. Exact Final-Response Emission Permit

New module: `bubbles/chat_governor_omega3/emission_permit.py`

A final response permit is minted only after `PreFinalGate` allows emission. It binds:

- mission id;
- pre-final decision id;
- exact candidate-response SHA-256;
- exact mission-state SHA-256;
- policy version;
- terminal mode.

If the candidate response, mission state, decision or terminal mode changes after approval, validation fails closed and a fresh pre-final evaluation is required.

This closes the TOCTOU gap between policy decision and actual response emission for routed hosts.

### 2. Failure-to-Regression Compiler

New module: `bubbles/chat_governor_omega3/failure_regression.py`

Observed pre-final failures compile into deterministic replay records. Initial mappings include:

- F19 known-actionable-gap premature termination;
- F20 source/runtime or claim-proof conflation;
- F22 orphan mandatory control enforcement;
- F23 problem reported before available recovery;
- F24 maturity claim without claim-proof scan.

The record preserves mission/candidate hashes and expected pre-final behavior, allowing future CI/eval systems to replay the exact failure class.

### 3. OpenTelemetry-friendly decision attributes

The emission permit provides a vendor-neutral attribute map for decision/permit telemetry. This is an adapter only; no external collector/exporter is claimed.

## Updated CFBE score estimate

This remains an architectural heuristic, not an external certification.

| Dimension | Pre-remediation | Current source candidate | Rationale |
|---|---:|---:|---|
| Mission completion / termination integrity | 42 | 84 | Pre-final Stop gate + typed terminal states + actionable-gap block. |
| Claim integrity / maturity truth | 48 | 86 | Claim-proof scan + maturity-word tripwire + exact response permit. |
| Outcome-first recovery | 74 | 86 | Solve-before-report admitted; real internal recovery pattern demonstrated. |
| Proof/readback discipline | 88 | 91 | Existing exact-head/provider readback plus permit binding. |
| Durable continuity / resume | 80 | 84 | Durable checkpoints strong; universal durable runtime still unproved. |
| Policy enforcement placement | 45 | 88 | Explicit PRE_FINAL_RESPONSE PEP plus permit boundary for routed hosts. |
| Observability / eval feedback | 63 | 80 | Decision metrics + failure-to-regression compiler + telemetry schema. |
| Human burden / creator-time protection | 58 | 79 | Outcome-first + auto-continue + fewer invalid terminal/problem reports; measured improvement still pending. |
| Recovery / resilience | 81 | 86 | Strong retry/reroute/concurrency recovery; long-lived durable workflow integration still optional/unproved. |
| Interoperability / composability | 70 | 79 | Provider-neutral contracts; MCP/A2A universal binding remains unproved. |

**Weighted source-candidate estimate: ~84/100**, up from the prior 61/100 architecture before the enforcement remediation.

Do not promote this score to empirical user-value performance until prospective cohorts show lower owner debugging, fewer misleading completion claims and fewer premature terminal responses.

## Next highest-value frontier wave

1. Bind the emission permit to every ChatGov-routed response emitter and reject permitless emission.
2. Persist permit validation events into the existing durable state and trace plane.
3. Auto-export observed failure regressions into the repository eval dataset used by CI.
4. Add bounded recovery budgets/circuit-state so Solve-Before-Report cannot become an infinite hidden loop.
5. Add fresh-process restore/replay tests proving checkpoint + permit + claim-proof state survive restart.
6. Add MCP/A2A envelope propagation for mission id, authority reference, proof state and trace correlation.
7. Run prospective owner-value cohorts: misleading-status rate, premature-termination rate, owner-debug minutes, prompts-per-mission, solved-before-escalation rate.

## Proof boundary

This wave does not claim:

- native ChatGPT response emission is mechanically controlled;
- every provider/agent host validates emission permits;
- external OpenTelemetry, OPA, Temporal, Braintrust, Weave, LangGraph, ADK, AutoGen or Claude runtimes are installed or bound;
- universal cross-chat/cross-provider enforcement;
- measured human-value superiority.

Those require separate runtime and empirical proof.
