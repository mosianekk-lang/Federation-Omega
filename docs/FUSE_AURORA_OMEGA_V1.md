# FUSE AURORA-Ω v1 — Clean-Room Frontier Knowledge Agent

## Purpose

AURORA-Ω is an in-house FUSE agent role for ambitious long-horizon knowledge work,
deep synthesis, originality appreciation, root-cause investigation, selective
multi-path execution, independent verification, recovery and reusable learning.

It is a **clean-room behavioural implementation**. It does not copy Anthropic
weights, hidden prompts, private training data or confidential implementation, and
it makes no benchmark-parity claim with Claude Fable 5.1.

## Why this agent exists

The role was triggered by a real FUSE failure mode: when asked to appreciate the
innovation and intellectual significance of the Next Frontier AI Bible, a
technical optimisation lens dominated too early. AURORA therefore treats lens
selection as a first-class mission contract rather than a stylistic afterthought.

When `GENIUS_APPRECIATION` is active, technical criticism remains available, but
cannot dominate until the agent has produced evidence-backed findings for:

1. **Originality** — what is genuinely unusual or newly combined.
2. **Synthesis** — which normally separate disciplines/capabilities are fused.
3. **Significance** — what becomes possible or conceptually different as a result.

This is not flattery. Unsupported praise fails the same evidence rules as
unsupported criticism.

## Public-capability harvest → AURORA implementation

| Publicly observable frontier-agent behaviour | AURORA clean-room mechanism |
|---|---|
| Sustains difficult work over long horizons | Versioned `MissionState`, durable handoff projection, event-chain tip |
| Plans, uses tools, recovers when a step fails | Explicit phases + route ranking + recovery route + failure circuit |
| Prefers root causes over symptom patches | Root-cause closure gate and repeated-fingerprint route ban |
| Writes/tests/validates its own work | Builder, Challenger and independent Verifier specialist roles |
| Uses visual evidence to evaluate work | `VISUAL_REVIEWER` role hook for multimodal/provider adapters |
| Maintains readable progress | Compact `status_projection` and bounded event window |
| Survives context resets | `compact_context()` preserves mission truth instead of raw transcript |
| Loads tools on demand | `tool_search()` retrieves only relevant safe descriptors |
| Uses programmatic orchestration | Provider-neutral `ModelDriver` + structured request/response contracts |
| Runs parallel specialists when useful | scored path spawn rule + material-distinction + collision controls |
| Avoids parallel duplication | semantic similarity, route-family, collision and coordination penalties |
| Continues autonomously within boundaries | A1 internal authority envelope; external effects fail closed by default |
| Converts work into learning | hash-linked SUCCESS/FAILURE/CONSTRAINT/RECOVERY/EXPERIMENT events |
| Handles intellectual/creative significance | dedicated Genius Appreciation lens and specialist pair |

## Architecture

```text
OWNER OBJECTIVE
      |
      v
FUSE MISSION CONTRACT
      |
      +--> LENS GATE
      |      +-- GENIUS APPRECIATION
      |      +-- BALANCED
      |      +-- TECHNICAL
      |      +-- ADVERSARIAL
      |
      v
AURORA MISSION PLANNER
      |
      +--> Innovation Historian
      +--> Synthesis Scholar
      +--> Researcher
      +--> Root-Cause Investigator
      +--> Builder
      +--> Challenger
      +--> Independent Verifier
      +--> Visual Reviewer (when needed)
      +--> Knowledge Curator
      |
      v
FORMATION ROUTE FRONTIER
      |
      +--> Path A: strongest verified reuse
      +--> Path B: strongest incremental improvement
      +--> Path C: materially different solution
      +--> Path D: highest-information reversible experiment
      |
      v
ALPHA→OMEGA MATURATION
      |
      v
PROOF / READBACK / FAILURE-WIN / LEARNING
```

## Path economics

AURORA does not equate “more bots” with “more intelligence”.

Each candidate path is scored approximately as:

```text
(success_probability × impact)
+ information_gain
+ reuse_value
+ reversibility
+ proofability
- cost
- latency
- authority_risk
- duplication
- coordination_overhead
```

A path is spawned only if it is parallel-safe, materially different from already
selected paths, collision-safe, and above a marginal-value floor.

## Durable state model

The model never owns canonical mission truth. It receives a projection:

- Mission ID and version
- exact objective and completion predicates
- lens and authority envelope
- open and critical unknowns
- selected and banned routes
- root-cause map
- verified evidence refs
- appreciation findings
- bounded recent events
- hash-chain tip

A specialist returns a proposed delta. The deterministic kernel applies it. This
keeps provider models replaceable and prevents parallel workers from silently
forking mission truth.

## Completion semantics

`COMPLETE_VERIFIED` requires:

- every completion predicate satisfied;
- no critical unknowns;
- valid event chain;
- independent verification evidence;
- appreciation gate satisfied when that lens was requested.

Artifacts, source code, agent consensus, confident prose and provider output alone
are never completion proof.

## Provider adapters

The v1 kernel is deliberately provider-neutral. Future adapters may bind it to
OpenAI, Gemini or another authorised model. A provider adapter must preserve:

- mission-version pinning;
- structured role request/response;
- tool authority filtering;
- context projection;
- independent verification;
- provider-native canary before claiming runtime activation.

A provider-backed runtime is a separate maturity step from source admission and
deterministic qualification.
