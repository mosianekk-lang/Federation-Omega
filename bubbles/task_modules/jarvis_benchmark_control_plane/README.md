# JARVIS Benchmark Control Plane

This package is lane one of the JARVIS mission rebase: an evidence-gated system that benchmarks the current JARVIS state against current public standards, ranks improvement opportunities, records measurable deltas and refreshes its knowledge registry without silently expanding authority.

## What is implemented

- A registry of official Microsoft, Alphabet/Google, SoftBank, NIST, ISO, SLSA, OWASP, DORA and OpenAI sources with publisher, canonical URL, verification time, freshness SLA, dimensions and evidence grade.
- A fail-closed freshness engine. Stale critical evidence changes the result to `DIAGNOSTIC_ONLY_STALE_EVIDENCE`; it never presents a stale comparison as current.
- Truth-state weighting that distinguishes `DESIGNED`, `IMPLEMENTED`, `TESTED`, `REGISTERED`, `AUTHORIZED`, `READY`, `DEPLOYED` and `PROVEN`.
- Deterministic Mission Utility Score:

  `5O + 4D + 3I + 3R + 3A + 2V - 2G - 2L`

- A three-opportunity fan-in, matching the one-primary-path rule. Rankings advise; they do not grant authority or take effectful action.
- An append-only JSONL learning ledger with SHA-256 payload hashes, a hash chain, cross-process lock, write-through flush, idempotency and tamper detection.
- A bounded HTTPS collector that only fetches registry-fixed URLs, rejects redirects and oversized content, and records hashes rather than source bodies.
- A loopback-first HTTP API, authenticated single write path, dependency-free CLI, optional continuous refresh daemon and container candidate.
- A public/private evidence boundary. Private internal Microsoft, Alphabet or SoftBank capability parity is explicitly score-excluded unless auditable evidence becomes available.

## Run and verify

Requires Node.js 24 or later. There are no third-party runtime dependencies.

```bash
npm test
npm run validate
npm run demo
npm start
```

The server binds to `127.0.0.1:8787` by default. Its write API is disabled unless `JARVIS_BENCHMARK_ADMIN_TOKEN` is set. A non-loopback bind also requires `JARVIS_ALLOW_REMOTE_BIND=true` and a token of at least 24 characters.

## CLI

```bash
node src/cli.js validate
node src/cli.js evaluate --input examples/jarvis-state.sample.json
node src/cli.js opportunities --input examples/jarvis-state.sample.json
node src/cli.js refresh-plan
node src/cli.js ledger-verify
node src/cli.js cycle-commit --input examples/jarvis-state.sample.json --idempotency-key cycle:2026-08-22:001
```

`cycle-commit` is a local operator action. Network/API commits use `POST /v1/cycle/commit` and require the bearer token.

## HTTP routes

| Method | Route | Effect |
|---|---|---|
| GET | `/health` | Runtime, ledger and scheduling state |
| GET | `/v1/registry` | Source registry and freshness assessment |
| GET | `/v1/refresh/plan` | Due/stale refresh plan |
| GET | `/v1/ledger/verify` | Hash-chain verification |
| POST | `/v1/evaluate` | Dry-run benchmark |
| POST | `/v1/opportunities` | Dry-run ranked opportunities |
| POST | `/v1/cycle/commit` | Authenticated, idempotent ledger commit |

## Continuous refresh

`node src/daemon.js` performs an immediate due-source check and repeats at `JARVIS_REFRESH_INTERVAL_HOURS` (default 24). Each source read is bounded and identity-pinned. `node src/daemon.js --once` executes a single bounded cycle. Creating a file named `STOP` activates the local stop switch.

The daemon exists and is tested through its component contracts, but it is **not scheduled or deployed by this package build**. A continuously running production state requires an authorized host, secrets, scheduler and deployment readback.

## Knowledge transaction

Each committed cycle contains the refreshed registry snapshot, source changes, current benchmark, top opportunities and before/after delta. The ledger is the source of truth; on restart the runtime restores the latest committed registry and evaluation. This makes a crash after a commit recoverable without rewriting history.

## Readiness interpretation

- `INITIAL`: scored public-evidence baseline exists.
- `FOUNDATIONAL`: weighted score reaches 50.
- `OPERATIONAL_READY`: score reaches 70 and critical dimensions clear minimum proof.
- `PRODUCTION_PROVEN`: score reaches 85 and critical dimensions are deployed/proven.
- `FRONTIER_PROVEN`: score reaches 95 and every critical dimension is proven.
- `DIAGNOSTIC_ONLY`: current-source evidence is insufficient.

These are local decision thresholds, not claims of independent certification or superiority over private company teams.

## Federation central-task-module integration

The source candidate is registered behind the existing `Bubbles Command Bus`; it does not add a workflow file or expand the Airlock allowlist. The Python adapter exposes only four read-only actions against the committed public fixture: validate, snapshot, opportunity ranking and refresh planning.

Arbitrary paths, URLs, private evidence payloads, cycle commits, network refreshes, server/daemon startup and provider effects are rejected at this public command boundary. Each invocation uses an ephemeral ledger path and returns a truth-bounded JSON receipt. Full private JARVIS benchmarking remains in the separately governed private runtime.

`FEDERATION_INTEGRATION.json` binds the exact stacked PR lineage, current main SHA, Airlock policy and central workflow blob used for this candidate. It is source evidence, not a merge, deployment or production proof.
