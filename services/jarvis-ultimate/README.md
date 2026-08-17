# JARVIS Ultimate Federation v1.5.0

JARVIS v1.5.0 is a governed interactive intelligence foundation built additively on the v1.4.0 authority and assurance core. It combines an ADK 2 workflow entrypoint, explicit Google GenAI provider selection, typed Formation action/resource/argument schemas, Ed25519 single-use permits, deterministic mathematics, a 32-principle truth-typed doctrine, route quarantine, anchored learning telemetry, and the proof-bearing `T20-AO-OMEGA-SCIENTIST-1.1` execution governor.

## Verified maturity

`IMPLEMENTED_TESTED_LOCAL`

This repository proves source structure and local behavior. It does **not** prove live Gemini, Google Workspace, Cloud Run, Agent Runtime, production persistence, or all-Federation authority. ChatGPT connector credentials remain bound to their connector context and are never inherited by this runtime. Google Cloud IAM is not treated as Workspace user-data authority.

## T20 Alpha–Omega execution model

Each bounded JARVIS execution attempt has a 1,200-second envelope:

- 0–120 seconds: lock the objective, deliverable form, expected state delta, current authority and proof target.
- 120–720 seconds: execute only genuinely independent high-value streams.
- At 720 seconds: split any remaining monolith.
- At 900 seconds: stop scope expansion and converge.
- At 1,080 seconds: enter release-only mode; no new work begins.
- At 1,200 seconds: terminate the attempt with an honest terminal receipt.

Three bounded paths are available: primary delivery, protective assurance, and failure recovery. Six streams are available: source truth, implementation, test/validation, adversarial risk, semantic readback, and method learning. Fan-in is mandatory before a completion claim.

Valid terminal states are:

- `COMPLETE_VERIFIED`
- `BOUNDED_COMPLETE`
- `BLOCKED_WITH_EXECUTABLE_NEXT_ROUTE`

The governor records route results separately as `SUCCESS`, `FAILURE`, `BLOCKED`, `NO_OP`, or `UNVERIFIED`. A successful lane is preserved when another route fails. The first `NO_OP` opens the no-op circuit and prohibits an unchanged retry.

## Proof-bearing cycle review

The cycle-review API does not accept caller-supplied quality booleans. Every required gate must provide a fresh structured evidence object containing:

- pass/fail state;
- trusted source class;
- proof reference;
- 64-character semantic digest;
- observation timestamp;
- independence state.

The adversarial gate must be independent. Evidence older than 24 hours is rejected. A speed reduction can be proposed only after a `COMPLETE_VERIFIED` cycle and remains a `SHADOW_CANDIDATE`; it is never self-promoted.

Required gates are objective/form lock, source fidelity, actual implementation/result, testing, independent adversarial review, semantic readback, known-failure replay, truthful completion, and a next best automated pathway.

The machine-readable 72-hour review is in `LESSON_GATE_72H.json`. It records why the earlier simplified T20 branch required repair, maps 21 recent Federation lessons to controls/tests, preserves the old head on an archive branch, and holds merge until provider checks and owner approval pass.

## Core reasoning and authority model

`intake → evidence context → objective/form lock → credential-free advisory twin → reason → response-contract verification → T20 assurance fan-in → unpromoted learning event → terminal receipt`

The HTTP/CLI path and the ADK `Workflow` entrypoint call the same governed graph. No ADK node receives effectful tools. Chat accepts only a typed `ADVISORY` or deterministic-result envelope with `NO_EFFECTS_EXECUTED`; it always returns `effectFruit=false`. Trusted local offline/math routes may return `semanticFruit=true`. External model output is explicitly qualified as untrusted, returns only `advisoryFruit=true`, and cannot mint semantic, provider, deployment or effect proof.

An effectful adapter may run only after typed resource/argument validation, the full effective-authority intersection, and a subject/mission-version/action/capability/resource/argument/idempotency-bound Ed25519 v3 permit are satisfied in the executor transaction. The verifier contains only a public key and cannot mint permits. The HTTP `/v1/authorize` route is dry-run only and never consumes a permit or executes a tool.

Provider selection never falls back across providers:

- `JARVIS_PROVIDER=offline`: deterministic local route; credentials are ignored.
- `JARVIS_PROVIDER=gemini_developer`: requires an explicit model plus `GOOGLE_API_KEY` or `GEMINI_API_KEY`.
- `JARVIS_PROVIDER=gemini_vertex`: requires an explicit model, project, location and ambient ADC.

