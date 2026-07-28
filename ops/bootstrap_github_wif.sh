#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="sov-hybrid-suite"
PROJECT_NUMBER="257649435135"
POOL_ID="github-federation-omega"
PROVIDER_ID="github"
REPO="mosianekk-lang/Federation-Omega"
DEPLOYER_SA="superior-logic-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

# Enable required APIs.
gcloud services enable iamcredentials.googleapis.com sts.googleapis.com run.googleapis.com artifactregistry.googleapis.com --project "$PROJECT_ID"

# Create pool/provider if absent.
gcloud iam workload-identity-pools describe "$POOL_ID" --location=global --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools create "$POOL_ID" --location=global --project "$PROJECT_ID" --display-name="Federation Omega GitHub"

gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" --workload-identity-pool="$POOL_ID" --location=global --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --workload-identity-pool="$POOL_ID" \
    --location=global \
    --project "$PROJECT_ID" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository=='${REPO}'"

# Bind only this repository to the deployer identity.
gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" \
  --project "$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${REPO}"

PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"
printf 'GCP_WORKLOAD_IDENTITY_PROVIDER=%s\n' "$PROVIDER"
printf 'GCP_DEPLOYER_SERVICE_ACCOUNT=%s\n' "$DEPLOYER_SA"
