# Apps Script Authority Recovery v2 — Migration Plan

## Objective

Replace the unsafe privileged monolith with an independently provable two-plane route while preserving the original backup and the serving read/status transport until equivalent canonical replacement proof exists.

## Phase 0 — Source admission

1. Admit this source only after exact-head Airlock, leak, provenance and command-bus controls pass.
2. Preserve the original backup unchanged as evidence and rollback lineage.
3. Keep project `516699068552` transport-only; do not target new IAM, WIF, API, Secret Manager, source or deployment work there.

## Phase 1 — Clean non-serving projects

1. Create a new minimum-scope gateway project from `public_gateway/`.
2. Create a separate private admin project from `private_admin/`.
3. Bind both to the canonical standard Cloud project only after current provider readback proves project `sov-hybrid-suite` / `257649435135`, OAuth consumer, active principal, API state and deployment relationships.
4. Configure only secret references and verifier identity/host metadata; never copy a raw secret into source, Sheets, logs or receipts.

## Phase 2 — Negative and read-only canaries

1. Public gateway: valid challenge, missing signature, invalid signature, stale timestamp, future timestamp, replay, wrong target, secret-shaped payload, oversized body and unsupported action.
2. Private admin: scripts.run relationship, project-management relationship, missing verifier, wrong verifier host/identity, stale provider receipt, tampered receipt, tampered permit, wrong transaction/request hash, wrong expected before/after hash and permit replay.
3. Read-only status/dry-run: exact current source/deployment inventory and deterministic before/after hash calculation.

No mutation proceeds in this phase.

## Phase 3 — Reversible non-serving mutation

1. Use dry-run to calculate exact before/after source hashes for a synthetic non-serving test file.
2. Obtain a fresh provider receipt and one-use effect permit bound to those hashes and the exact transaction.
3. Require external admission verification.
4. Consume the permit under the already-held source transaction lock.
5. create and read back a V2 backup;
6. apply the test-file change;
7. read back exact project hash;
8. create an immutable version;
9. verify deployment configuration only if a non-serving deployment is explicitly included;
10. run external semantic readback when deployment is included.

## Phase 4 — Rollback canary

1. Issue a distinct one-use rollback permit bound to the exact backup ID, current hash and restored hash.
2. Create a safety backup.
3. restore the V2 backup;
4. read back the restored source hash;
5. create an immutable rollback version;
6. verify deployment configuration and external semantics if applicable.

## Phase 5 — Serving cutover

Cut over only after both projects pass the negative, mutation and rollback canaries with independent readback. Keep the legacy bridge available as bounded rollback transport during the observation window. Do not retire it until missed-run recovery, idempotency, semantic receipts and rollback have remained healthy for the defined soak period.

## Stop conditions

Stop and preserve evidence on target/consumer mismatch, missing token/principal, verifier identity mismatch, stale proof, request/hash drift, backup readback mismatch, permit replay, source readback mismatch, deployment mismatch, semantic failure or rollback failure. A transport 2xx or self-written queue row never closes a provider action.