A configured provider remains `ACTIVE_PARTIAL`. A contract-valid external response creates only a session-scoped advisory-contract receipt; it does not create semantic, provider, deployment or effect proof.

## Owner communication boundary

`gmail.send` and `gmail.forward` remain effectful action schemas. They require an explicit current owner grant, exact OAuth/IAM/tool/resource authority, and an executor-only single-use permit. No email send or forward may be inferred from a draft, request, plan, connector availability, or provider transmission record.

## Run locally

```bash
PYTHONPATH=. python -m jarvis.main "Map my next objective"
JARVIS_API_TOKEN=local-only PYTHONPATH=. python -m jarvis.main --serve --port 8080
```

Open `http://127.0.0.1:8080`. A production listener must set `JARVIS_API_TOKEN`; secrets belong in Secret Manager, never source, prompts, logs, Drive or GitHub.

## Run with Gemini Developer API

```bash
JARVIS_PROVIDER=gemini_developer \
JARVIS_GEMINI_MODEL=YOUR_EXACT_TESTED_MODEL \
JARVIS_GEMINI_API_VERSION=v1beta \
GOOGLE_API_KEY=SECRET_FROM_RUNTIME \
PYTHONPATH=. python -m jarvis.main "Run a bounded semantic canary"
```

For Vertex/Agent Platform, select `gemini_vertex`, set an exact model, project and location, and use the Cloud Run service identity through ADC. Never set `GOOGLE_APPLICATION_CREDENTIALS` in Cloud Run.

## Interfaces

- `GET /health`
- `GET /v1/capabilities`
- `GET /v1/principles`
- `GET /v1/execution-policy`
- `POST /v1/chat`
- `POST /v1/plan`
- `POST /v1/math`
- `POST /v1/authorize` — dry-run decision only
- `POST /v1/cycle-review` — proof-bearing T20 review

Example plan request:

```json
{
  "objective": "Finish the governed build",
  "deliverableForm": "stacked GitHub pull request",
  "expectedStateDelta": "candidate source and proof receipt exist without changing main"
}
```

Example authorization preview:

```json
{
  "missionId": "M1",
  "missionVersion": 24,
  "actionId": "gmail.send",
  "capability": "gmail",
  "resource": "gmail:draft-1",
  "arguments": {
    "idempotency_key": "job-1",
    "to_hash": "…",
    "body_hash": "…"
  },
  "permit": "..."
}
```

The preview denies because the public HTTP route cannot provide a trusted authority envelope. Unknown action strings fail closed.

## Science, mathematics and philosophy boundary

The doctrine contains 9 categories and 32 principles. Every item is typed as `EMPIRICAL_LAW`, `MATHEMATICAL_THEOREM`, `HEURISTIC`, or `METAPHOR`, with operational uses, limits and falsification checks. Kung-fu concepts are decision heuristics only; they cannot prove facts, grant authority or override law and governance. The safe AST mathematics engine rejects attribute access, imports, code execution, non-finite values and unbounded exponents.

## Google access boundary

Workspace adapters remain disabled until a separate least-scope OAuth binding and semantic readback passes for the exact user and action. Runtime authority is the intersection:

`user grant ∩ OAuth scopes ∩ IAM ∩ mission permit ∩ tool allowlist ∩ resource boundary`

A missing term means deny. The current capability registry marks Google Cloud as blocked/unverified because the earlier WIF route returned `invalid_target`.

## Test

```bash
uv lock --check
uv sync --frozen
PYTHONPATH=. uv run --frozen python -m unittest discover -s tests -p 'test_*.py' -v
uv run --frozen python -m compileall -q jarvis tests scripts
```

The checked-in universal `uv.lock` remains authoritative. Direct versions remain `google-adk==2.1.0`, `google-genai==1.75.0`, and `cryptography==46.0.0`. The inherited v1.4 assurance suite remains intact; v1.5 adds T20, structured-evidence, route-accounting, no-op, deadline, next-pathway, email-authority, HTTP and 72-hour lesson-gate regressions.

## Deployment gate

The container is buildable, but live deployment is intentionally gated. Promotion requires the installed ADK/GenAI integration tests, exact dependency lock, an externally isolated Ed25519 signer, globally transactional nonce/effect and recovery-generation state, a provider-managed monotonic/immutable ledger high-water anchor, dedicated least-privilege runtime identity, private unauthenticated-denial canary, zero-traffic candidate, two stable action-specific semantic readbacks, source→build→digest→revision lineage, exact traffic proof, rollback restoration, cost-cap proof, and a current Formation permit.

Until those gates pass, `ready=false`, `deployed=false`, and `proven=false` remain authoritative.
