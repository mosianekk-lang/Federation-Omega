# JARVIS Ultimate Federation v1.1

JARVIS is a governed interactive intelligence foundation that combines an ADK 2 workflow entrypoint, an explicitly selected Google GenAI provider, exact Formation action schemas, a single-use permit verifier, a deterministic mathematics engine, a 32-principle scientific doctrine, route quarantine, and concurrency-safe learning telemetry.

## Verified maturity

`IMPLEMENTED_TESTED_LOCAL`

This repository proves source structure and local behavior. It does **not** prove live Gemini, Google Workspace, Cloud Run, Agent Runtime, or all-Federation authority. ChatGPT connector credentials remain bound to their connector context and are never inherited by this runtime. Google Cloud IAM is not treated as Workspace user-data authority.

## Execution model

`intake → evidence context → credential-free advisory twin → reason → semantic verification → unpromoted learning event`

The HTTP/CLI path and the ADK `Workflow` entrypoint both call the same governed JARVIS graph. No ADK node receives effectful tools. An effectful adapter may run only after the exact action schema and a mission/action/capability-bound HMAC permit are consumed in the executor transaction.

Provider selection never falls back across providers:

- `JARVIS_PROVIDER=offline`: deterministic local route; credentials are ignored.
- `JARVIS_PROVIDER=gemini_developer`: requires an explicit model plus `GOOGLE_API_KEY` or `GEMINI_API_KEY`.
- `JARVIS_PROVIDER=gemini_vertex`: requires an explicit model, project, location and ambient ADC.

A configured provider remains `ACTIVE_PARTIAL`. A successful response creates only a session-scoped semantic proof; deployment and independent provider proof remain separate gates.

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
- `POST /v1/chat`
- `POST /v1/plan`
- `POST /v1/math`
- `POST /v1/authorize` — dry-run decision only; it never consumes a permit or executes a tool

Example math request:

```json
{"expression":"sqrt(81) + sin(pi / 2)"}
```

Example authorization preview:

```json
{"missionId":"M1","actionId":"gmail.send","capability":"gmail","permit":"..."}
```

Unknown action strings fail closed. Exact effectful schemas include `drive.write`, `drive.share`, `gmail.send`, `calendar.schedule`, `github.release`, `cloud.deploy_candidate`, `cloud.promote_candidate`, and `federation.invoke`.

## Science, mathematics and philosophy boundary

The doctrine contains 9 categories and 32 principles. Every item is typed as `EMPIRICAL_LAW`, `MATHEMATICAL_THEOREM`, `HEURISTIC`, or `METAPHOR`, with operational uses, limits and falsification checks. Kung-fu concepts are decision heuristics only; they cannot prove facts, grant authority or override law and governance. The safe AST mathematics engine rejects attribute access, imports, code execution, non-finite values and unbounded exponents.

## Google access boundary

Workspace adapters remain disabled until a separate least-scope OAuth binding and semantic readback passes for the exact user and action. Runtime authority is the intersection:

`user grant ∩ OAuth scopes ∩ IAM ∩ mission permit ∩ tool allowlist ∩ resource boundary`

A missing term means deny. The current capability registry explicitly marks Google Cloud as blocked/unverified because the earlier WIF route returned `invalid_target`.

## Test

```bash
PYTHONPATH=. python -m unittest discover -s tests -p 'test_*.py' -v
python -m compileall -q jarvis tests
```

The tests cover provider fail-closed behavior, false-live prevention, action-schema bypass attempts, permit binding/expiry/replay, enforced quarantine, semantic fruit rejection, concurrent ledger writes, tamper detection, authority intersection, safe mathematics, science doctrine invariants, and the ADK workflow entrypoint.

## Deployment gate

The container is buildable, but live deployment is intentionally gated. Promotion requires: exact dependency lock, dedicated least-privilege runtime identity, private unauthenticated-denial canary, zero-traffic candidate, two stable semantic readbacks, source→build→digest→revision lineage, exact traffic proof, rollback restoration, cost-cap proof, and a current Formation permit. Until those gates pass, `cloudDeployed=false` and `geminiLive=false` remain authoritative.
