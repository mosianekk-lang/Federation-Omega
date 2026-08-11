# Federation Omega — Final Cloud Activation

Run this single command in an authenticated Google Cloud Shell:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/mosianekk-lang/Federation-Omega/main/ops/cloud_shell_activate.sh)
```

The transaction will:

1. Synchronise the canonical `main` branch.
2. Enable required Google Cloud APIs.
3. Create or repair the GitHub workload-identity pool and provider.
4. Verify the repository-to-deployer service-account binding.
5. Create the Artifact Registry repository when absent.
6. Build the container through Cloud Build.
7. Deploy `architron9` to `africa-south1`.
8. Verify the latest created revision is the latest ready revision.
9. Perform an authenticated `/health` request.
10. Emit `FEDOMEGA-WIF-AND-CLOUDRUN-VERIFIED` only after every proof gate succeeds.

## Failure routing

- `PERMISSION_DENIED`: the active Cloud Shell principal lacks the named IAM operation. Capture the failed command and grant only the missing role.
- `invalid_target`: the WIF pool/provider was not created or is not ACTIVE; rerun the transaction after confirming the project is `sov-hybrid-suite`.
- Artifact Registry write failure: verify the deployer has Artifact Registry Writer in `africa-south1`.
- Cloud Build submission failure: verify Cloud Build API and build permissions.
- Cloud Run deployment failure: inspect the latest revision condition and retain the prior ready revision.
- Health failure: do not mark deployment complete; preserve the revision and response payload for repair.
