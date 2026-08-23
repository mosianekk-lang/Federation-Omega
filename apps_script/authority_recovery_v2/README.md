# SOVARA Apps Script Authority Recovery v2

## State

`TWO_PLANE_SOURCE_CANDIDATE_VERIFIED / LIVE_FLEET_UNCHANGED / PROVIDER_DEPLOYMENT_UNEXECUTED`

This source candidate recovers the useful queue, status, backup, project-source, immutable-version, deployment and rollback capabilities identified in the protected fleet backup without preserving its public privileged monolith, default approval bypasses, raw authentication persistence, global handler collisions or legacy-project authority ambiguity.

## Source anchor

- backup contract: `FO_GAS_FLEET_RESTORABLE_BACKUP`
- backup run: `FLEETWEEKLY-20260718-181318-5BXX66`
- declared source SHA-256: `2e80636313ba1942ac80d0de687bf465d1472f998a0bc071d5e2d93adfe33248`
- raw wrapper SHA-256: `3af2057a8fd0ee98fca08493f4b0e2405e86484c0663c53740af63c9f076082f`

The producer's canonicalization algorithm for the declared source hash was not present. The mismatch between the declared hash and tested wrapper/project serializations remains `ALGORITHM_UNSPECIFIED_UNVERIFIED`; it is not represented as corruption evidence.

## Two-plane architecture

### Public gateway

The public project has exactly one `doGet` and one `doPost`, no explicit OAuth scopes, no Google Cloud or Apps Script project-management authority, and only two signed read-only actions: `STATUS` and `CHALLENGE`.

Every POST binds version, request ID, action, canonical target, timestamp, nonce and payload under HMAC-SHA256. A locked, bounded Script Properties ledger rejects replay. Secret-bearing keys, credential-shaped values, excessive depth and oversized bodies fail closed. Public responses expose no spreadsheet, runtime, deployment or provider identity inventory.

### Private admin plane

The private project has no web entry point. Invocation requires a separately authenticated Apps Script API execution route. It preserves a namespaced, backup-first ARCHON source manager and requires a complete `APPS_SCRIPT_ADMIN_COMPOSITE` provider receipt proving both:

1. scripts.run/common-standard-Cloud-project/API-executable relationship; and
2. Apps Script project-management/content/deployment relationship.

Mutation also requires a fresh, one-use effect permit bound to the exact transaction, mutation-intent SHA-256, canonical target, expected before/after project hashes, provider receipt, rollback reference and semantic-readback plan.

Neither receipt is trusted merely because its hash is stored inside the same script. The admin plane sends only hashes and stable evidence references to a pinned HTTPS verifier and requires a challenge-bound response from the configured verifier identity. No raw source, token, secret or credential value is sent to that verifier.

## Transaction sequence

`SIGNED REQUEST → EXTERNAL ADMISSION → CURRENT HASH → PROPOSED HASH → ONE-USE PERMIT CONSUMPTION → EXACT-READBACK BACKUP → SOURCE UPDATE → SOURCE HASH READBACK → IMMUTABLE VERSION → DEPLOYMENT CONFIG READBACK → OPTIONAL EXTERNAL SEMANTIC READBACK → AUDIT`

A no-change result returns before permit consumption or provider writes. A failed mutation restores the exact-readback backup; a failed rollback restores its safety backup. V2 backups are self-hash bound and downloaded/read back immediately after creation. Legacy V1 backups require an explicitly permit-bound `allowLegacyBackup=true` request.

## Corrections beyond the first recovery draft

- replaced same-project “external” hash anchors with a pinned independent verifier contract;
- bound provider receipt and effect permit to transaction, request and source hashes;
- added durable one-use permit replay rejection;
- removed a non-reentrant nested-lock path during permit consumption;
- made no-change requests provider-write free;
- added exact backup-file readback and self-hash verification;
- made post-effect verification action-aware for both apply and rollback;
- pinned verifier identity as well as host;
- rejected redirects on authenticated Apps Script API requests;
- removed unnecessary `cloud-platform` authority from the private source manager and all explicit OAuth scopes from the public gateway;
- replaced active-spreadsheet assumptions with an explicit audit-spreadsheet ID.

## Local evidence

- bundle-aware authorization gate: 18/18 tests passed;
- public candidate source audit: `SOURCE_REVIEW_PASS`, zero findings;
- private candidate source audit: `SOURCE_REVIEW_PASS`, zero findings;
- Node HMAC/replay/tamper/permit security contract: passed;
- concatenated JavaScript syntax checks: passed;
- Python compilation: passed;
- protected backup audit under gate v2.1: `SECURITY_HOLD`, 22 findings (15 critical, 5 high, 2 medium);
- static defect-class coverage: 16 classes, 5.333333× the prior gate's best-case manual-concatenation class coverage.

The 5.333333× result is limited to static defect-class coverage on this supplied backup. It is not evidence of live provider authority, deployment quality, operational speed, production reliability or future intelligence gain.

## Truth boundary

This directory is public-safe source, tests and governance only. It does not create an Apps Script project, bind a standard Cloud project, enable an API, issue a Google token, expose a secret, mutate the live fleet, deploy a web app, change traffic, grant IAM, or certify provider authority. The legacy read/status route remains unchanged until a separately authenticated provider canary proves the replacement and rollback.
