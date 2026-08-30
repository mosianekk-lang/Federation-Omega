# FCX-COPILOT PRO — Federation Adapter v1

## Objective

Use the owner's existing GitHub Copilot Pro entitlement as a governed Federation Cognitive Exchange (FCX) surface for coding, review, falsification and model challenge work before purchasing redundant external inference.

This adapter does **not** replace Copilot's service or expose a hidden API. It creates a deterministic Federation contract around tasks that are launched through supported Copilot surfaces and then scores only observed results.

## Reuse-first architecture

The adapter reuses:

- `AGENTS.md` and `.github/copilot-instructions.md` for repository governance;
- GitHub's native `.github/agents/*.agent.md` custom-agent profiles;
- `federation.orchestration.mission_arbitration.CapabilityRoute` and `CapabilitySelector` for CFBE tournament scoring;
- Phoenix Airlock, source provenance and Leak Guard for source admission;
- KDV/learning/proof systems for runtime evidence outside public source.

It does not introduce a second mission router or a parallel proof system.

## Governed roles

### FCX Builder

Use for bounded implementation work. The task must explicitly authorize branch/PR source changes. Direct `main` writes, provider mutations and consequential external effects are prohibited.

### FCX Reviewer

Independent read-only code/proof review. It should identify defects, missing tests, unsupported proof claims and unnecessary complexity without modifying source.

### FCX Falsifier

Read-only adversarial review. It tries to break the proposed solution, identify hidden assumptions, stale-state hazards, security/privacy failures and conditions under which the claimed behavior is false.

### FCX Gemini Challenger

Proposal-only challenger intended for use with a Gemini model selected through a supported Copilot model selector when available. The profile itself does not prove model identity. Any Gemini-specific claim requires runtime readback of the observed model.

## AI-credit policy

The public contract knows the current public Copilot Pro plan shape, but account-specific usage remains private evidence.

Rules:

1. Fresh usage/budget snapshot before an AI-credit-consuming task.
2. Every task receives an explicit credit ceiling for Federation planning.
3. Included credits are preferred first.
4. Paid overage defaults to **DENY**.
5. If a task may exceed included credits, it remains held unless paid usage is explicitly authorized **and** provider-side budget enforcement is verified.
6. A Federation task ceiling is not proof that GitHub will terminate a running agent at that amount; post-run usage must be read back from GitHub's AI usage surface or a supported billing API.
7. Normal code completion/next-edit usage is outside this task-dispatch contract because paid Copilot plans treat those separately from AI-credit-metered agent/chat usage.

## Privacy boundary

Copilot is an external service. Default eligible classes are `PUBLIC_SAFE` and `INTERNAL_SAFE`.

Fail closed for:

- legal/case evidence or private case files;
- sensitive identity data;
- credentials, tokens and secret values;
- identity documents;
- any payload whose provider eligibility is not current and explicit.

Private KDV pointers and account billing evidence stay outside public source.

## CFBE scoring

`CopilotRunObservation` does not derive quality from token count or model prestige. The runtime observer must supply grounded normalized metrics for quality, reliability, freshness, proof strength, latency penalty, cost penalty, owner-burden penalty and risk penalty. The adapter converts those metrics into an existing `CapabilityRoute`; the established `CapabilitySelector` remains the ranking authority.

This means Copilot, Gemini-via-Copilot, sovereign models and other eligible routes can participate in the same CFBE tournament without trust transfer.

## Minimum runtime evidence packet

A task is not provider-proven merely because an agent profile exists. A useful runtime receipt should bind:

- deterministic task-envelope hash;
- role;
- observed model identity;
- actual AI credits consumed;
- branch/PR or review reference where applicable;
- tests/proof reference;
- terminal success/failure/constraint state;
- owner-intervention delta;
- later CFBE metrics.

## MCP status

MCP is deliberately **not enabled in v1**. It can materially expand the data/tool surface available to Copilot. A later MCP phase must first define server allowlists, data minimization, secret isolation, authority ceilings, tool-level audit, rollback/disable and a bounded canary.

## Initial proof ladder

1. Source/test/CI admit this adapter and the four agent profiles.
2. Read back current private Copilot usage and confirm included-credit headroom.
3. Run one low-risk Reviewer or Falsifier task using included credits.
4. Read back actual model + credits + task result.
5. Feed measured metrics to CFBE and compare against a non-Copilot baseline.
6. Run a Builder canary only after branch/PR source authority is explicit.
7. Run Gemini Challenger only when the selected model can be independently read back.
8. Expand only after repeated value is demonstrated.

## Truth boundary

Source admission proves only the adapter, policies, profiles and deterministic tests. It does not prove cloud-agent execution, Gemini execution, model identity, AI-credit usage, Copilot code-review quality, MCP connectivity, cost savings or value improvement.
