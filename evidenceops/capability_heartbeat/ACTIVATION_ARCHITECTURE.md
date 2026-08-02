# EvidenceOps heartbeat activation architecture

Status: **IMPLEMENTED AND LOCALLY TESTED; NOT REGISTERED, AUTHORIZED, READY,
DEPLOYED OR PROVIDER-PROVEN**.

This document defines the bounded activation layer around the existing
`VerifiedV4Authority`. It does not change that foundation's A0-only authority,
create live-awareness authority, or claim access to an authoritative active-chat
inventory. The activation layer is metadata-only. It must reject raw prompts,
messages, documents, evidence, transcripts, legal content, personal data and
credentials.

## Trust boundaries

```text
OAuth 2.1 client
  |  Authorization: Bearer <external access token>
  |  audience = public MCP resource URI
  v
PUBLIC TOOL-ONLY MCP GATEWAY
  - publishes Protected Resource Metadata
  - verifies external issuer, signature, audience, expiry and tool scopes
  - never forwards the external token
  - exposes bounded search/fetch/status/emitter/emit tools
  |
  |  X-Serverless-Authorization: Bearer <Google service identity token>
  |  audience = exact private heartbeat API URL
  |  X-EvidenceOps-Internal-Auth: <named Secret Manager value>
  v
PRIVATE HEARTBEAT API
  - Cloud Run IAM is a required platform gate, not application-proven state
  - defense-in-depth internal token is independently verified
  - validates metadata-only typed requests
  - delegates all policy/signing/receipt decisions to VerifiedV4Authority
  v
DURABLE EVENT-STORE INTERFACE
  - immutable object-per-event create with generation precondition
  - deterministic event identity and exact readback
  - no overwrite, raw body or secret persistence
```

The two bearer audiences are deliberately different. The public gateway accepts
only an authorization-server token whose `aud` is its configured MCP resource.
The private API accepts only a Google-issued service identity token whose `aud`
is the exact private service URL. `X-Serverless-Authorization` keeps Cloud Run's
identity token separate from application authorization. Token passthrough,
audience substitution, wildcard audiences and reuse of the inbound OAuth token
for the private hop are prohibited.

## Components and contracts

### Existing verified-v4 authority

`evidenceops/capability_heartbeat/authority.py` remains the sole authority for
A0 recommendation policy, registered signer binding, complete lineage,
destination acceptance, signed receipts and semantic readback. The activation
services are adapters. They may not implement an alternative policy or widen
authority.

### Private heartbeat API

The Python API is the canonical internal wire contract. The MCP gateway adapts
its connector-oriented `search`, `fetch` and `heartbeat_emit` inputs and results
to that single contract: `POST /v1/search`, `GET /v1/resources/{id}`,
`POST /v1/ingest` and `GET /v1/readback/{idempotency_hash}`. Compatibility
aliases or a second write route are prohibited.

The private API has three application-level readiness conditions:

1. non-fixture verified-v4 runtime configuration and signer material are
   injected by the runtime;
2. the internal request gate is configured and validates; and
3. the configured store reports healthy and production mode rejects local or
   in-memory fixture durability.

Health output is minimal and secret-free. Readiness must remain false when a
production dependency, runtime identity, signer, store or readback is missing.
Requests carry a bounded correlation code and typed pseudonymous metadata only.
Invalid input, replay conflict, stale registration, bad receipt, authorization
failure, timeout and partial write all fail closed.

Cloud Run IAM validates the Google service identity token before a request
reaches the application. The API code cannot prove that platform enforcement;
platform policy and an authenticated provider canary must be read back
separately. Likewise, an immutable write plus exact readback is a later canary
gate, not a side effect of the readiness endpoint.

### Public MCP gateway

The gateway is a tool-only Streamable HTTP MCP server. Private-data tools
declare OAuth security schemes and the minimum required scopes. The resource
server publishes Protected Resource Metadata and returns standards-compliant
authentication challenges. It verifies token issuer, signature, audience,
expiry and scopes locally against configured authorization-server metadata.

