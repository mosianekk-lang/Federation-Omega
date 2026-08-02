# EvidenceOps Capability Heartbeat — verified-v4 integration

This package is a local, read-only, recommendation-only heartbeat foundation with compatibility facades for the existing EvidenceOps catalogue, SQLite system, Master Bible federation, CLI and scheduler.

Its truthful maturity is **`DURABLE_FOUNDATION_IMPLEMENTED_NOT_ATTACHED`**. It has no provider-authoritative active-chat inventory, per-chat emitter coverage, unsolicited injection, system-wide awareness, hosted heartbeat API, or heartbeat MCP tool. Source files, catalogues, manifests and session connector labels do not prove those capabilities.

## One authority

`VerifiedV4Authority` is the only component allowed to:

- apply heartbeat recommendation policy;
- bind owner, matter, classification, authority and control generation;
- create or forward a signed envelope;
- verify complete root-to-current lineage;
- accept ingress and issue a destination-signed receipt;
- perform registry or respawn semantic readback.

`CapabilityHeartbeatEngine`, `BibleFederation`, `EvidenceOpsHeartbeatSystem`, the standalone CLI and the external scheduler are facades. They cannot create authority from catalogue availability, an unhosted source, a session connector label, a scheduled run, a static fixture, an MCP declaration or an API route claim.

```text
explicit on-input caller
  -> synthetic/local catalogue observation
  -> verified-v4 A0 aggregator
  -> registered runtime signer
  -> complete signed lineage (maximum 3 hops)
  -> fresh destination registration
  -> destination-signed receipt
  -> atomic metadata-only local record
```

## Non-negotiable controls

- Heartbeat authority is exactly `A0`; no effectful route can be selected or executed.
- Children inherit owner code, matter code, classification floor, schema, adapter version, signing version, control generation and an authority ceiling that cannot widen.
- Runtime signers are injected and must exactly match every fresh registry record, including signing version, key fingerprint and rotation generation.
- Forwarded ingress requires the complete signed lineage. A digest-only or child-only envelope is insufficient.
- Stop advances generation and fences earlier registrations, envelopes, receipts, leases and delegations.
- Envelope identity and idempotency bind the complete canonical payload. Identical replay is stable; conflicting replay fails closed.
- Receipt verification binds the exact accepted envelope, scope, generation, destination signer, registration window and explicit current time.
- Respawn verifies policy, every fresh registry record, ledger tail, parent transaction, receipts and false live-awareness flags.
- No turn payload may contain task summaries, prompts, messages, chats, documents, evidence, transcripts, personal data, legal content or credentials. Only codes, hashes, enums, timestamps, counts and signed receipts cross the boundary.
- JSON rejects duplicate keys. Local paths reject escapes and symlink traversal.
- Static JSON is marked `SYNTHETIC_STATIC_*` or `fixture_only`; it never authorizes ingress.
- Scheduler and adapter-remediation methods are inventory-only. They do not rank, advance, retry, authorize, dispatch or execute work.

Namespaced pseudonymous syntax constrains representation but cannot prove caller intent or guarantee that semantics were never embedded in a syntactically valid code.

## Preserved scaffolding

- `engine.py` inventories existing Federation Omega, Secondary Brain, MODISA, EvidenceOps and supporting catalogue evidence. It needs an injected `VerifiedV4Authority` before returning recommendations.
- `system.py` retains local SQLite transactions, outbox receipts, connector PRE/POST records and surface inventory. Turn ingress additionally requires a complete typed signed lineage.
- `bible_federation.py` exposes child readback, signed heartbeat, forwarding, acceptance and respawn facades; it owns no independent policy.
- `scheduler/run_scheduler.py` emits catalogue and surface inventory only, with zero recommendation or ingress authority.
- `system_cli.py` and `python -m evidenceops.capability_heartbeat` are inventory/readback tools. The static turn example cannot be ingested.

The repository currently contains no implemented heartbeat endpoints in `evidenceops/runtime_service/main.py` and no implemented heartbeat tools in `evidenceops-mcp-adapter/src/server.ts`. Authentication, API schemas, MCP tools, durable production storage, deployment, provider-backed canaries and live attachment remain explicit later obligations.

## Verification

From the repository root:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s evidenceops/capability_heartbeat/tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_atomic_transactions tests.test_connector_foundry tests.test_connector_foundry_google_drive tests.test_ecasp tests.test_innovation_engine_registry tests.test_operation_idempotency tests.test_provenance_passport tests.test_runtime tests.test_slrk tests.test_wif_hardening
PYTHONDONTWRITEBYTECODE=1 python3 evidenceops/capability_heartbeat/static_verify.py
PYTHONDONTWRITEBYTECODE=1 python3 evidenceops/capability_heartbeat/validate_build_contract.py evidenceops/capability_heartbeat/BUILD_CONTRACT.json --require-proof
PYTHONDONTWRITEBYTECODE=1 python3 -m compileall -q evidenceops/capability_heartbeat scheduler/run_scheduler.py
PYTHONDONTWRITEBYTECODE=1 python3 evidenceops/security/public_repository_leak_guard.py
```

The original 24-test behavior audit is recorded in `TEST_COVERAGE_MAP.md`.

## Activation closure

Live attachment is a separate Formation mission. It requires implemented authenticated runtime and MCP contracts, injected non-static signers, provider-authoritative inventory, registered current emitters, exact reconciliation, privacy/stop/rotation tests, durable storage, two later clean cycles, a real respawn canary and provider-backed round-trip readback. Until then, all live-awareness flags remain false.
