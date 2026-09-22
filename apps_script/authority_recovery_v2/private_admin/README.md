# Private Admin Plane

No web entry point. Invoke `SOVARA_ADMIN_dispatch` only through an independently authenticated Apps Script API executable route bound to the canonical standard Cloud project. Required properties are `ARCHON_CODE_UPDATE_SECRET`, `ARCHON_CODE_BACKUP_FOLDER_ID`, `ARCHON_AUDIT_SPREADSHEET_ID`, `SOVARA_ADMISSION_VERIFIER_URL`, `SOVARA_ADMISSION_VERIFIER_HOST` and `SOVARA_ADMISSION_VERIFIER_IDENTITY`; optional deployment/core-mutation properties remain separately gated. Property presence is configuration, not provider authority proof.
