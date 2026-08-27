# Federation Omega operator — v4 CIOS production control lane

This restores source control for the existing `federation-omega-operator` Cloud Run service. It preserves the existing Federation and CFRE actions and adds a keyless Gemini route through Vertex AI using the operator's Cloud Run service identity.

Version 4 also adds the exact CIOS actions `READ_CIOS_PRODUCTION`, `READ_CIOS_PERSISTENCE`, `DEPLOY_CIOS_ZERO_TRAFFIC`, `VERIFY_CIOS_CANARY`, `ROLLBACK_CIOS_TRAFFIC`, and `PROMOTE_CIOS_TRAFFIC`. Their contracts pin the project, region, service, runtime service account, Cloud SQL instance, three Secret Manager names, tenant, runtime user, source SHA, digest image, revision and idempotency keys.

The CIOS lane:

- rejects deployment unless Cloud SQL PostgreSQL backups, PITR, log retention, storage auto-resize, deletion protection and a successful backup are read back;
- preserves the active traffic baseline and admits only a tagged zero-percent candidate;
- invokes the tagged revision with Cloud Run IAM plus a separately retrieved application token;
- verifies managed persistence, append-only audit health and deterministic event replay;
- writes first-writer-wins deployment/canary/rollback/promotion receipts to the private control bucket;
- restores the baseline active traffic and retains the candidate at zero traffic for a recovery canary;
- keeps promotion environment-disabled unless `CIOS_PROMOTION_ENABLED=true`, and still requires the exact immutable receipts.

The Gemini route separates discovery from inference:

- `READ_GEMINI_VERTEX_CAPABILITY` checks that `aiplatform.googleapis.com` is enabled and reads the allowlisted Google publisher-model record. It performs no inference and reports zero incremental cost.
- `VERIFY_GEMINI_VERTEX_SEMANTIC` runs one exact-nonce `generateContent` canary only when `GEMINI_SEMANTIC_CANARY_ENABLED=true` and the request carries the exact approval, tenant, model and idempotency contract.

The route accepts no browser session, API key, arbitrary endpoint, arbitrary tenant or silent fallback. `PROJECT_ID`, `VERTEX_LOCATION`, `FEDERATION_TENANT_ID`, `GEMINI_MODEL` and `GEMINI_ALLOWED_MODELS` pin the execution surface. The operator service account must have the narrow Vertex prediction permission before the semantic gate is enabled.

Authentication is fail-closed and accepts either the existing Secret Manager-backed `ADMIN_TOKEN` or a Google-signed OIDC identity whose email is explicitly listed in `OIDC_ALLOWED_PRINCIPALS` and whose audience exactly matches `OPERATOR_AUDIENCE`. No credential values are committed.

The binding action validates the fixed project, region, service, service account, embedded CFRE archive hash, manifest hash, deployment-envelope hash, and idempotency key. It downloads a Drive-shared deployment envelope, verifies it before upload, stages it immutably, runs Cloud Build, deploys a private Cloud Run service, and performs semantic service readback. It does not grant `allUsers` invocation.

Run `npm test` and `npm run check`. Source does not self-certify live deployment; `.github/workflows/cios-production-lane.yml` performs exact-main provider execution and provider-native readback.
