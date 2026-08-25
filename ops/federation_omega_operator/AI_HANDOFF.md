# AI handoff

1. Verify the current repository head and this patch's test receipts.
2. Repair or replace the disabled/missing GitHub WIF provider with repository-and-branch-restricted OIDC, or use an already authenticated Google-native deployer.
3. Deploy this source to the existing `federation-omega-operator` service with zero traffic first; bind `ADMIN_TOKEN` from Secret Manager and set an exact `OPERATOR_AUDIENCE` plus `OIDC_ALLOWED_PRINCIPALS`.
4. Prove `/health`, `/`, authenticated `STATUS`, and authenticated `BIND_CFRE_PRIVATE_RUNTIME` dry-run.
5. Share only the exact deployment-envelope Drive file with the operator service account.
6. Execute the live bind once, then verify Cloud Build `SUCCESS`, private Cloud Run revision/image/service account, `/health`, `/contract`, and `/canary` using a Google identity token.
7. Preserve the prior operator revision and any prior CFRE service revision as rollback references.
