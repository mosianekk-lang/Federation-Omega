# WIF Activation Edge

Repository-side secret configuration has been eliminated. The deployment workflow now uses deterministic, non-secret identifiers:

- Provider: `projects/257649435135/locations/global/workloadIdentityPools/github-federation-omega/providers/github`
- Deployer service account: `superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com`

The only remaining activation edge is to execute `ops/bootstrap_github_wif.sh` once in an authenticated Google Cloud administration surface for project `sov-hybrid-suite`.

After that binding exists, any qualifying push to `main` or a manual workflow dispatch will build, push, deploy and verify `architron9` in `africa-south1` without a service-account key or GitHub repository secrets.

Closure requires:

1. Google OIDC authentication succeeds.
2. Artifact Registry image is pushed.
3. Cloud Run reports `latestCreatedRevisionName == latestReadyRevisionName`.
4. Authenticated `/health` returns `status=HEALTHY` and `event_chain_valid=true`.
