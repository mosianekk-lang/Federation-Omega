# CFBE Ω — Chat Integrity / Mission-Completion Audit — 5 September 2026

Status: SOURCE CANDIDATE — repository admission and host/runtime proof remain separate.

## Audit subject

The active ChatGPT/Federation workstream that created Human-First Ω, bound Forest-First Ω, implemented Solve-Before-Report, and then exposed two owner-corrected defects:

1. a material maturity/status answer overstated the practical meaning of `implemented`; and
2. the assistant terminated a response after identifying a known actionable gap instead of continuing safe authorised work.

The audit treats these as engineering failures, not presentation defects.

## Evidence from the current estate

The estate already contained much of the right doctrine:

- ACME-001: mission completion outranks turn completion and distinguishes documentation/source/CI from execution/deployment.
- RealityGuard: typed claim-versus-proof lifecycle states with fail-closed completion/false-reality verdicts.
- ChatBridge completion witness: terminal provider claims can require provider/app evidence rather than owner assertion.
- ChatGov completion interlock: automatic reconciliation before repeated owner prompts.
- Human-First Outcome-First: recoverable issues remain internal until verified solution or genuine escalation.
- ConnectorGateway/StallDetector: retries, semantic readback, idempotency, circuit breaking and stalled-route repair.

The failure was **enforcement placement**: no mandatory `PRE_FINAL_RESPONSE` policy-enforcement point composed mission closure, claim integrity, outcome-first recovery and mandatory-control coverage before a response could be emitted.

## CFBE pre-remediation score

This is a transparent architectural heuristic, not an externally certified product benchmark.

| Dimension | Weight | Score /100 | Main finding |
|---|---:|---:|---|
| Mission completion / termination integrity | 15% | 42 | Doctrine existed; no final-response Stop gate; observed premature termination. |
| Claim integrity / maturity truth | 15% | 48 | RealityGuard strong but not mandatory at response emission; observed source/runtime implication drift. |
| Outcome-first recovery | 10% | 74 | Source policy and real internal recovery behavior existed; not universally bound. |
| Proof/readback discipline | 10% | 88 | Strong exact-head CI, provider readback, rollback and state separation. |
| Durable continuity / resume | 10% | 80 | WAL/checkpoints/continuity strong; not a universally durable external workflow runtime. |
| Policy enforcement placement | 15% | 45 | Key controls present but could be orphaned from the point they were meant to control. |
| Observability / eval feedback | 8% | 63 | Metrics/checkpoints exist; production failures are not yet automatically normalized into a release-blocking eval corpus. |
| Human burden / creator-time protection | 10% | 58 | Scoped preauthorization helps, but the owner still had to detect misleading completion/reporting failures. |
| Recovery / resilience | 4% | 81 | Retry, circuit, isolation, outcome-first and concurrency recovery are comparatively strong. |
| Interoperability / composability | 3% | 70 | Rich internal organ architecture; universal MCP/A2A/provider runtime binding remains unproved. |

**Weighted CFBE score: 61/100.**

## Frontier benchmark mechanisms harvested

The comparison is mechanism-level, not a claim that one product is globally superior.

### Anthropic Claude Code — deterministic Stop hooks

Public current documentation exposes a `Stop` lifecycle hook that can block stopping and feed the reason back so the agent continues. `TaskCompleted` can also be blocked. This directly addresses the defect where the working model decides it is done but a separate policy evaluator disagrees.

Harvested gene: **PRE_FINAL_RESPONSE_STOP_GATE**.

### OpenAI Agents SDK — output guardrails and durable RunState

Output guardrails evaluate the final agent output at the workflow boundary; tool guardrails cover tool-call boundaries. HITL `RunState` is serializable/resumable and ambiguous output-bearing resume cases fail closed.

Harvested genes: **FINAL_OUTPUT_GUARDRAIL**, **FAIL_CLOSED_RESUME_PROVENANCE**, **RUN_STATE_BOUNDARY**.

### Microsoft AutoGen — explicit stateful termination conditions

AutoGen models stopping as a stateful `TerminationCondition` rather than an informal prose instruction, and conditions can be composed.

Harvested gene: **TYPED_TERMINAL_STATE_CONTRACT**.

### LangGraph — checkpoint/pending-write recovery

LangGraph persistence checkpoints graph state and preserves completed pending writes when another node fails, enabling resume without rerunning successful work.

Harvested gene: **RESUMABLE_TURN_BOUNDARY_REQUIRES_CHECKPOINT**.

### Temporal — durable execution

Temporal’s durable workflow model resumes after process/network/infrastructure failure rather than treating an in-memory turn as the mission boundary.

