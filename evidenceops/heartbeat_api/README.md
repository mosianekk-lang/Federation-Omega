# EvidenceOps Private Heartbeat API

This package exposes the existing `VerifiedV4Authority` through one private,
metadata-only HTTP boundary. It never reads raw chat, evidence, document,
account, contact, credential, or secret content. Its authority ceiling is A0
recommendation/observation only.

## Truth boundary

Maturity is `IMPLEMENTED_NOT_DEPLOYED`. The package does not prove a live
Master Bible attachment, active-chat inventory, per-chat emitter fleet,
unsolicited injection, cloud IAM, or durable cloud storage. Development mode
can use memory or create-only local files. Production readiness additionally
requires an injected external immutable object store plus independent provider
registry and storage proof; environment-synthesized registry metadata and
signer injection alone can never make production ready.

## Authentication

Cloud Run should remain private and require its IAM identity token. The API then
requires a second, injected application header on every route except health:

```text
X-EvidenceOps-Internal-Auth: <injected value of at least 32 UTF-8 bytes>
```

The value is compared in constant time and is never logged or returned. This
header is a defense-in-depth seam; it does not replace Cloud Run IAM.

## Routes

- `GET /health` — minimal unauthenticated liveness only.
- `GET /ready` — authenticated, `200` when ready and `503` otherwise.
- `GET /v1/status` — authenticated authority, store, maturity, and false-live-flag readback.
- `POST /v1/search` — authenticated structured emitter/event search.
- `GET /v1/resources/{resource_id}` — authenticated emitter or direct indexed signed-event fetch.
- `POST /v1/ingest` — the only ingest path; closed A0 metadata schema, root-signed envelope, destination-signed receipt, create-if-absent persistence.
- `GET /v1/readback/{idempotency_hash}` — authenticated signature, receipt, object-hash, and semantic readback.

Unknown fields, free-form content, PII shapes, credentials, non-A0 authority,
non-root origin, stale registrations, stopped generations, invalid runtime
modes, changed idempotency replays, and unavailable durable dependencies fail
closed. Validation responses never reflect rejected input.
State-changing request bodies require a valid `Content-Length` and are capped
at 64 KiB before schema processing.

Store enumeration is never used by request paths. Search calls a bounded,
indexed page primitive with a hard maximum of 100 objects; fetch resolves one
immutable resource index and one event object directly. The local development
store bounds startup indexing to 10,000 directory entries and fails closed
rather than silently creating a partial index.

## Runtime configuration

Development environment construction recognizes:

```text
HEARTBEAT_MODE=development|production
HEARTBEAT_INTERNAL_AUTH_VALUE=<injected secret>
HEARTBEAT_ROOT_NODE_ID=NODE-ROOT
HEARTBEAT_ACCEPT_NODE_ID=NODE-EVIDENCEOPS
HEARTBEAT_OWNER_CODE=OWNER-A1B2C3D4
HEARTBEAT_MATTER_CODE=MATTER-B1C2D3E4
HEARTBEAT_CONTROL_GENERATION=0
HEARTBEAT_ROOT_SIGNER_B64=<base64 injected signer bytes>
HEARTBEAT_ACCEPT_SIGNER_B64=<base64 injected signer bytes>
HEARTBEAT_STORE_DIRECTORY=<optional safe local directory>
```

Missing configuration leaves the process healthy but not ready. A malformed
explicit mode is rejected. Signer material must decode to at least 32 bytes.
Root and acceptance nodes must use different material. No signer material is
generated, discovered from a file, or persisted.

## Run and test

From the repository root:

```bash
python -m venv /tmp/evidenceops-heartbeat-api-venv
/tmp/evidenceops-heartbeat-api-venv/bin/pip install -r evidenceops/heartbeat_api/requirements.txt
/tmp/evidenceops-heartbeat-api-venv/bin/python -m unittest discover -s evidenceops/heartbeat_api/tests -t . -v
PYTHONPATH=. /tmp/evidenceops-heartbeat-api-venv/bin/uvicorn evidenceops.heartbeat_api.service:app --host 127.0.0.1 --port 8080
```

The supplied Dockerfile runs as a non-root user. Deployment, IAM, Secret
Manager, external object storage, provider proof binding, canary, traffic
switching, and rollback remain outside this code-only package and are not
claimed complete.
