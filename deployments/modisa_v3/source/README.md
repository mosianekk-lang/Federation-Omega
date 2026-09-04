# MODISA Agent Recovery v3.0

This is a public-safe, offline-qualified recovery of the MODISA–EvidenceOps
Sovereign Legal Intelligence OS. It was reconstructed from the qualified source
tree at Federation Omega commit
`9386804713512313f6aaa7cc0912d22dcc3135c0`. Version 2.1 modernized the Agents
SDK dependency contract, version 2.2 added the pinned P12 composition adapter,
version 2.3 added the admitted CFBE binding and webhook security repair, and
version 2.4 added a tested Google Secret Manager resolver plus an Apps Script
`MODISA-HMAC-V2` migration package, and version 2.5 adds a fail-closed shared
Redis nonce-store adapter for multi-instance replay protection. Version 2.6
adds a provider-neutral, default-inert Redis live-qualification and failover
runner with hash-bound receipts.

Version 2.7 adds CFBE runtime hardening: workflow fencing tokens and state CAS,
case-level behavioral evaluation, privacy-safe Agents SDK defaults, a generic
claim-versus-fruit completion gate, directive-closure controls, execution budgets,
circuit breaking, and a trusted-verifier boundary for Redis live promotion.
Version 2.8 adds whole-directive orchestration completeness: exhaustive element
coverage, full ready-set fan-out, local blocker isolation, lawful route ranking,
automatic resume triggers, evidence-backed terminal states and an anti-dilution
completion gate. The authoritative current qualification is
`V28_QUALIFICATION.md`; earlier version reports are retained as historical
baseline evidence only.

Version 3.0 adds the Sovereign Execution Fabric: immutable mission graphs,
concurrent full-ready-set execution, a durable hash-chained SQLite/WAL journal,
crash replay with proof rehydration, lane-local repair, capability-aware provider
failover, independent proof verification and signed, exactly-once external-effect
approval. See `ULTIMATE_VERSION.md` and `V30_QUALIFICATION.md`.

Version 2.6 preserves the proof-bound EvidenceOps v7.2.2 P12 checkpoint adapter
and adds two local repairs: a dependency-decoupled BCO–MODISA–SOL 6.1 cognitive
binding and signed-webhook authentication with rotatable secret references and
durable replay prevention.

## Canonical truth correction

