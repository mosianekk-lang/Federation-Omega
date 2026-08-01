# Chat Audit Remediation Standard

Status: ACTIVE_REMEDIATION
Owner and Final Authority: Kim Kagiso Mosiane
Scope: ChatGPT, ICT control artefacts, GitHub, Google Drive, external schedulers and Kim Dataverse estate reporting

## 1. Exact Directive Scope Lock

Every substantive instruction must be captured before execution with:

- exact user wording;
- directive ID;
- required output;
- allowed actions;
- prohibited actions;
- completion test;
- superseding instruction, if any.

No adjacent work may be started unless it is expressly included in the active directive.

## 2. Corrected `n` Semantics

Within this mission, `n` means:

> Continue the current explicit directive only. Do not expand the mission, create adjacent work, activate optional improvements, or substitute a different objective.

## 3. Read-Before-Build Rule

No new control artefact may be created until equivalent existing controls have been identified, read and compared. Existing canonical controls must be amended before parallel controls are created unless isolation, rollback, risk or approval requirements justify a separate artefact.

## 4. Authoritative Coverage Ledger

Every estate surface must use one of these coverage states:

- `NOT_DISCOVERED`
- `METADATA_ONLY`
- `TITLE_AND_SUMMARY_READ`
- `PARTIAL_CONTENT_READ`
- `FULL_CONTENT_READ`
- `PROVIDER_NATIVE_STATE_READ`
- `WRITE_AND_READBACK_VERIFIED`
- `EXPLICITLY_EXCLUDED`
- `PROVIDER_INACCESSIBLE`

Whole-estate completion may not be claimed unless every in-scope item has a terminal evidence-supported state.

## 5. Maturity Vocabulary

Use only evidence-supported states:

- `DISCOVERED`
- `PARTIALLY_READ`
- `FULLY_READ`
- `MAPPED`
- `WRITTEN`
- `READBACK_VERIFIED`
- `TRIGGER_CONFIGURED`
- `TRIGGER_EXECUTED`
- `PROVIDER_BOUND`
- `CANONICAL`
- `COMPLETE`

Non-equivalence rules:

- configured trigger is not triggered execution;
- map creation is not full estate reading;
- comment creation is not structured register update;
- source presence is not provider binding;
- green CI is not production proof;
- local output is not canonical write.

## 6. Binding Levels

Report binding precisely:

- `BRIDGE_BOUND`
- `SOURCE_STORE_BOUND`
- `PROVIDER_BOUND`
- `SCHEMA_BOUND`
- `MISSION_STATE_BOUND`
- `FULL_KIM_DATAVERSE_BOUND`

Never use the unqualified word `bound` where more than one level is possible.

## 7. Duplicate-Control Check

Before creating an artefact, record:

- equivalent artefact search result;
- canonical status;
- amend-versus-create decision;
- supersession rule;
- duplicate source-of-truth risk.

Default: amend the existing canonical control.

## 8. Public and Private Classification

Use three classes:

- `PUBLIC_ARCHITECTURE`
- `PRIVATE_OPERATIONAL_METADATA`
- `SECRET_OR_CREDENTIAL_MATERIAL`

Public repositories store aliases and architecture only. Private bridges store provider IDs and operational pointers. Vaults store secrets. Chat outputs contain only the minimum necessary detail.

## 9. External Scheduling Rule

All delayed, recurring, conditional and monitoring work must run on an authorised external surface. ChatGPT-hosted scheduling is prohibited unless the founder explicitly reverses the rule.

Before deployment, record:

- scheduler surface;
- trigger and timezone;
- authority;
- output and receipt target;
- failure route;
- first-run proof.

A schedule is `TRIGGER_CONFIGURED` until a real run and its artefact or receipt are read back.

## 10. Branch and PR Discipline

Use one active branch and one active PR per mission by default. Separate PRs require a recorded reason such as independent rollback, different approval, materially different risk or deployment isolation.

## 11. Stale-State Audit

Every control sweep must test for:

- broken canonical pointer;
- superseded receipt;
- duplicate bridge;
- stale runtime state;
- receipt-target mismatch;
- schema drift;
- maturity overclaim;
- unresolved transaction.

## 12. Release Gate

A completion claim requires:

1. exact directive satisfied;
2. required reading complete;
3. execution complete;
4. target readback complete;
5. maturity terminology validated;
6. duplicate-control check passed;
7. stale-state audit passed;
8. unresolved delta disclosed;
9. receipt issued;
10. work stops when the directive is complete.

## 13. Current Remediation Scope

This standard implements the findings of the full chat audit. The accompanying machine-readable control and private bridge registers are the enforcement surfaces. No claim is made that the entire Kim Dataverse estate has been fully read or reconciled.
