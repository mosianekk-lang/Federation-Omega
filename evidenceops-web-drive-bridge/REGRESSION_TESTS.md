# Mandatory Regression Tests

The bridge is not production-ready until all tests pass against the deployed URL.

| ID | Test | Expected result |
|---|---|---|
| WB-01 | GET status | `ok=true`, correct service and version |
| WB-02 | Missing API key | Rejected as `UNAUTHORISED` |
| WB-03 | Wrong API key | Rejected as `UNAUTHORISED` |
| WB-04 | HTTP URL | Rejected as `HTTPS_REQUIRED` |
| WB-05 | Non-allowlisted domain | Rejected as `DOMAIN_NOT_ALLOWED` |
| WB-06 | localhost/private address | Rejected as `PRIVATE_HOST_REJECTED` |
| WB-07 | Redirect to disallowed domain | Redirect target rejected |
| WB-08 | More than five redirects | Rejected as `TOO_MANY_REDIRECTS` |
| WB-09 | HTML returned for PDF job | Rejected as `MIME_REJECTED` |
| WB-10 | Empty file | Rejected as `EMPTY_FILE` |
| WB-11 | File larger than configured limit | Rejected as `FILE_TOO_LARGE` |
| WB-12 | Incorrect expected SHA-256 | Rejected as `HASH_MISMATCH`; no file created |
| WB-13 | Valid official PDF | Original bytes, JSON sidecar and manifest row created |
| WB-14 | Same PDF imported twice | Second request returns `DUPLICATE_LINKED` when deduplication is enabled |
| WB-15 | Filename traversal characters | Filename safely sanitised |
| WB-16 | Batch over ten jobs | Rejected as `INVALID_BATCH` |
| WB-17 | Manifest unavailable | File import may succeed, but response and logs disclose manifest limitation |
| WB-18 | Destination folder inaccessible | Job fails; no completion claim |
| WB-19 | Hash of Drive download | Matches receipt SHA-256 |
| WB-20 | No-send boundary | Code contains no Gmail, MailApp or external transmission function |

## Release rule

- Any failure in WB-02 through WB-12, WB-19 or WB-20 blocks deployment.
- A test result must record date, deployment ID, source URL, outcome, and reviewer.
- A copied hash is not sufficient for WB-19; retrieve the stored Drive file bytes and recompute independently.
