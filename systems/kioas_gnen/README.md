# KIOAS Google Native Execution Node (GNEN) v1.0.0

GNEN is the permanent **thin Google-native execution node** for KIOAS. It is deliberately not the KIOAS brain and it carries no provider/model sovereignty.

## Responsibilities
- owner identity and node health
- KIOAS command queue intake for A0/A1 actions
- bounded Google Sheets control-plane reads and safe appends
- allowlisted Google Drive metadata and Google Docs text reads
- semantic proof/readback receipts
- heartbeat and trigger watchdog
- idempotency and single-writer command execution
- failure-to-win capture
- configuration checkpoints / source rollback pointers
- secret-free external-worker handoff envelopes
- compatibility wrappers for the existing KIOAS lab kernel

## Explicit non-responsibilities
- no email send
- no IAM mutation
- no deployment or traffic mutation
- no billing/payment
- no secret reads/writes
- no arbitrary HTTP target execution
- no model/provider promotion
- no production-effect authority

## Deployment model
Source is versioned in GitHub. The existing owner-private KIOAS Apps Script project is the intended Google runtime. Deployment requires exact source identity, pre-install checkpoint, source sync, trigger singleton readback, bootstrap canary and semantic command canary before maturity may advance beyond SOURCE_READY.
