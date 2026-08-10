# ARCHITRON semantic dispatch repair — KAIO provider canary

## Verified defect boundary

The existing Google Apps Script CloudOps bridge v13.2 preserves the requested action and sends it to the existing `architron9` Cloud Run `/execute` endpoint. Provider transport succeeds with HTTP 200. However, `GET_RUNTIME_IDENTITY`, `GET_PROJECT_INFO`, and `GET_CLOUD_RUN_SERVICE` each return the same generic runtime-health object instead of action-specific provider data.

This means the current defect is downstream of the Apps Script action selection: the Cloud Run `/execute` dispatcher/operator response path is flattening distinct action aliases into the generic health response.

## Required repair

Patch only the existing `architron9` execution dispatcher/operator. Do not create a second service and do not change the canonical project, region, queue, or CloudOps workbook.

The repaired endpoint must preserve the existing health contract while making these actions semantically distinct:

- `GET_RUNTIME_IDENTITY` -> return a `runtimeIdentity` object containing the authenticated runtime principal/identity source and no secret values.
- `GET_PROJECT_INFO` -> return a `projectInfo` object containing the canonical project ID/number and relevant read-only metadata.
- `GET_CLOUD_RUN_SERVICE` -> return a `service` object containing `architron9` service metadata, including name, region, URL/latest-ready revision/service account when provider-authorised.

A 2xx response, `DONE`, or the five-field generic health payload is not action proof.

## Safety and rollback gates

1. Preserve the current ready revision before any deployment.
2. Deploy as a new reversible revision of the existing `architron9` service only.
3. No IAM expansion, secret-value reads, service duplication, or traffic migration beyond what the bounded repair requires.
4. Run health first. If health regresses, roll back immediately.
5. Run the three action probes and require the semantic contract in `ops/architron_semantic_contract.py`.
6. Only promote KAIO provider canary maturity after exact provider readback is persisted to the CloudOps command rows/proof ledger.
7. If any action still returns generic health, mark semantic failure and roll back or keep the prior ready revision serving traffic.

## Current proof inputs

- `KAIO-GCP-COMPAT-HEALTH-20260809-1903-001`: valid provider HTTP 200 health proof.
- `KAIO-GCP-COMPAT-STATUS-20260809-1914-001`: valid bridge STATUS proof.
- `KAIO-GCP-COMPAT-IDENTITY-20260809-1957-001`: transport success, semantic failure.
- `KAIO-GCP-COMPAT-PROJECT-20260809-1957-001`: transport success, semantic failure.
- `KAIO-GCP-COMPAT-SERVICE-20260809-1957-001`: transport success, semantic failure.

This repair package is source/governance preparation only. It does not itself assert that a Cloud Run revision has been mutated or deployed.
