# SOVARA Sovereign Intelligence Court v2

## Canonical user experience

The intended ChatGPT-facing interaction is:

```text
SOVARA — external model review

<PASTE CODE>
```

The chat is a client terminal. It is not the system of record and it does not have to sequence multiple internal tools. The public MCP surface intentionally exposes one user-goal tool: `sovara_external_model_review`.

## Architecture

1. **MCP ingress** receives supplied code, declared language, objective and review mode.
2. **Durable mission control** creates a deterministic mission ID from the exact source hash and review contract, then checkpoints every material transition.
3. **Privacy preflight** blocks secret-shaped source from external transmission by default.
4. **Round 1** requests blind independent external reviews when OpenRouter authority is actually present. A deterministic non-executing local lane always remains available.
5. **Disagreement extraction** separates exact consensus signals from non-identical proposal positions.
6. **Round 2** cross-examines anonymized competing proposals when an authorized external route exists.
7. **Bounded ΑΩ5 binding** attaches the repository-native JARVIS ΑΩ5 profile without claiming signed SLOS or provider authority.
8. **Ω-Scientist contract** requires challenger hypotheses, falsification, measured gain and rollback.
9. **CFBE contract** refuses to invent scores before empirical benchmark evidence exists.
10. **Zero-dilution court** keeps the incumbent canonical and prevents direct model-output promotion.
11. **Sealed receipt** is hash-bound and exact retries return the sealed result without re-entering providers.

## Platform-resilience law

A provider policy boundary, refusal, timeout, outage, rate limit, missing credential, client disconnect, UI failure, CI failure or context exhaustion is an observed boundary event. SOVARA may degrade or reroute only through independently authorized lanes. A boundary event never grants authority to bypass provider/platform safeguards.

The mission objective, source hash and acceptance criteria survive the event. Unrelated safe lanes continue. If no safe lane remains, SOVARA checkpoints and holds instead of fabricating success.

## Degradation modes

- `FULL`: at least two external review responses plus a sovereign deterministic/local lane.
- `DEGRADED_EXTERNAL_PARTIAL`: at least one external response but full diversity is not proven.
- `DEGRADED_LOCAL_ONLY`: an explicitly attached local model lane is available while external providers are not.
- `DEGRADED_DETERMINISTIC_ONLY`: only non-executing deterministic source analysis is available.
- `CHECKPOINT_ONLY`: no safe review lane is available; mission state is preserved for resume.

## Authority separation

- External and local models: intelligence suppliers only.
- Deterministic analyzers: evidence generators only.
- SOVARA: orchestration authority.
- SLOS: decision authority.
- Owner: final approver.
- GitHub: source control, CI, admission and regression proof; not the production SOVARA runtime.

No external model answer can directly mutate or promote canonical code.

## Review modes

`AUTO`, `CREATIVE`, `RED_TEAM`, `ARCHITECTURE`, `ZERO_DILUTION`, `PERFORMANCE`, `SECURITY`, and `10X` alter review strategy only. They do not alter authority, privacy, safety or release boundaries.

## Current truth boundary

Source implementation and CI proof do not equal a deployed MCP endpoint. A deployed MCP endpoint does not equal a ChatGPT connection. OpenRouter connectivity requires exact provider response/readback for the executing runtime. A candidate code recommendation does not become canonical until independent tests, empirical CFBE comparison, zero-dilution regression, rollback and applicable release/recovery gates pass.

## Deployment target

The production path is a persistent SOVARA service exposing MCP Streamable HTTP at a stable HTTPS `/mcp` endpoint. Mission state must live on durable storage across runtime restarts; container-local ephemeral disk is not sufficient production durability.

The current OpenAI plugin guidance recommends building tools first, using Streamable HTTP for deployed MCP servers, and connecting ChatGPT to a stable HTTPS endpoint that typically ends in `/mcp`.
