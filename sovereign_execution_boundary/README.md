# Sovereign Execution Boundary Omega (SEB-Ω) v1

Provider-neutral, policy-governed execution control for Federation workflows.

SEB-Ω prevents route failures, provider refusals, local artifacts, or partial
proofs from redefining the owner's authorized outcome. Objective, constraints,
routes, and completion evidence are separate state domains.

## What is implemented

- Immutable MissionIR with validation and fingerprints.
- Deterministic policy decisions and authority/data/tool gates.
- Provider abstraction, OpenRouter-compatible adapter and mock providers.
- Bounded retry, failover, typed failures and semantic quarantine.
- Append-only hash-chained JSONL evidence ledger with replay verification.
- Fenced idempotent effect broker with semantic readback.
- Cancellation and external-effects-off defaults.
- Minimal HTTP API and health/readback endpoint.
- Container hardening and deterministic standard-library tests.
- Owner-authenticated, monotonic objective contracts and supersession.
- Anti-dilution comparison for requirements, tests, invariants and prohibited substitutes.
- A completion theorem that returns `BLOCKED_INCOMPLETE` until all proofs hold.
- OPA, durable-workflow, SPIFFE identity and Kubernetes production contracts.
- Fail-closed mTLS with CA validation and exact URI-SAN SPIFFE authorization.

OpenRouter is disabled by default. No production credential, provider call or external effect is part of this qualification. Kubernetes, OPA, Temporal, SPIFFE/SPIRE and production rollback still require live infrastructure; their absence is an open operational requirement, not a completed substitute.

### SPIFFE mTLS host proof

Set `SEB_MTLS_REQUIRED=1` and the SVID, key, bundle, and exact allowed identity
variables in `.env.example`. A SPIRE Agent and `spiffe-helper` can materialize
and rotate those files from the standard Workload API. SEB refuses to start if
the files are absent, requires a CA-valid client certificate, and permits a
mission only when its sole URI SAN exactly matches the configured SPIFFE ID.

Run `PYTHONPATH=. python3 proofs/prove_spiffe_mtls.py` (requires `openssl`). It
creates ephemeral certificates and proves that an intended SVID is accepted
while a CA-valid rogue SVID in the same trust domain is denied. This proves the
host enforcement mechanism, not deployment of a production SPIRE control plane.

## Run

```bash
python3 -m seb.api
```

The service defaults to the real OPA backend and fails closed on connection,
HTTP, JSON, schema, or contradictory-decision errors. For isolated development
tests only, set both `SEB_ENVIRONMENT=development` and `SEB_POLICY_BACKEND=local`.

Health:

```bash
curl http://127.0.0.1:8080/health
```

Execute a mock mission:

```bash
curl -X POST http://127.0.0.1:8080/v1/missions/execute \
  -H 'Content-Type: application/json' \
  -d '{"mission_id":"demo-1","objective":"prove the local route","prompt":"hello","acceptance_tests":["accepted=true"]}'
```

## Test

```bash
python3 -m compileall -q seb tests
python3 -m unittest discover -s tests -v
```

## Container

```bash
docker compose build
docker compose up -d
docker compose down
```

## Recovery

The ledger is the authoritative execution history. Verify it before replay. A failed semantic result quarantines only its provider route. External effects are disabled unless a separately governed runtime constructs an `EffectBroker(external_effects_enabled=True)` and supplies a verified operation/readback pair.

Rollback this reference build by stopping its container and restoring the prior packaged release. No database migration or external state is created by the default configuration.

## Debugging

| Symptom | Cause | Resolution |
|---|---|---|
| `OpenRouter credential unavailable` | External route enabled without a bound secret | Leave the route disabled or bind a secret through the target runtime's secret manager |
| Provider quarantined | Malformed or semantically invalid output | Inspect `ROUTE_FAILURE`/`MISSION_QUARANTINED`, repair adapter or prompt contract, then run two clean canaries |
| Ledger integrity error | Event mutation, truncation or chain mismatch | Freeze writes, preserve the file, restore from verified backup and replay accepted events |
| HTTP 400 | Invalid or incomplete mission input | Validate required MissionIR fields and payload size |
| All routes failed | No eligible provider produced a valid response | Inspect typed failures; retry only transient routes and keep policy refusals intact |

## Maturity

`IMPLEMENTED_LOCAL / TESTED_LOCAL` after the included verification suite passes. A hosted claim additionally requires: an immutable OPA image digest; exact Rego-to-ConfigMap byte/digest attestation; an OPA readiness readback; allow and deny API canaries; an OPA-stop canary proving zero provider calls and an `opa_unavailable_or_invalid` ledger decision; restart/persistence health; and rollback to the prior revision with readback. Source and local tests are not deployment proof.