The gateway preserves the standard read-only `search` and `fetch` discovery
shape and adds bounded heartbeat status, emitter registry and metadata emission
operations. An emit result is a signed receipt or a typed failure; route
invocation is not evidence of acceptance. The gateway must not expose operator
actions that are absent from the live operator allowlist.

### Durable storage interface

Production durability is an interface, not a deployment claim. Its contract is:

- `append(event_id, canonical_metadata, expected_absent=true)` is atomic;
- an identical replay returns the already-stored digest and readback;
- a changed replay under the same identity returns a conflict;
- `read(event_id)` returns canonical metadata and integrity fields;
- `health()` proves the configured backend is reachable without writing raw
  content;
- retention, hold and deletion policy are external governed configuration; and
- logs contain codes, hashes, enums, timestamps and counts only.

A Google Cloud Storage binding may use one immutable object per event with
`if_generation_match=0`. Local memory or local files are test fixtures and must
never satisfy production readiness.

## Emitter registry boundary

Registration proves only that a bounded emitter record exists and is fresh. It
does not prove that every active chat has an emitter, that unsolicited messages
can be injected, or that Federation Omega, Secondary Brain, MODISA, EvidenceOps
or any Bible node has system-wide awareness. Provider-authoritative inventory,
exact reconciliation and per-provider delivery readback remain separate future
proof obligations.

## Data minimization

Allowed fields are pseudonymous codes, typed enums, hashes, timestamps, counts,
capability identifiers, key fingerprints, signed lineages and receipts. The API,
gateway, durable-store adapter and logs must reject or redact raw text and
credentials before persistence. The boundary is structural; syntactically valid
codes cannot by themselves prove that a caller did not embed forbidden
semantics, so callers remain subject to the same metadata-only contract.

## Failure, replay and cancellation

- Every request has a correlation code and deterministic idempotency identity.
- Timeouts are bounded; retries are limited to safe idempotent reads or
  identical append replays.
- A partial write is not success until exact readback matches the canonical
  digest.
- Changed replay, stale state, scope failure, dependency failure and missing
  configuration are terminal typed failures.
- Stop-generation advancement fences earlier registrations, envelopes,
  receipts, leases and delegations.
- No queue, worker or scheduler activation is implied by this HTTP/MCP layer.

## Deployment, canary and rollback gates

The repository CI is deliberately non-deploying. A later Formation mission may
authorize at most a bounded zero-traffic canary only after all of the following
are independently read back:

1. exact Google Cloud project, project number, region and service names;
2. current GitHub OIDC pool, provider, repository and branch conditions;
3. distinct deployer, public-gateway runtime and private-API runtime identities,
   plus a provider canary proving that the private service rejects an
   unauthorized caller and accepts only the intended gateway identity;
4. least-privilege IAM, including only the required private API invoker and
   named secret access;
5. billing/quota status and an approved zero-new-recurring-cost envelope;
6. secret versions exist without secret values appearing in output;
7. immutable image digests and the previous healthy revision are recorded;
8. ingress, egress, OAuth metadata, issuer, audience and scope configuration;
9. privacy, authorization-denied, replay, stop, timeout and dependency-failure
   canaries; and
10. exact rollback commands plus post-rollback semantic readback.

The canary must receive zero traffic until health, readiness and internal
service-to-service authentication pass. Promotion requires a separate current
Formation permit. Rollback restores the exact prior revision or traffic split,
then verifies health and semantic state. CI success, source publication,
resource creation or a healthy HTTP response alone never proves attachment or
end-to-end heartbeat operation.

## Cost and truth boundary

This code-only activation adds no cloud resources and authorizes no spend. Local
tests and repository CI use existing bounded execution only. Any cloud resource,
secret, IAM mutation, build, deployment, traffic shift or recurring cost is
outside this contract until separately authorized and proven.

Truthful state for this activation is:

- `DESIGNED=true`
- `IMPLEMENTED=true`
- `TESTED=true` only for the exact local evidence recorded in
  `ACTIVATION_BUILD_CONTRACT.json`
- `REGISTERED=false`
- `AUTHORIZED=false`
- `READY=false`
- `DEPLOYED=false`
- `PROVEN=false`

This is not a claim of active-chat coverage, universal heartbeat attachment,
system-wide awareness, provider registration or live Google Cloud operation.