The two observed Airlock failure notices were intermediate events, not the final
state. The initial policy referenced dependency identities that Airlock could
not resolve. A later revision changed the dependency to the registered `CFBE`
capability, and the binding was subsequently admitted in Federation Omega merge
commit `1e300df555a44092ec54ef0681bd9fe5d6aeaf06` (PR #1029).

This package reuses that admitted contract. It does not import the Federation
runtime packages directly: `CognitiveBindingAdapter` accepts the stable `CFBE`
handle, checks the objective and authority envelope, then appends and verifies a
MODISA HMAC proof. See `MODISA_CANONICAL_TRUTH_MAP.md`.

## Webhook security repair

`modisa_v2.webhook_auth` supersedes the documented shared-token pattern with
`MODISA-HMAC-V2`: key-ID and SHA-256 body binding, timestamp bounds, unique nonces,
constant-time signature comparison, and selectable SQLite or shared Redis replay rejection.
Configuration accepts `env://` plus strict, numerically pinned
`gcp-secret://projects/.../versions/<number>` references. The Google adapter
uses an exact resource allowlist, bounded no-implicit-retry access, response and
CRC32C verification, and a thread-safe one-read memory cache. The Apps Script
source independently reproduces the canonical bytes and checks the exact
no-dispatch receipt. Raw or embedded secrets are rejected, and there is no V1
or bearer-token fallback. Redis uses one atomic `SET NX EX`, zero retries after
an uncertain write, TLS-only configuration, hashed keys, bounded TTLs, and no
SQLite fallback. No Apps Script, Redis, or cloud surface was changed.

## EvidenceOps v7.2.2 composition adapter

`modisa_v2.adapters.EvidenceOpsV722Adapter` runs the exact pinned P12 worker as
a local crash/resume and integrity sidecar for a leased MODISA workflow. The
adapter creates an atomic, idempotent receipt bound to the matter, mission,
workflow, worker lease, and workflow-state hash. It rejects source drift,
receipt tampering, authority widening, state collisions, wrong lease owners,
and incomplete P12 proof.

The adapter intentionally does not complete or mutate the MODISA workflow. It
does not run a model, process legal evidence, deploy a provider service, or
authorize an external action. Those responsibilities remain with MODISA's
existing workflow, proof, approval, and release layers.

## Verified recovery scope

- deterministic legal claim, evidence, proof, approval, release and workflow controls;
- encrypted content-addressed evidence vault;
- recursive EML/ZIP inventory with abuse limits;
- seven-role adversarial council decision contract;
- FastAPI contract, JWT matter scopes and audit chain;
- OpenAI Agents SDK construction against `openai-agents 0.22.0` and
  `openai 3.7.0`, without a model request;
- source provenance and capability mapping against EvidenceOps v7.2.2;
- proof-bound cognitive decision admission through the registered `CFBE` handle;
- secret-reference-only HMAC webhook verification with durable replay protection.
- strict Google Secret Manager resolution and cross-language Apps Script signing tests.
- shared atomic Redis nonce adapter with 64-way concurrency, cross-app replay,
  timeout/uncertainty, secret-safety, and fail-closed integration tests.
- whole-directive orchestration completeness with blocked-lane isolation,
  zero-burden route selection and proof-bound closure receipts.

The included `LIVE_DEPLOYMENT_RECEIPT.json` contains a historical v2.0 receipt
with an explicit supersession marker. It is not current deployment proof.

## Current boundary

This recovery is `TESTED_LOCAL_OFFLINE / NOT_DEPLOYED / LIVE_REDIS_UNPROVEN /
READY_FOR_AUTHORIZED_LIVE_QUALIFICATION`. It is not deployed, has no current
provider trace, performs no external legal action, and includes no credentials
or private evidence. The external-action kill switch remains disabled by
default.

`modisa-redis-qualify` is plan-only and has zero network or provider effects.
The Python live path requires separately supplied authorization, writer,
observer, and controller adapters. See `REDIS_LIVE_QUALIFICATION.md`.

## Requirements

- Python 3.11 or newer
- `uv`

## Setup and test

```bash
uv sync --extra dev
uv run python scripts/init_secrets.py --target .env.local
uv run python -m pytest -q
uv run python evals/run_local.py
uv run python scripts/build_manifest.py
```

The core lock records the Redis 8.1 dependency graph; the Redis adapter remains
optional and lazy-loaded. A separately authorised hosted-runtime qualification
must install `requirements-gcp.txt` and `requirements-redis.txt`, prove ADC/IAM
and a TLS/ACL/noeviction/persistence/HA Redis service, then record provider-native
readback. The supplied Dockerfile includes both requirements files but was not
built or deployed in this offline cycle.

`.env.local`, runtime state, evidence, build output and virtual environments
are excluded from integrity manifests and release archives.

## Run the offline-capable API

```bash
PORT=8421 uv run python main.py
curl -fsS http://127.0.0.1:8421/health
```

Without `OPENAI_API_KEY`, health is deliberately `degraded` and live agent
missions stop at the credential boundary. The deterministic API planes remain
testable.

## Live model boundary

A live Agents SDK run requires an explicitly authorized credential decision and
a separately qualified provider route. Do not place API keys in source,
manifests, archives or command output.

## Key records

- `RECOVERY_STATUS.md` — current qualification results and limitations
- `CFBE_MARKET_LEADER_AUDIT.md` — representative market benchmark and capability harvest
- `ORCHESTRATION_COMPLETENESS.md` — v2.8 execution and anti-dilution contract
- `ULTIMATE_VERSION.md` — v3.0 architecture, failure model and operating boundary
- `V30_QUALIFICATION.md` — v3.0 qualification and promotion gates
- `V28_QUALIFICATION.md` — current local qualification truth
- `CAPABILITY_MIGRATION_MAP.md` — MODISA versus EvidenceOps v7.2.2
- `MODISA_CANONICAL_TRUTH_MAP.md` — reconciled Gemini/Drive, Gmail, Git and local state
- `SECURITY_REPAIR.md` — signed-webhook contract and supersession boundary
- `GSM_APPS_SCRIPT_MIGRATION.md` — provider and Apps Script migration contract
- `REDIS_NONCE_STORE.md` — shared replay contract, proof boundary and production blockers
- `INDEPENDENT_REVIEW.md` — security, concurrency and release challenge results
- `COGNITIVE_BINDING_QUALIFICATION.md` — dependency and proof-adapter contract
- `BUILD_CONTRACT.json` — MODISA Code-Forge v3.3 completeness contract
- `FORMATION_SPEC.md` — authority, side-effect and stop boundaries
- `PROJECT_MEMORY.md` — durable technical decisions
- `AI_HANDOFF.md` — exact continuation commands and proof gates
- `MANIFEST.sha256` — release-tree hashes generated after verification

## Deployment and rollback

No deployment is included in this recovery. A future deployment must use a
separate Formation permit, provider-native readback, health check, persistence
check and rollback canary. Rollback before deployment is simply removal of the
candidate runtime while retaining this immutable recovery archive and its hash.
