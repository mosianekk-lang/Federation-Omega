# ARCHITRON semantic dispatch repair — KAIO provider canary

## Verified defect boundary

The existing Google Apps Script CloudOps bridge v13.2 preserves the requested action and sends it to the existing `architron9` Cloud Run `/execute` endpoint. Provider transport succeeds with HTTP 200. However, `GET_RUNTIME_IDENTITY`, `GET_PROJECT_INFO`, `GET_CLOUD_RUN_SERVICE`, and the later `LIST_SERVICE_ACCOUNTS` probe have each returned the generic runtime-health object instead of the action-specific provider data required by their semantic contract.

This means the current defect is downstream of the Apps Script action selection: the Cloud Run `/execute` dispatcher/operator response path can flatten distinct action aliases into the generic health response. Transport success must therefore remain separate from semantic provider proof.

## Required repair

Patch only the existing `architron9` execution dispatcher/operator. Do not create a second service and do not change the canonical project, region, queue, or CloudOps workbook.

The repaired endpoint must preserve the existing health contract while making these actions semantically distinct:

- `GET_RUNTIME_IDENTITY` -> return a `runtimeIdentity` object containing the authenticated runtime principal/identity source and no secret values.
- `GET_PROJECT_INFO` -> return a `projectInfo` object containing the canonical project ID/number and relevant read-only metadata.
- `GET_CLOUD_RUN_SERVICE` -> return a `service` object containing `architron9` service metadata, including name, region, URL/latest-ready revision/service account when provider-authorised.
- `LIST_SERVICE_ACCOUNTS` -> return a `serviceAccounts` collection containing only read-only service-account inventory metadata and no credential or secret values.

A 2xx response, `DONE`, or the generic health payload is not action proof. Wrapper actions such as `RUNTIME_EXECUTE` also require the requested inner capability to be preserved and read back explicitly.

## Safety and rollback gates

1. Preserve the current ready revision before any deployment.
2. Deploy as a new reversible revision of the existing `architron9` service only.
3. No IAM expansion, secret-value reads, service duplication, or traffic migration beyond what the bounded repair requires.
4. Run health first. If health regresses, roll back immediately.
5. Run all admitted action probes and require the semantic contract in `ops/architron_semantic_contract.py` plus the generic action-specific proof validator.
6. Only promote provider canary maturity after exact provider readback is persisted to the CloudOps command rows/proof ledger.
7. If any action still returns generic health, mark semantic failure and roll back or keep the prior ready revision serving traffic.
8. A disabled provider-specific CloudOps capability must not be treated as satisfied by a generic `RUNTIME_EXECUTE` success response.

## Current proof inputs

- `KAIO-GCP-COMPAT-HEALTH-20260809-1903-001`: valid provider HTTP 200 health proof.
- `KAIO-GCP-COMPAT-STATUS-20260809-1914-001`: valid bridge STATUS proof.
- `KAIO-GCP-COMPAT-IDENTITY-20260809-1957-001`: transport success, semantic failure.
- `KAIO-GCP-COMPAT-PROJECT-20260809-1957-001`: transport success, semantic failure.
- `KAIO-GCP-COMPAT-SERVICE-20260809-1957-001`: transport success, semantic failure.
- `GEMINI_ADC_PREFLIGHT_LIST_SA` / CloudOps command row 418, observed 2026-08-28: intended read-only service-account inventory probe; provider transport returned the generic `architron9` health object rather than service-account inventory. Classify as transport success plus semantic failure, not provider inventory proof.
- CloudOps capability registry readback on 2026-08-28: `RUNTIME_EXECUTE` enabled while provider-specific inventory actions including `LIST_SERVICE_ACCOUNTS` and `GET_PROJECT_INFO` are disabled. This forbids promotion of the generic wrapper response as substitute proof.

## Failure-Win recurrence rule

When an action-specific provider probe receives a generic health object, preserve the transport receipt but reject semantic promotion. Compile the recurrence into all three layers before closure: provider-specific semantic contract, generic wrapper/action-proof validation, and the admitted CI regression court. Repeated unchanged probing is not a repair.

This repair package is source/governance preparation only. It does not itself assert that a Cloud Run revision has been mutated, deployed, or provider-read back with repaired semantics.
