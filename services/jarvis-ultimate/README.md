# JARVIS Ultimate Federation v1.4.0

JARVIS is a governed interactive intelligence foundation that combines an ADK 2 workflow entrypoint, an explicitly selected Google GenAI provider, typed Formation action/resource/argument schemas, a resource-bound single-use permit verifier, a deterministic mathematics engine, a 32-principle scientific doctrine, route quarantine, and concurrency-safe learning telemetry.

## Verified maturity

`IMPLEMENTED_TESTED_LOCAL`

This repository proves source structure and local behavior. It does **not** prove live Gemini, Google Workspace, Cloud Run, Agent Runtime, or all-Federation authority. ChatGPT connector credentials remain bound to their connector context and are never inherited by this runtime. Google Cloud IAM is not treated as Workspace user-data authority.

## Execution model

`intake → evidence context → credential-free advisory twin → reason → response-contract verification → unpromoted learning event`

The HTTP/CLI path and the ADK `Workflow` entrypoint both call the same governed JARVIS graph. No ADK node receives effectful tools. Chat accepts only a typed `ADVISORY` or deterministic-result envelope with `NO_EFFECTS_EXECUTED`; it always returns `effectFruit=false`. Trusted local offline/math routes may return `semanticFruit=true`. External model output is explicitly qualified as untrusted, returns only `advisoryFruit=true`, and cannot mint semantic or effect proof. An effectful adapter may run only after typed resource/argument validation, the full effective-authority intersection, and a subject/mission-version/action/capability/resource/argument/idempotency-bound Ed25519 v3 permit are satisfied in the executor transaction. The verifier contains only a public key and cannot mint permits.

Provider selection never falls back across providers:

- `JARVIS_PROVIDER=offline`: deterministic local route; credentials are ignored.
- `JARVIS_PROVIDER=gemini_developer`: requires an explicit model plus `GOOGLE_API_KEY` or `GEMINI_API_KEY`.
- `JARVIS_PROVIDER=gemini_vertex`: requires an explicit model, project, location and ambient ADC.

A configured provider remains `ACTIVE_PARTIAL`. A contract-valid external response creates only a session-scoped advisory-contract receipt; it does not create semantic, provider, deployment or effect proof.

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

Example authorization preview (external actions deliberately deny because the public route cannot provide a trusted authority envelope):

```json
{"missionId":"M1","missionVersion":1,"actionId":"gmail.send","capability":"gmail","resource":"gmail:draft-1","arguments":{"idempotency_key":"job-1","to_hash":"…","body_hash":"…"},"permit":"..."}
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

The 32 authored tests cover provider fail-closed behavior, executable Gemini SDK call-contract retention, typed response envelopes, contradictory external advisory qualification, two trusted-local provenance spoof attempts, twelve unsupported untyped effect-claim variants, false-live prevention, typed action/resource/argument bypass attempts, Ed25519 permit binding/expiry/replay, enforced quarantine, signed generation-bound recovery receipts, replay rejection and in-process atomic consumption, input-failure isolation, concurrent ledger writes, authenticated checkpoints, retained separate file anchoring, deletion/rollback/replay and tamper write refusal, authority intersection, interactive safe mathematics, science doctrine invariants, protected browser bootstrap, and the ADK workflow entrypoint source contract.

## Deployment gate

The container is buildable, but live deployment is intentionally gated. Promotion requires: installed ADK/GenAI integration tests, exact dependency lock, an externally isolated Ed25519 signer, globally transactional nonce/effect and recovery-generation state, a provider-managed monotonic/immutable ledger high-water anchor that survives total local-state deletion or replay, dedicated least-privilege runtime identity, private unauthenticated-denial canary, zero-traffic candidate, two stable action-specific semantic readbacks, source→build→digest→revision lineage, exact traffic proof, rollback restoration, cost-cap proof, and a current Formation permit. Until those gates pass, `cloudDeployed=false` and `geminiLive=false` remain authoritative.
