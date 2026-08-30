# Omega-One v0.8.5 — Maturity + Interoperability Candidate

Status: PREPARED / NON-EFFECT / BRANCH-ONLY

Purpose:
- compile heterogeneous capability evidence into the highest contiguous fully proven maturity state;
- preserve detached later-stage evidence without allowing semantic proof-state promotion;
- prevent design/source/test/deployment/provider/value promotion collapse;
- project Omega-One Universal Capability Contracts into current MCP, A2A and OpenTelemetry-compatible shapes without transferring authority;
- preserve Omega-One as the semantic superset when external standards expose only a portable subset;
- keep all external effects subject to SOVARA and independent proof.

## Zero-Dilution Interoperability Invariant

External compatibility is additive. It is never authority to weaken Omega-One.

The exact internal UCC remains the source of truth and is hash-bound inside each interoperability bundle. MCP, A2A, OpenTelemetry or any later standard receives a standards-compatible projection, while Omega-One-only metadata, creative controls, proof semantics, authority boundaries, privacy classifications, rollback requirements and future extension state remain preserved internally.

Therefore:

`FULL OMEGA-ONE CONTRACT -> PORTABLE PROJECTION -> EXTERNAL STANDARD`

never:

`FULL OMEGA-ONE CONTRACT -> FLATTEN TO LOWEST COMMON DENOMINATOR`.

No source, code, creative capability, test, dormant function, lineage or richer semantic field may be removed merely to fit an external standard. A target incapable of representing a field receives the portable subset and the full field remains in the source UCC / Omega-One genome.

Current target standards:
- MCP 2026-07-28 stateless request model, per-request client metadata and routable headers;
- A2A 1.0 Agent Card capability discovery and declared protocol extensions;
- OpenTelemetry Semantic Conventions 1.44-era GenAI/tool operation tracing.

Standards corrections captured during candidate development:
- A2A Omega governance metadata belongs in an AgentCapabilities extension declaration rather than an invented AgentSkill field.
- A2A runtime-interface proof is separate from generation of an Agent Card template.
- OpenTelemetry uses the recognised `execute_tool` GenAI operation value for the projected tool execution span.
- MCP projection carries the 2026-07-28 routing headers and per-request client metadata without creating a provider session or execution authority.

Truth boundary:
This branch does not claim that all 100 Omega-One capabilities are deployed or provider-verified. The supplied v0.8.4 blueprint defines all 100 capabilities, while the Startup Register contains mixed maturity states including a static 100-candidate registry and a staged 100-improvement package. The maturity compiler is intended to make that distinction machine-enforceable while retaining all available evidence.

No provider call, credential use, production deployment, external communication or main-branch promotion is created by this candidate.
