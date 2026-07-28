#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="sov-hybrid-suite"
PROJECT_NUMBER="257649435135"
POOL_ID="github-federation-omega"
PROVIDER_ID="github"
REPO="mosianekk-lang/Federation-Omega"
DEPLOYER_SA="superior-logic-deployer@${PROJECT_ID}.iam.gserviceaccount.com"
PROVIDER_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"
PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${REPO}"

# Enable required APIs.
gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  --project "$PROJECT_ID"

# Create or reactivate the workload identity pool.
if ! gcloud iam workload-identity-pools describe "$POOL_ID" \
  --location=global --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL_ID" \
    --location=global \
    --project "$PROJECT_ID" \
    --display-name="Federation Omega GitHub"
else
  gcloud iam workload-identity-pools undelete "$POOL_ID" \
    --location=global --project "$PROJECT_ID" >/dev/null 2>&1 || true
fi

# Create or reactivate the OIDC provider.
if ! gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --workload-identity-pool="$POOL_ID" \
  --location=global --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --workload-identity-pool="$POOL_ID" \
    --location=global \
    --project "$PROJECT_ID" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository=='${REPO}'"
else
  gcloud iam workload-identity-pools providers undelete "$PROVIDER_ID" \
    --workload-identity-pool="$POOL_ID" \
    --location=global --project "$PROJECT_ID" >/dev/null 2>&1 || true
fi

# Bind only this repository to the deployer identity.
gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" \
  --project "$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="$PRINCIPAL" >/dev/null

# Destination-side verification.
POOL_STATE=$(gcloud iam workload-identity-pools describe "$POOL_ID" \
  --location=global --project "$PROJECT_ID" --format='value(state)')
PROVIDER_STATE=$(gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --workload-identity-pool="$POOL_ID" \
  --location=global --project "$PROJECT_ID" --format='value(state)')
POLICY_MATCH=$(gcloud iam service-accounts get-iam-policy "$DEPLOYER_SA" \
  --project "$PROJECT_ID" \
  --flatten='bindings[].members' \
  --filter="bindings.role:roles/iam.workloadIdentityUser AND bindings.members:${PRINCIPAL}" \
  --format='value(bindings.role)' | head -n1)

test "$POOL_STATE" = "ACTIVE"
test "$PROVIDER_STATE" = "ACTIVE"
test "$POLICY_MATCH" = "roles/iam.workloadIdentityUser"

cat <<EOF
{"receipt":"FEDOMEGA-WIF-CLOUD-VERIFIED","project":"${PROJECT_ID}","pool":"${POOL_ID}","pool_state":"${POOL_STATE}","provider":"${PROVIDER_RESOURCE}","provider_state":"${PROVIDER_STATE}","deployer_service_account":"${DEPLOYER_SA}","repository":"${REPO}","binding_verified":true,"github_secrets_required":false}
EOF
