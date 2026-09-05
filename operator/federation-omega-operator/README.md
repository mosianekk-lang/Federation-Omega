# Federation Omega Operator — WIF Inventory Candidate

Status: TESTED; not deployed or production-proven.

This candidate preserves the five observed live actions and adds
READ_WIF_INVENTORY. It is stateless, fixed to one Google Cloud project, and
returns only allowlisted fields.

## Contract

GET /health is public-safe readiness. GET / returns the version and six-action
allowlist. POST /execute is token-gated.

Actions: STATUS, READ_CLOUD_RUN_SERVICE, VERIFY_ARCHITRON_HEALTH,
DEPLOY_SOLUTION5_LOCKED, READ_BUILD, READ_WIF_INVENTORY.

The deployment action is a validated adapter contract. It fails closed with
DEPLOYMENT_ADAPTER_REQUIRED because the exact production backend is not indexed.

## Security

- Payloads cannot select another project; WIF location is global.
- Pagination, concurrency, timeout, item counts, and request counts are bounded.
- Keys, IAM policies, credentials, raw JWK/SAML/X.509 data, mapping values,
  dependency bodies, Cloud Run env, and Build substitutions are omitted.
- Auth comparison is timing-safe; logs omit payloads and tokens.

## Test and run

~~~bash
node --check src/wif-inventory.js
node --check src/operator-service.js
node --check src/http-app.js
node --check src/server.js
node --test
node scripts/check-build-contract.mjs
~~~

The tests need no dependency install. To run the Cloud adapter:

~~~bash
npm install --ignore-scripts
export PROJECT_ID=sov-hybrid-suite
export REGION=africa-south1
export TARGET_SERVICE=architron9
export ADMIN_TOKEN
node src/server.js
~~~

Required WIF read permissions are iam.workloadIdentityPools.list,
iam.workloadIdentityPoolProviders.list, and iam.serviceAccounts.list.

No deployment occurred. Reconcile the live source/build, implement and test the
adapter, obtain A2 authority, deploy an immutable no-traffic canary, verify all
six actions, and prove rollback before promotion.

See BUILD_CONTRACT.json, FORMATION_SPEC.md, PROJECT_MEMORY.md, AI_HANDOFF.md.
