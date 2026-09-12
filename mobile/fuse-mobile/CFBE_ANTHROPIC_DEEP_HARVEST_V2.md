# CFBE Anthropic Deep Harvest v2 — 100-Gene Integration Map

Date: 2026-09-12
Scope: public Anthropic engineering/product patterns translated into provider-neutral FUSE Mobile/Federation mechanisms. This work does not copy Anthropic proprietary source code, hidden prompts, model weights, private routing, or non-public infrastructure.

## Result

The Anthropic-specific harvest now contains exactly 100 capability genes:

- `ANTH-001..042` — multi-agent research, dynamic tools, progressive skills, context compaction, prompt-injection screening, action-risk gates, containment, checkpoints, device descriptors and outcome truth.
- `ANTH-043..072` — advisor/executor delegation, adaptive effort, execution locus routing, context-pressure composition, memory trust/versioning, agent-definition versioning, bounded outcome loops, self-hosted execution, brain/hand separation, two-stage approval screening, research fitness/rubrics/citation audit, token budgets, harness simplification, infrastructure-noise courts, code-shard ownership, device recovery and incident-to-eval compilation.
- `ANTH-073..100` — model-agnostic hardware manifests, natural-language device safety metadata, MCP/CLI/API hardware convergence, closed-loop write/readback, deterministic learned routines, asynchronous mission recovery, progress heartbeats, self-tests, vision validation gates, root-cause repair, cache economics, pending-event hydration, execution-hand health, approval-fatigue telemetry, operator-aware containment, credential provenance, typed return inspection, reproducible eval environments, real-task seed sets, multi-grader courts and continuous provider qualification.

## What was newly harvested from Anthropic's public 2026 work

### Long-running autonomy

FUSE adopts a durable mission-state contract instead of assuming a single model context remains alive. Objective, evidence cursor, checkpoint, attempts and progress heartbeat are separable from the reasoning worker. The reasoning worker may be replaced while the mission remains intact.

### Brain / hands decoupling

Execution environments are modeled as replaceable hands. Reasoning workers can remain stateless; hands can be provisioned lazily, health-checked, replaced and eventually transferred between qualified brains. This supports lower time-to-first-token and reduces the blast radius of a single failed execution environment, while preserving FUSE authority ceilings.

### Approval fatigue → bounded autonomy

Repeated human approvals are not treated as safety by themselves. FUSE keeps hard containment as the primary boundary, then uses a fast action screen for low-risk operations and escalates ambiguous/high-risk actions to deeper review. The approval classifier is deliberately anchored on user intent and requested effects, not on the agent's own persuasive explanation.

### Containment-first security

Secrets should be absent from the sandbox where possible. Filesystem/network access is bounded. Egress credentials are short-lived, environment-bound and destination-bound. External tool results are typed by source and inspected before entering model context. FUSE prefers mature operating-system/container isolation primitives over custom security code unless a custom component is necessary and reviewed.

### Context and tool economics

Tool discovery, deferred schemas, code/programmatic tool orchestration, cache reuse, stale-result clearing, memory offload and compaction solve different bottlenecks. They are composed according to measured context pressure rather than switched on globally.

### Research economics and quality

Multi-agent fanout is gated by task value, parallelizability, context breadth, dependency coupling and cost pressure. Research output is judged across factual accuracy, citation accuracy, completeness, source quality and tool efficiency. Citation auditing is a separate concern rather than assumed from fluent synthesis.

### Physical AI / hardware interoperability

FUSE adopts the public Model Hardware Standard design direction as a provider-neutral device layer: discoverable hardware manifests, simple read/write commands, natural-language safety metadata, model-agnostic protocols, write/readback loops, driver-level limits, parallel-device planning and deterministic scripts for stable repeated routines. Physical writes remain proof- and authority-gated.

### Evaluation rigor

Agentic benchmark results are not trusted without environment metadata. CPU, RAM, timeout, concurrency, egress profile and run window are first-class evidence. Challenger gains must clear both practical-value floors and observed infrastructure noise. FUSE can begin with a small representative real-work task set and expand once the harness stabilizes.

### Provider evolution

Model upgrades are challengers, not automatic promotions. Quality, cost, latency and safety are normalized against the incumbent. Provider/model deprecation becomes a migration trigger rather than an outage surprise.

## Source-level implementation map

Implemented source primitives now include:

- dynamic tool discovery and deferred schemas;
- progressive skill loading;
- untrusted-context screening;
- bounded research fanout;
- context compaction and context-pressure planning;
- model-lane, advisor and effort selection;
- action-risk and two-stage approval gates;
- memory trust planning and immutable versioning;
- versioned agent definitions;
- containment profile selection;
- mission checkpoints and async mission recovery;
- research suitability, rubric scoring and citation-audit planning;
- tool-result budgeting;
- harness-simplification and infra-noise decisions;
- parallel code-shard ownership checks;
- device capability manifests, safety envelopes, write/readback loops and recovery decisions;
- self-test plans and visual-verification requirements;
- approval-fatigue measurement;
- credential provenance checks;
- typed external-return inspection;
- eval-environment normalization;
- multi-grader outcome aggregation;
- incident-to-regression conversion;
- provider lifecycle decisions.

## Proof boundary

`SOURCE_IMPLEMENTED` means the mechanism exists in source and is covered by deterministic source/compile tests where available. It does not mean a hosted runtime or external provider has demonstrated the behavior.

`RUNTIME_GATED` requires live execution/readback evidence.

`PROVIDER_GATED` requires a real provider/device capability and observed outcome.

`REUSE_VERIFIED` is reserved for a FUSE primitive that already has evidence elsewhere in the estate and should be reused rather than duplicated.

No maturity label can advance from prose, design intent or file existence alone.

## Next empirical courts

1. Context/tool court: measure tool-definition tokens, tool-result tokens, latency, quality and missed tool calls with and without discovery/deferred schemas/programmatic orchestration.
2. Long-horizon court: interrupt a real mission, restart the reasoning process and prove recovery from durable state without losing objective/evidence.
3. Safety court: seed prompt injections into web/file/shell/connector returns; measure detection, false positives and blocked unsafe effects.
4. Approval-friction court: compare manual prompts with containment + two-stage gate while measuring unsafe misses and owner prompts.
5. Research court: single-agent vs bounded multi-agent on representative FUSE research tasks; measure factuality, citation accuracy, coverage, source quality, tool efficiency and total cost.
6. Physical/device court: use the FUSE baseline phone/emulator first; prove discover/read/write/readback/recovery with privacy-minimised device characteristics and no personal-content cloning.
7. Provider court: compare incumbent and challenger models under identical resource envelopes across quality, latency, cost, recovery and safety.

## Bottom line

The useful Anthropic lesson is not a brand-specific clone. It is an architecture where autonomy rises because context, execution, containment, evaluation and recovery are engineered as separate systems. FUSE keeps sovereignty over authority, proof and memory while treating every model—including Anthropic models—as replaceable cognition behind stable provider-neutral contracts.
