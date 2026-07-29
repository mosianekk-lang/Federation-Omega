# EvidenceOps Web-to-Drive Bridge

A reusable Google Apps Script web service that retrieves allowlisted public evidence files, recomputes SHA-256, stores the original bytes in Google Drive, creates a JSON provenance sidecar, and appends a manifest row.

## Why this exists

EvidenceOps previously could identify official public PDFs but could not reliably place the raw bytes into Drive through the active connector. This bridge closes that gap without weakening source integrity.

## Security model

- HTTPS only.
- Explicit domain allowlist.
- Private, loopback and link-local hosts rejected.
- Redirects revalidated and limited to five.
- API-key authentication.
- PDF-only by default.
- 25 MB maximum file size by default.
- SHA-256 recomputed from retrieved bytes.
- Optional expected-hash verification.
- Duplicate detection by hash and destination folder.
- Filename sanitisation.
- No email, filing or external transmission capability.

## Repository files

- `Code.gs` — Apps Script web service.
- `appsscript.json` — Apps Script manifest and scopes.
- `openapi.yaml` — connector/action contract.
- `REGRESSION_TESTS.md` — mandatory security and integrity tests.

## Deployment

1. Create a standalone Google Apps Script project.
2. Copy `Code.gs` and `appsscript.json` into the project.
3. In **Project Settings**, enable the manifest file if needed.
4. Run once from the editor:

```javascript
configureBridge(
  'REPLACE_WITH_A_RANDOM_KEY_AT_LEAST_24_CHARACTERS',
  'gov.za,dhet.gov.za,che.ac.za,justice.gov.za,saflii.org',
  'REPLACE_WITH_EVIDENCEOPS_SCORECARD_SPREADSHEET_ID'
);
```

5. Deploy as a web app:
   - Execute as: **User deploying the web app**
   - Access: **Anyone**
6. Insert the deployment URL into `openapi.yaml`.
7. Store the API key in an approved secret store. Never commit it.

The web app allows anonymous network access only at the HTTP layer; every POST remains protected by the API key, domain allowlist and input validation.

## Request example

```json
{
  "apiKey": "REDACTED",
  "jobs": [
    {
      "url": "https://www.gov.za/sites/default/files/gcis_document/201409/a101-97.pdf",
      "folderId": "GOOGLE_DRIVE_FOLDER_ID",
      "filename": "Higher_Education_Act_101_of_1997.pdf",
      "sourceLabel": "Higher Education Act 101 of 1997",
      "evidenceLane": "DHET_GOVERNANCE",
      "allowedMimeTypes": ["application/pdf"],
      "deduplicate": true,
      "notes": "Official statutory source for independent-assessor powers."
    }
  ]
}
```

## Receipt states

- `IMPORTED` — file bytes created in Drive and a sidecar receipt written.
- `DUPLICATE_LINKED` — an existing matching SHA-256 was found in the same folder.
- `FAILED` — no evidential import claim may be made; the error is written to the manifest when available.

Hash status is deliberately separated:

- `HASH_RECOMPUTED` — SHA-256 calculated from retrieved bytes.
- `HASH_MATCH_VERIFIED` — recomputed hash matched a supplied expected hash.

## Connector use

`openapi.yaml` can be used as the contract for a custom GPT action, an MCP wrapper, a Cloud Run gateway, or another approved orchestration layer. The Apps Script service remains the evidence-ingestion backend.

## Production hardening

For higher-volume or files larger than Apps Script limits, preserve the same OpenAPI contract and move the fetch worker to Cloud Run. Keep the Apps Script implementation as the no-cost and low-volume route.

## No-send boundary

This service can fetch and preserve public files. It cannot send email, file complaints, serve documents on third parties, appoint assessors, or take any external legal action.
