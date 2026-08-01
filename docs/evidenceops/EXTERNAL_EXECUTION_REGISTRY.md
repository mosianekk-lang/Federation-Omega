# EvidenceOps External Execution Registry

Status: SOURCE-CONSOLIDATED / EXTERNAL-RUNTIME-ONLY / READBACK-PENDING
Owner and final authority: Kim Kagiso Mosiane

## Standing rule

All recurring, delayed, conditional, monitoring and scheduled work must execute on authorised external infrastructure. ChatGPT may design, launch, inspect and verify external schedules, but must not host or maintain them internally.

## Runtime selection order

1. GitHub Actions — repository, CI, release, deployment and code-state watches.
2. Google Cloud Scheduler + Cloud Run / Functions / Tasks — durable processing, provider checks, queues, databases and long-running jobs.
3. Google Apps Script triggers — lightweight Drive, Docs, Sheets, Gmail and workspace-local automation.
4. Google Calendar — human reminders and meetings only.

## Canonical registry

| ID | Workstream | Trigger | Primary runtime | Output / receipt | Current state |
|---|---|---|---|---|---|
| EXT-WATCH-001 | WIF provider boundary watch | Hourly at minute 17 | GitHub Actions | issue #52 state comment + JSON artifact | DEPLOYED; first scheduled run pending verification |
| EXT-WATCH-002 | Kimmie Seed maturity watch | Hourly condition evaluation | Google Cloud Scheduler + Cloud Run | maturity receipt + registry update | MIGRATION REQUIRED |
| EXT-WATCH-003 | EvidenceOps lane watch | Hourly dependency scan | Google Cloud Scheduler + Cloud Run | lane-state delta receipt | MIGRATION REQUIRED |
| EXT-WATCH-004 | IPEP innovation scan | Daily | GitHub Actions or Cloud Run | innovation register update | MIGRATION REQUIRED |
| EXT-WATCH-005 | IPEP Bible capture | Hourly event/turn-derived | Google Apps Script or Cloud Run | append/readback receipt | MIGRATION REQUIRED |
| EXT-WATCH-006 | Audio run learning loop | Hourly Drive-folder scan | Google Apps Script for intake + Cloud Run for processing | quality-ledger and lesson receipt | MIGRATION REQUIRED |

## Migration requirements

Each migrated task must define:

- stable external execution ID;
- source mission and directive;
- trigger type and cadence;
- authorised runtime and identity;
- minimum input scope;
- side-effect class;
- idempotency key;
- output target;
- readback proof;
- failure route;
- owner and escalation path;
- no-secret logging rule;
- disable/rollback mechanism.

## Evidence standard

A schedule is not active merely because configuration exists. Activation requires:

1. deployment to the external runtime;
2. a real triggered execution;
3. target-state readback;
4. retained receipt or artifact;
5. failure-path verification;
6. maturity update.

## Current control gaps

- EXT-WATCH-001 is deployed but its first scheduled run is not yet verified.
- EXT-WATCH-002 through EXT-WATCH-006 are mapped but not yet deployed externally.
- No ChatGPT schedule is authorised.

Maturity: `REGISTRY_CREATED / ONE_EXTERNAL_SCHEDULER_DEPLOYED / FIVE_MIGRATIONS_OPEN`
