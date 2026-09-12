# CFBE Anthropic Deep Harvest v1 — FUSE Mobile / Federation Omega

Date: 2026-09-12
Scope: public Anthropic product/engineering patterns translated into original FUSE mechanisms. No Anthropic proprietary code, prompts, model weights, private internals, or brand-dependent runtime assumptions are copied.

## Why this harvest matters

The September-2026 Federation benchmark already shows strong architecture breadth but lower proof density in model routing, hosted durable runtime, identity/action readback, enterprise UX, standardized telemetry, and physical/edge AI. Anthropic's public engineering work is unusually relevant because it exposes concrete production patterns for long-running agents, multi-agent research, tool ergonomics, context management, permission automation, containment, and device interoperability.

FUSE should not clone Claude. The leverage is to absorb the public mechanisms that improve autonomy and reliability, then combine them with FUSE's stronger proof, authority, provenance, and fail-closed controls.

## Public capability families harvested

1. Multi-agent research with lead-agent planning, parallel specialist workers and a separate citation pass.
2. Long-running managed agents with context stored outside the model and selectively rehydrated.
3. Planner / generator / evaluator harnesses for multi-hour application work.
4. Parallel agent teams operating over a shared codebase with tests as the steering mechanism.
5. Dynamic tool discovery and deferred tool schema loading.
6. Programmatic tool calling and MCP-backed code execution to reduce context overhead.
7. Agent Skills with metadata-first progressive disclosure and executable helper resources.
8. Tool ergonomics: clear namespaces, high-signal results and eval-driven tool improvement.
9. Auto-mode style action screening with a cheap fast path and deeper review only when risk signals fire.
10. Pre-context inspection of untrusted tool/network returns for prompt-injection signals.
11. Filesystem and network containment so autonomy can rise without unconstrained blast radius.
12. Separation of the reasoning brain from the execution hands so policy enforcement does not depend on the model's own judgment.
13. Outcome-based agent evaluation: the environment state wins over what the agent claims happened.
14. Context compaction, plan persistence and durable mission checkpoints.
15. Model-tier specialization for cost/latency/quality matching.
16. Model Hardware Standard ideas: discoverable device capabilities, simple command semantics, natural-language safety metadata and model-agnostic interoperability.
17. Threat-intelligence feedback loops that convert real incidents into regression tests and policy improvements.
18. Persistent-memory poisoning defenses and live inspection of data before it reaches future sessions.

## FUSE advantage after synthesis

Anthropic's public patterns are strongest at making agents useful over longer horizons. FUSE's existing advantage is stricter authority/proof separation. The combined target is therefore:

`high autonomy + low context waste + bounded blast radius + durable recovery + independent outcome proof`.

This avoids the two common failure modes: agents that are powerful but over-permissioned, and governed systems that are safe but too manual to be useful.

## 42 harvested improvement genes

The executable registry lives in `src/anthropicCfbe.ts` as `ANTHROPIC_CFBE_GENOME`. Each gene has an owner, priority, proof-scoped maturity state and acceptance condition.

Priority-zero source implementations in the mobile/Federation-facing layer include:

- query-ranked dynamic tool discovery;
- deferred schemas;
- progressive skill selection;
- untrusted-context screening;
- two-stage action-risk classification;
- context compaction that preserves pinned plans;
- bounded research fanout;
- risk/value/latency model-lane selection;
- deterministic mission checkpoints;
- observed-outcome evaluation;
- device capability descriptors;
- subagent authority ceilings and blast-radius caps.

The remaining genes are deliberately marked `REUSE_VERIFIED`, `RUNTIME_GATED`, or `PROVIDER_GATED` where source alone cannot prove a live provider/runtime outcome.

## Competitive delta against the current Federation benchmark

### Already strong / reuse instead of duplicate

- MCP surfaces and remote adapters already exist.
- ProofOS/Airlock and authority ceilings already outperform simple permission prompts.
- Prompt-injection handling already exists in security and EvidenceOps paths.
- Governance/provenance/auditability are already a top Federation dimension.
- Multi-agent and durable-workflow architecture already exists at source level.

### Material Anthropic-derived gaps closed at source level here

- a single mobile-facing dynamic-tool discovery contract;
- progressive skill selection contract;
- explicit context compactor for long missions;
- deterministic fast-path vs approval-path action classifier;
- provider-neutral model-lane chooser;
- provider-neutral research fanout budgeter;
- mobile/device capability manifest inspired by hardware-interoperability standards;
- outcome-state verifier that treats observed state as authoritative;
- checkpoint digest and subagent capability ceiling helpers.

### Still requires empirical/provider proof

- real hosted durable session recovery after process loss;
- real programmatic MCP tool execution with token/cost measurements;
- real provider model routing cohorts across the same task set;
- real mobile/physical device command and readback pairs;
- production prompt-injection classifier recall/false-positive measurements;
- real owner-burden reduction from auto-mode style gating;
- live memory-poisoning and tool-return containment tests;
- sustained cost/value proof for multi-agent fanout.

## Acceptance doctrine

No gene may be promoted merely because a file exists. A source helper is `SOURCE_IMPLEMENTED`; runtime recovery is `RUNTIME_GATED`; external-device/provider outcomes remain `PROVIDER_GATED`; existing admitted mechanisms may be `REUSE_VERIFIED` only when there is already evidence for them.

The next high-value court should compare the new context/tool/permission primitives against the current FUSE baseline on real Mobile missions. Measure wall-clock time, tool-definition tokens, tool-result tokens, owner approvals, unsafe action blocks, missed required actions, recovery after interruption, and final observed outcome quality.
