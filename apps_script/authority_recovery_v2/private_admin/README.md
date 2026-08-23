# Private Privileged Admin Plane

This is a separate owner-only Apps Script project. It has no public `doGet` or `doPost`.

The retained ARCHON manager is namespaced to `SOVARA_ARCHON_*`, uses the recovered signed and backup-first transaction engine, claims nonce and permit hashes in bounded durable state, and requires externally verified provider/effect admission before apply or rollback.

Required Script Properties configure local key material or stable resource references; none proves provider authority by itself:

- `ARCHON_CODE_UPDATE_SECRET`
- `ARCHON_CODE_BACKUP_FOLDER_ID`
- `ARCHON_AUDIT_SPREADSHEET_ID`
- optional `ARCHON_DEPLOYMENT_ID`
- `SOVARA_ADMISSION_VERIFIER_URL`
- `SOVARA_ADMISSION_VERIFIER_HOST`

The verifier endpoint must be HTTPS, match the pinned hostname, reject redirects, resolve the provider receipt and one-use effect permit from independently held stable evidence references, and return a fresh challenge-bound result. No provider receipt or permit anchor stored in this same Apps Script project is accepted as independent authority.

The source package does not mint provider receipts, effect permits, OAuth tokens, IAM grants or deployment authority. Provider mutation remains blocked until exact external admission, before/after source hashes, rollback and semantic-readback gates pass.
