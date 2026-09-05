# CFBE Ω — Chat Performance Frontier Audit — 5 September 2026

Status: **SOURCE CANDIDATE — host binding, CI admission, provider runtime and empirical owner-value remain separate proof gates.**

Current source anchor at audit start: `f8d9e7a0188d0efe4534fc523ddb1e059e6c7dad`.

## Audit objective

Audit the active ChatGPT/Federation workstream against current frontier agent-engineering mechanisms, identify the main sources of wasted owner time and orchestration drag, and implement the highest-value clean-room performance controls inside the existing ChatGov architecture rather than creating another sovereign system.

## Observed chat-performance defects

1. Repeated connector/tool-schema discovery after an adequate schema had already been loaded.
2. Repeated fresh reads of unchanged source/PR/CI state without an explicit freshness lease or semantic read cache.
3. Large workflow logs entering active context when job/step summaries or targeted evidence were sufficient.
4. Sequential read patterns where independent evidence lanes could have been issued concurrently.
5. Successful sibling work sometimes being recomputed after another lane failed or a turn boundary interrupted execution.
6. Specialist/subagent fan-out was not governed by an explicit independence/context-isolation test at the chat orchestration boundary.
7. Context growth was dominated by raw tool payloads instead of delta capsules and stable proof pointers.
8. Owner burden was discussed, but duplicate reads, schema rediscovery, repeated prompts, unnecessary specialists and full-log fetches were not all first-class performance counters.
9. The repository contains strong source-level ChatGov controls, but native host binding remains a separate fact and cannot be inferred from source presence.
10. Architecture/capability growth has outpaced prospective matched owner-value measurement.

## CFBE score

This score is a transparent engineering heuristic for this observed workstream, not an independent certification.

| Dimension | Weight | Observed /100 | Source-potential /100 | Main finding |
|---|---:|---:|---:|---|
| Correctness / proof discipline | 14 | 86 | 93 | Strong proof-before-claim and source/runtime separation; some costly rereads. |
| Mission completion | 12 | 75 | 92 | PRE_FINAL controls are strong in source; host binding is not universal. |
| Authority / effect safety | 12 | 92 | 96 | External-effect boundaries are strong and explicit. |
| Retrieval / context efficiency | 12 | 42 | 82 | Raw logs and repeated reads are the largest practical drag. |
| Tool-call efficiency | 10 | 40 | 80 | Schema discovery, readback and polling can be deduplicated. |
| Failure recovery / resume | 10 | 80 | 92 | Checkpoints and continuity exist; sibling-work preservation needs to be universal. |
| Parallelism / scheduling | 8 | 38 | 78 | DAG capability exists but chat-level independent reads remain too sequential. |
| Observability / eval feedback | 8 | 75 | 90 | Strong trace/proof foundations; failure-to-regression is not yet universal. |
| Owner-burden reduction | 8 | 50 | 78 | Owner still detects some orchestration inefficiency and stale-work conditions. |
| Interoperability / skill portability | 6 | 67 | 82 | MissionIR/MCP/A2A direction is sound; selective skill loading needed. |

**Observed chat score: ~66/100. Source architecture potential after this tranche: ~84/100.**

The gap between those scores is the central finding: the estate already contains many high-grade components, but the chat surface does not consistently exploit them at the point where tool calls, context growth, specialist fan-out and finalization are decided.

## Frontier mechanism harvest

Mechanism-level comparison only; no claim that one product is globally superior.

- **OpenAI Agents SDK**: lightweight agents/handoffs, input/output/tool guardrails, sessions and built-in traces spanning model, tool, guardrail and handoff activity. Harvest: lifecycle enforcement + semantic execution traces.
- **LangGraph**: checkpoint persistence and pending writes preserve successful sibling-node outputs when another node fails. Harvest: pending-work preservation + exact-resume reuse.
- **Temporal**: durable workflow execution persists progress through process/network/infrastructure failure. Harvest: mission lifetime must be independent of a single turn/process lifetime.
- **GitHub Copilot**: explicit session/tool/error/stop hooks; `preToolUse` can allow/deny/modify a tool call and `agentStop` can force continued work. Harvest: typed lifecycle hook bus and pre-tool enforcement.
- **Claude Code**: Stop/TaskCompleted hooks can block premature stopping or completion and feed the reason back for continued work. Harvest: explicit stop/completion feedback loop.
- **Google ADK / Agents CLI**: reusable skills, automated evaluation workflows, trace-oriented observability and persistent sandbox execution. Harvest: dynamic skill paging + eval-fix discipline + persistent workspaces.
- **A2A + MCP**: A2A provides agent capability discovery/collaborative task interoperability; MCP standardizes external resources/tools. Harvest: keep agent interoperability and tool/data interoperability separate and typed.
- **OpenTelemetry**: semantic conventions standardize spans/attributes across platforms. Harvest: OTel-shaped mission/tool/cache/error telemetry without claiming an exporter is bound.

