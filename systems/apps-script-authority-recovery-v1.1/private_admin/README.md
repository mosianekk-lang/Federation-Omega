# Private Privileged Administration Plane v1.1

This is a separate owner-only Apps Script project. It has no public `doGet` or `doPost`.

## Contract

- broad scopes exist only in this private project;
- one namespaced `SOVARA_ARCHON_*` source manager performs signed, backup-first source changes;
- a signed request binds the full mutation intent, timestamp, nonce and transaction ID;
- replay state is hash-only, sharded and corruption-fail-closed;
- current provider proof must bind the canonical target, exact OAuth consumer, active-principal fingerprint, provider authentication, Apps Script API relationship, action and deployment inventory;
- effect permits are externally anchored, one-use, exact-action/target, transaction-bound, idempotency-bound and mutation-bound;
- the permit is consumed before the first provider write; an exact retry of the same transaction is idempotent, while cross-transaction replay is rejected;
- source change requires a verified backup, exact post-write hash readback and rollback on mismatch;
- transport lineage never grants target authority.

## Required Script Properties

Secret-bearing values and anchors are configured only through a trusted owner-controlled administration route:

- `ARCHON_CODE_UPDATE_SECRET` — random 32+ character HMAC material;
- `ARCHON_CODE_BACKUP_FOLDER_ID`;
- optional `ARCHON_DEPLOYMENT_ID`;
- `SOVARA_PROVIDER_RECEIPT_ANCHOR_SHA256`;
- `SOVARA_EFFECT_PERMIT_ANCHOR_SHA256`;
- `SOVARA_EXPECTED_OAUTH_CONSUMER_PROJECT_NUMBER`;
- `SOVARA_EXPECTED_ACTIVE_PRINCIPAL_SHA256`.

The source package does not mint provider receipts, effect permits, OAuth tokens, IAM grants or credentials. Storing an anchor alone is not provider proof.

## Truth boundary

Source and hostile-test readiness only. No live Apps Script source, deployment, trigger, OAuth consent, IAM, API or provider state is changed by this package.
