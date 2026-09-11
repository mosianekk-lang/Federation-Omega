# FUSE Anthropic Deep Harvest v0.2 — Provider-Neutral Capability Genome

This source slice extends the prior Anthropic public-source harvest without copying proprietary weights, training data, hidden prompts, private routing, hidden classifiers or non-public infrastructure. The objective is clean-room functional transfer into FUSE semantic primitives.

## Public mechanisms harvested in this tranche

1. **Advisor/executor separation** — a lower-cost executor may consult a stronger advisor selectively, with bounded uses and independent cost/caching controls.
2. **Adaptive effort** — cognition depth is treated as a runtime policy over low/medium/high/xhigh/max effort rather than a fixed model identity.
3. **Tool execution locus** — client-executed, provider/server-executed and self-hosted tool execution are distinct trust/data-boundary choices.
4. **Browser vs computer toolsets** — page-aware browser actions and full-desktop actions are different execution surfaces and should be selected by task semantics.
5. **Context-pressure composition** — tool search, programmatic tool calling, prompt caching, context editing, compaction and memory offload solve different context-pressure causes and can be combined.
6. **Persistent memory trust zones** — durable memory supports read-only/read-write access, immutable versions and separate stores; untrusted-input sessions should not automatically receive writable shared memory.
7. **Versioned reusable agent definitions** — model/tools/skills are a versioned agent resource; optimistic concurrency prevents silent overwrite.
8. **Outcome-evaluation loops** — an agent outcome is not complete because the agent says so; explicit evaluation can require revision, terminate, or hit a bounded iteration ceiling.
9. **Self-hosted execution boundary** — sensitive/internal-network tool execution may stay in infrastructure controlled by the owner while cognition remains replaceable.

## Existing FUSE capabilities reused instead of duplicated

- `TOOL.DYNAMIC_DISCOVERY` for deferred tool search.
- `TOOL.PROGRAMMATIC_ORCHESTRATION` for deterministic multi-tool fan-out/filtering.
- `SKILL.PROGRESSIVE_DISCLOSURE` for filesystem skill packages.
- `SEC.CONTAINMENT_COMPILER` for filesystem/network blast-radius controls.
- `AGENT.HARNESS_MINIMIZER`, `CONTEXT.ARTIFACT_HANDOFF`, `REASON.REFLECTION_GATE`, `CK.MODEL`, `CK.TOOL`, `CK.EXEC`, `CK.STATE`, `CK.POLICY`, `CK.PROOF`.

## New provider-neutral semantic candidates

- `REASON.ADVISOR_DELEGATION`
- `REASON.EFFORT_CONTROL`
- `TOOL.EXECUTION_LOCUS`
- `CONTEXT.PRESSURE_CONTROLLER`
- `CONTEXT.MEMORY_TRUST_ZONES`
- `AGENT.RESOURCE_VERSIONING`
- `AGENT.OUTCOME_EVALUATION`
- `EXEC.SELF_HOSTED_SANDBOX`
- `EXEC.BROWSER_COMPUTER_ROUTER`

## Truth boundary

Local v0.2 reference code passed 15/15 deterministic tests before repository admission. These tests prove only the provider-neutral control mechanics in this package. They do not prove live Claude/Anthropic API access, Managed Agents deployment, provider advisor execution, browser/computer runtime behavior, memory-store persistence, or parity with any Claude model.

FUSE remains the mission, authority, proof and learning layer. Anthropic/Claude is a qualified cognition/tooling provider, not a sovereign controller.