Public references:
- https://openai.github.io/openai-agents-python/
- https://openai.github.io/openai-agents-python/guardrails/
- https://openai.github.io/openai-agents-python/tracing/
- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.temporal.io/
- https://docs.github.com/en/copilot/concepts/agents/hooks
- https://code.claude.com/docs/en/hooks
- https://google.github.io/agents-cli/reference/skills/
- https://google.github.io/agents-cli/guide/evaluation/
- https://a2a-protocol.org/dev/specification/
- https://modelcontextprotocol.io/specification/2025-11-25
- https://opentelemetry.io/docs/specs/semconv/

## Implemented performance tranche — ChatGov Ω3.5

The new `bubbles/chat_governor_omega3/performance_kernel.py` adds thirteen bounded controls:

1. `LifecycleHookBus` — typed SESSION/PROMPT/PRE_TOOL/POST_TOOL/FAILURE/PRE_FINAL/END hook points with material-effect fail-closed behavior.
2. `ToolSchemaCache` — TTL + source-version aware schema discovery reuse.
3. `SemanticReadCache` — exact-source read dedupe; effectful actions are never cacheable.
4. `ElasticSpecialistPlanner` — specialists only when task complexity, parallelizability and context isolation justify them; shared mutable dependencies suppress fan-out.
5. `PendingWorkLedger` — preserves successful sibling work so retry/resume does not recompute it.
6. `DeltaCapsuleCompiler` — content-addressed delta state instead of repeatedly hydrating unchanged context.
7. `SkillPager` — relevance-driven skill loading with dependency closure and a hard active-skill budget.
8. `InformationGainStopRule` — required work always runs; optional research stops below marginal decision value.
9. `UnnecessaryWorkMeter` — directly measures duplicate reads, schema rediscovery, recomputation, unnecessary specialists, repeated owner prompts, full-log fetches and tool round trips.
10. `TraceToRegressionCompiler` — converts observed failures into sanitized regression candidates; never auto-commits or grants provider authority.
11. `HostBindingContract` — distinguishes `SOURCE_ONLY_UNBOUND`, `PARTIAL_HOST_BINDING` and `HOST_BOUND` so source capability cannot masquerade as native host enforcement.
12. `PreFinalEfficiencyGate` — finalization is blocked when known material, safe, authorized, available system work remains; owner-only decisions remain explicit.
13. `SemanticSpan` — OTel-shaped execution attributes for mission, operation, tool, cache hit, context size, duration and error type.

## Measurable 2× hypothesis

A performance win is not declared from source tests. The prospective target is:

**≥50% reduction in combined duplicate reads + schema rediscovery + repeated successful-task recomputation + avoidable owner continuation prompts + full-log retrieval + tool round trips per substantive mission, with no degradation in correctness/proof quality.**

The `UnnecessaryWorkMeter` encodes this as a measurable comparison rather than a marketing claim. A matched prospective cohort is still required before declaring a 2× owner-value result.

## Remaining high-value frontier

Highest-value next work after admission is not more architecture names. It is host binding and empirical closure: bind these controls at the actual chat/tool execution boundary where possible, make cache/trace/pending-write receipts durable across turns, feed real sanitized failures into regression datasets, and run matched missions until owner-burden/latency/quality deltas are statistically useful.

Repository release enforcement is also still incomplete while `main` has no provider-native required-status protection. That is a separate provider-administration gate and is not altered by this source tranche.

## Proof boundary

This tranche does **not** claim that native ChatGPT context management, model serving, tool routing, Gemini/Copilot/Claude runtimes, GitHub branch protection, IAM, deployments, traffic or provider authority have been changed. It is source-level executable code plus deterministic tests and ProofOS mapping. CI admission and any later source promotion remain separate gates.
