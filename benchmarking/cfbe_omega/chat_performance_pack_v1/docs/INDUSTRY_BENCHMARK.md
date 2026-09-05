# Industry Capability Benchmark — 2026-09-04

This is a capability-contract benchmark from current official documentation, not an independent vendor throughput or quality test.

| Capability | Industry-leading documented pattern | Gap addressed by this pack |
|---|---|---|
| Long-running work | OpenAI background Responses support asynchronous execution, polling, cancellation and resumable streaming cursors | Terminal state and explicit de-instrumentation |
| Context economics | OpenAI and Anthropic prompt caching reuse stable prefixes; Anthropic and OpenAI document compaction/context management | Task-bounded capsule and stable canonical prefix |
| Tool round trips | Anthropic programmatic tool calling executes multiple tool calls in code and filters results before model context | O(1) head and metadata-first snapshot |
| Durable recovery | Temporal replays event history; LangGraph checkpointers persist state and resume after failure | Transactional ledger, hash chain, generation/fence |
| Agent state | Microsoft Agent Framework and Google Agent Platform document managed sessions/checkpoints/state | Explicit source epochs, capsule and snapshot |
| Observability | OpenAI Agents SDK traces runner, turns, agents, generations, tools, guardrails and handoffs; OpenTelemetry defines common GenAI agent spans | Correlation-ready receipt schema and proof-state split |
| Evaluation | Google documents final-response and trajectory evaluation; OpenAI documents eval-driven iteration | Fixed matched canary lifecycle and strict promotion rule |
| Governance | OpenAI Agents SDK supports serializable pause/approve/resume and fail-closed approvals | External mutation remains separately gated |

## Sources

- https://developers.openai.com/api/docs/guides/background
- https://developers.openai.com/api/docs/guides/prompt-caching
- https://openai.github.io/openai-agents-python/
- https://openai.github.io/openai-agents-python/tracing/
- https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
- https://docs.anthropic.com/en/docs/build-with-claude/context-windows
- https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/programmatic-tool-calling
- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.temporal.io/workflow-execution
- https://learn.microsoft.com/en-us/agent-framework/overview/
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale
- https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md
