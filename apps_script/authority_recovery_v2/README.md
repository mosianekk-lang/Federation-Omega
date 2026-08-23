# Federation Omega — Apps Script Authority Recovery v2

## Purpose

This additive source candidate preserves the admitted v1 fleet guard and recovers the useful queue, readback, backup, source-management, versioning and rollback capability identified in the restorable Apps Script fleet while removing the public privileged monolith, default approval substitution, raw authentication persistence, duplicate global handlers and legacy-project authority ambiguity.

The source basis is the owner-supplied `FO_GAS_FLEET_RESTORABLE_BACKUP`, run `FLEETWEEKLY-20260718-181318-5BXX66`, script `1LqRdlFdDlSh79snZYidLk-rdxjR8zGtEnYfkJgB7iA2N98l_yi18Zfeu`. The wrapper bytes have SHA-256 `3af2057a8fd0ee98fca08493f4b0e2405e86484c0663c53740af63c9f076082f`; the backup declares project-source SHA-256 `2e80636313ba1942ac80d0de687bf465d1472f998a0bc071d5e2d93adfe33248`. The producer's canonicalization algorithm is not present, so the declared hash is preserved as a source assertion rather than treated as independently reproduced.

## Architecture

### Public signed gateway

- one `doGet` and one `doPost`;
- `script.external_request` scope only;
- public status exposes no project, runtime, spreadsheet or capability inventory;
- read-only `STATUS` and `CHALLENGE` actions only;
- HMAC-SHA256 over the full canonical envelope;
- canonical target, request ID, timestamp, nonce, action and payload binding;
- bounded durable replay ledger;
- secret-bearing fields and credential-shaped values rejected;
- no IAM, API enablement, source mutation, deployment promotion, Drive or Sheets capability;
- offline Python signer that reads HMAC key material only from an injected value or environment variable and returns no secret.

### Private privileged admin plane

- no `doGet`, `doPost` or public web-app deployment;
- invocation must use a separately authenticated Apps Script API execution route on the canonical standard Cloud project;
- exact composite proof for both `scripts.run` invocation and Apps Script project-management access;
- canonical target `sov-hybrid-suite / 257649435135`;
- legacy `516699068552` retained as transport-only, with `516690968552` and `979287460558` retained as separate OAuth-consumer contexts;
- externally verified provider receipt plus one-use effect permit;
- transaction, canonical mutation-intent, expected-before hash and expected-after hash binding;
- fixed HTTPS verifier host, redirect rejection and one-time challenge response;
- backup before effect, exact source readback, immutable version, deployment configuration readback, external semantic readback when deploying, automatic source/deployment rollback on failure;
- explicit audit spreadsheet and backup folder references; no dependency on an implicit active spreadsheet;
- protected core files and namespace validation.

## Source state

`SOURCE_CANDIDATE_TESTED / PROVIDER_DEPLOYMENT_UNEXECUTED / SERVING_LEGACY_TRANSPORT_UNCHANGED`

The candidate does not create an Apps Script project, OAuth client, token, IAM grant, API enablement, deployment or secret. It does not mutate the serving fleet. Provider promotion requires current Google project, OAuth-consumer, principal, API, deployment and semantic readback proof.

## Local verification

Run:

```bash
python -m unittest -v tests/test_phoenix_provider_cutover_v3_apps_script_authority_gate_v2.py
python -m unittest -v tests/test_phoenix_provider_cutover_v3_apps_script_authority_recovery_v2.py
python -m unittest -v tests/test_phoenix_provider_cutover_v3_apps_script_gateway_signer_v2.py
node apps_script/authority_recovery_v2/tests/security_contracts.mjs
```

The tests verify bundle-aware defect detection, minimum-scope routing, namespace isolation, delegated HMAC verification, stale/tampered/replayed request rejection, exact lineage, external verifier challenge binding, one-use effect permits and source/deployment rollback contracts.