Harvested gene: **MISSION_LIFETIME_INDEPENDENT_OF_TURN_LIFETIME**. Full Temporal provider/runtime adoption is not claimed by this source tranche.

### Open Policy Agent — PDP/PEP separation and decision logs

OPA separates policy decision points from enforcement points, recommends policy near the enforcement surface, and emits auditable decision IDs/logs.

Harvested genes: **CONTROL_BINDING_COVERAGE**, **PRE_FINAL_POLICY_ENFORCEMENT_POINT**, **DURABLE_DECISION_RECEIPT**.

### Braintrust / W&B Weave — trajectory evals and trace-to-regression

Modern agent evaluation inspects trajectories/tool calls rather than only final prose, and production traces can become regression datasets.

Harvested gene: **OBSERVED_FAILURE_TO_REGRESSION**. This tranche adds deterministic regressions and decision metrics; automatic external trace-platform ingestion remains a later empirical integration gate.

## Clean-room composition admitted by design

No new sovereign truth system is created. The remediation composes existing estate authorities:

`ACME mission rule`
→ `Human-First Outcome-First`
→ `RealityGuard/admitted claim-proof verdict`
→ `ChatGov PRE_FINAL_RESPONSE enforcement`
→ `DurableState decision receipt`
→ `final response or continued execution`.

The new source module is `bubbles/chat_governor_omega3/pre_final.py`.

### Core invariant

`known + material + safe + authorised + available + non-owner-only = CONTINUE`

not:

`describe remaining work → stop`.

### Material claim invariant

Words such as `implemented`, `operational`, `live`, `deployed`, `fixed`, `resolved`, `complete`, `connected`, `integrated`, `verified`, `active`, `fully`, `universal`, or equivalent require an admitted claim-proof snapshot before a routed host may emit them as material maturity claims.

### Valid terminal states

- `VERIFIED_COMPLETE` with objective satisfaction;
- `OWNER_DECISION_REQUIRED` with a precise decision request;
- `BLOCKED_IRREDUCIBLY` with blocker + exhaustion evidence;
- `LEGAL_OR_SAFETY_PROHIBITION` with a specified prohibition; or
- `ACTIVE_TURN_BOUNDARY` with no currently executable work and a resumable checkpoint.

## New regression classes

- F19 `KNOWN_ACTIONABLE_GAP_PREMATURE_TERMINATION`
- F20 `SOURCE_RUNTIME_CONFLATION`
- F21 `BOUNDED_TO_UNIVERSAL_GENERALISATION`
- F22 `ORPHAN_MANDATORY_CONTROL_ENFORCEMENT`
- F23 `PROBLEM_REPORTED_BEFORE_AVAILABLE_RECOVERY`
- F24 `MATURITY_CLAIM_WITHOUT_CLAIM_PROOF_SCAN`

## Expected performance effect

The intended improvement is not more reasoning tokens. It is less wasted human work and fewer invalid terminal responses:

- lower owner debugging/contradiction burden;
- lower repeated prompt burden;
- lower maturity overclaim rate;
- fewer actionable gaps abandoned at response boundaries;
- higher solved-before-escalation rate;
- better auditability through deterministic decision IDs/checkpoints;
- higher reuse of already-completed work after interruptions.

These effects are hypotheses until measured on prospective cohorts. Source admission alone does not prove owner-value improvement.

## Public benchmark references used for mechanism harvest

- Claude Code Hooks / Stop: https://code.claude.com/docs/en/hooks
- Claude Code hooks guide: https://code.claude.com/docs/en/hooks-guide
- OpenAI Agents SDK guardrails: https://openai.github.io/openai-agents-python/guardrails/
- OpenAI Agents SDK RunState/HITL: https://openai.github.io/openai-agents-python/ref/run_state/
- AutoGen termination: https://microsoft.github.io/autogen/dev/user-guide/agentchat-user-guide/tutorial/termination.html
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- Temporal docs: https://docs.temporal.io/
- OPA deployment / PEP-PDP: https://www.openpolicyagent.org/docs/deploy
- OPA decision logs: https://www.openpolicyagent.org/docs/management-decision-logs
- W&B Weave agent evals: https://docs.wandb.ai/weave/agent-evals
- Braintrust agent evaluation: https://www.braintrust.dev/articles/how-to-eval

## Proof boundary

This audit/remediation source does **not** claim:

- native ChatGPT final-output hooks have been modified;
- native ChatGPT is mechanically unable to violate these rules;
- universal Gemini/Copilot/OpenRouter/Microsoft/provider enforcement;
- automatic external OPA, Temporal, Braintrust, Weave, LangGraph, AutoGen or Claude runtime integration;
- H9 empirical superiority over those systems; or
- H10 receiver-local human-value improvement.

Those are separate execution/empirical gates.
