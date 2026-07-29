# WIF Activation Edge

The deployment path is fail-closed. Source merge, pull-request tests and a
healthy historical Cloud Run service do not prove that the current Superior
Logic image was built, deployed or promoted.

## Verified failure boundary

The deployment for commit `2a2d1cef9b985251ecec3980dae2e85d2df4cdfb`
failed before token issuance with Google STS `invalid_target`. Build, push,
deploy and health-verification steps did not run.

## Canonical identities

- Project: `sov-hybrid-suite` (`257649435135`)
- Region: `africa-south1`
- Existing service: `architron9`
- Artifact Registry repository: `federation-omega`
- Provider: `projects/257649435135/locations/global/workloadIdentityPools/github-federation-omega/providers/github`
- Deployer: `superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com`
- Runtime identity: `superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com`

## Safe activation sequence

1. Run `ops/bootstrap_github_wif.sh --plan` in an authenticated Google Cloud
   administration surface. This is read-only and is the default mode.
2. Inspect the exact missing APIs, identities, WIF state and IAM bindings.
3. Apply only after explicit owner approval by setting:
   `FEDOMEGA_WIF_APPLY_APPROVAL=APPLY_FEDOMEGA_WIF_LEAST_PRIVILEGE`
   and running `ops/bootstrap_github_wif.sh --apply`.
4. Require `ops/bootstrap_github_wif.sh --verify` to return the exact receipt
   `FEDOMEGA-WIF-CLOUD-VERIFIED`.
5. Manually dispatch `Deploy Superior Logic to Cloud Run`. Automatic push
   deployment is disabled.
6. The workflow builds an immutable image, deploys a tagged zero-traffic
   canary and verifies `/health` for version `3.2.0`, a valid event chain and
   `ALG-ECASP-001`.
7. Production promotion occurs only when the manual `promote` input is true.
   Failed post-promotion health triggers traffic rollback to the previous ready
   revision.

## Least-privilege bindings checked by the bootstrap

- `roles/iam.workloadIdentityUser` on the deployer service account, restricted
  to `mosianekk-lang/Federation-Omega` on `refs/heads/main`.
- `roles/serviceusage.serviceUsageConsumer` for the deployer.
- `roles/run.developer` and `roles/run.invoker` on the existing `architron9`
  service.
- `roles/artifactregistry.writer` on the existing `federation-omega`
  repository.
- `roles/iam.serviceAccountUser` on the runtime service account.

The bootstrap refuses to create a Cloud Run service or Artifact Registry
repository. Missing target resources remain explicit owner/admin decisions.
