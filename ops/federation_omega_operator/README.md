# Federation Omega operator — CFRE binding repair

This restores source control for the existing `federation-omega-operator` Cloud Run service. It preserves the five observed actions and adds exactly one new action: `BIND_CFRE_PRIVATE_RUNTIME`.

Authentication is fail-closed and accepts either the existing Secret Manager-backed `ADMIN_TOKEN` or a Google-signed OIDC identity whose email is explicitly listed in `OIDC_ALLOWED_PRINCIPALS` and whose audience exactly matches `OPERATOR_AUDIENCE`. No credential values are committed.

The binding action validates the fixed project, region, service, service account, embedded CFRE archive hash, manifest hash, deployment-envelope hash, and idempotency key. It downloads a Drive-shared deployment envelope, verifies it before upload, stages it immutably, runs Cloud Build, deploys a private Cloud Run service, and performs semantic service readback. It does not grant `allUsers` invocation.

Run `npm test` and `npm run check`. Deployment is held until a current Google principal can deploy the operator revision and provider readback proves the new contract.
