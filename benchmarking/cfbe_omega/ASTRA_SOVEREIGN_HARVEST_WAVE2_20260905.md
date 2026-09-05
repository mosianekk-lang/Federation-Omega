# CFBE Ω — Astra / Work Sovereign Harvest Wave 2 — 5 September 2026

Status: SOURCE CANDIDATE until exact-head admission.

This receipt supersedes the implementation-state column of the Wave-1 harvest where later source in the same tranche has moved an item forward. It does not supersede Wave-1's truth boundary.

## Newly implemented source mechanisms

- **ASTRA-G04 / Programmatic Tool Calling:** `federation_sovereign_runtime.tool_micro_runtime.DeterministicDataRuntime` now provides narrow, effect-free filter, project, sort, dedup and aggregate-count operations with deterministic SHA-256 receipts. It is intended for mechanical work that should not consume frontier-model reasoning.
- **ASTRA-G06 / Persisted reasoning:** `federation_sovereign_runtime.reasoning_capsule.ReasoningCapsule` preserves conclusions, assumptions, evidence refs, unresolved questions, rejected routes and next action with hash-linked lineage. It is explicitly *not* a private chain-of-thought store; evidence refs are never silently removed by capsule compaction.
- **ChatGPT Work harness harvest:** `federation_sovereign_runtime.work_profile` captures ten public harness genes covering long deliverables, remote cloud browser execution, continuation after device exit, user-boundary pauses, scheduled/event-triggered work, connected resources, project context, progress steering, finished artifacts and desktop computer use. These are public mechanism mappings, not claims that the Federation currently controls ChatGPT Work.
- **Package composition:** `federation_sovereign_runtime.__init__` exports the new reasoning, deterministic-data and Work-profile primitives.
- **Governance v1.1:** the canonical source candidate now records Astra and Work mechanism genes together while keeping Human-First, Forest-First, SLOS, SOVARA, RealityGuard/TruthGrid/JFRIE and KDV/ChatBridge sovereignty separate.

## Why this is more sovereign than provider imitation

The Federation preserves decision-relevant reasoning continuity in its own schema rather than requiring a vendor's hidden reasoning state. It also moves deterministic transforms out of the model loop, reducing dependency on any one model's token budget, context management or tool-calling behavior. Provider models remain eligible processors in a measured market.

## Remaining empirical gates

Exact-head CI/admission comes first. Then fresh-process capsule replay, async independent-lane behavior, steering replay, context-loss courts, blind multi-processor cohorts and provider-native remote/computer execution need separate proof. Neither Astra API execution nor ChatGPT Work cloud-browser control is asserted by this source tranche.
