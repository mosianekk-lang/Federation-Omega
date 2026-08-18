#!/usr/bin/env bash
set -Eeuo pipefail

HOST_PROJECT="${HOST_PROJECT:-sov-hybrid-suite}"
REGION="${REGION:-africa-south1}"
SERVICE="${SERVICE:-federation-omega-gcp-admin-mcp}"
REPOSITORY="${REPOSITORY:-federation-omega}"
RUNTIME_SA_NAME="${RUNTIME_SA_NAME:-federation-omega-admin}"
DEPLOYER_SA_NAME="${DEPLOYER_SA_NAME:-federation-omega-deployer}"
RUNTIME_SA="${RUNTIME_SA:-${RUNTIME_SA_NAME}@${HOST_PROJECT}.iam.gserviceaccount.com}"
DEPLOYER_SA="${DEPLOYER_SA:-${DEPLOYER_SA_NAME}@${HOST_PROJECT}.iam.gserviceaccount.com}"
ATTEST_PROJECT="${ATTEST_PROJECT:-sov-hybrid-suite}"
ATTEST_REGION="${ATTEST_REGION:-africa-south1}"
ATTEST_SERVICE="${ATTEST_SERVICE:-${SERVICE}}"

test "${GITHUB_ACTIONS:-}" = "true"
test "${GITHUB_REPOSITORY_ID:-}" = "1292795464"
test "${GITHUB_REPOSITORY_OWNER_ID:-}" = "261966700"
test "${GITHUB_REF:-}" = "refs/heads/main"
test -n "${GITHUB_RUN_ID:-}"
test -n "${GITHUB_RUN_ATTEMPT:-}"
test -n "${GITHUB_SHA:-}"
RELEASE_FENCE="github-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}-${GITHUB_SHA}"

gcloud config set project "$HOST_PROJECT" --quiet

gcloud services enable \
  serviceusage.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  logging.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project="$HOST_PROJECT" \
  --quiet

gcloud artifacts repositories describe "$REPOSITORY" \
  --project="$HOST_PROJECT" --location="$REGION" >/dev/null 2>&1 || \
gcloud artifacts repositories create "$REPOSITORY" \
  --project="$HOST_PROJECT" --repository-format=docker --location="$REGION" --quiet

gcloud iam service-accounts describe "$RUNTIME_SA" --project="$HOST_PROJECT" >/dev/null 2>&1 || \
gcloud iam service-accounts create "$RUNTIME_SA_NAME" \
  --project="$HOST_PROJECT" --display-name="Federation Omega Governed Runtime" --quiet

gcloud iam service-accounts describe "$DEPLOYER_SA" --project="$HOST_PROJECT" >/dev/null 2>&1 || \
gcloud iam service-accounts create "$DEPLOYER_SA_NAME" \
  --project="$HOST_PROJECT" --display-name="Federation Omega Transactional Deployer" --quiet

if ! gcloud secrets describe federation-omega-approval-token --project="$HOST_PROJECT" >/dev/null 2>&1; then
  APPROVAL_TOKEN="${FEDERATION_APPROVAL_TOKEN:-$(openssl rand -hex 32)}"
  printf '%s' "$APPROVAL_TOKEN" | gcloud secrets create federation-omega-approval-token \
    --project="$HOST_PROJECT" --replication-policy=automatic --data-file=- --quiet
  unset APPROVAL_TOKEN
elif [ -n "${FEDERATION_APPROVAL_TOKEN:-}" ]; then
  printf '%s' "$FEDERATION_APPROVAL_TOKEN" | gcloud secrets versions add federation-omega-approval-token \
    --project="$HOST_PROJECT" --data-file=- --quiet
fi

gcloud secrets add-iam-policy-binding federation-omega-approval-token \
  --project="$HOST_PROJECT" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --quiet >/dev/null

# The runtime receives only the provider reads required by the 17 typed tools.
for PROJECT in 979287460558 516690968552 257649435135; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/resourcemanager.projectViewer" \
    --quiet >/dev/null

  ROLE_ID="FederationOmegaServiceEnable"
  if ! gcloud iam roles describe "$ROLE_ID" --project="$PROJECT" >/dev/null 2>&1; then
    gcloud iam roles create "$ROLE_ID" \
      --project="$PROJECT" \
      --title="Federation Omega Service Enable Operator" \
      --description="Enable and verify allowlisted Google APIs without disable or IAM permissions" \
      --permissions="serviceusage.services.enable,serviceusage.services.get,serviceusage.services.list,serviceusage.operations.get" \
      --stage=GA \
      --quiet
  fi
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="projects/${PROJECT}/roles/${ROLE_ID}" \
    --quiet >/dev/null
done

for ROLE in roles/run.viewer roles/artifactregistry.reader roles/cloudbuild.builds.viewer roles/logging.viewer; do
  gcloud projects add-iam-policy-binding 257649435135 \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="$ROLE" \
    --quiet >/dev/null
done

# Metadata-only source verification needs storage.objects.get on the build's
# immutable source object. A custom role avoids list, write and delete powers.
SOURCE_VERIFY_ROLE="FederationOmegaSourceVerify"
if ! gcloud iam roles describe "$SOURCE_VERIFY_ROLE" --project="$HOST_PROJECT" >/dev/null 2>&1; then
  gcloud iam roles create "$SOURCE_VERIFY_ROLE" \
    --project="$HOST_PROJECT" \
    --title="Federation Omega Source Verifier" \
    --description="Read immutable Cloud Build source-object metadata for lineage proof" \
    --permissions="storage.objects.get" \
    --stage=GA \
    --quiet
fi
gcloud projects add-iam-policy-binding "$HOST_PROJECT" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="projects/${HOST_PROJECT}/roles/${SOURCE_VERIFY_ROLE}" \
  --quiet >/dev/null

# Deployment authority is separated from runtime authority.
for ROLE in roles/cloudbuild.builds.builder roles/run.admin roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "$HOST_PROJECT" \
    --member="serviceAccount:${DEPLOYER_SA}" \
    --role="$ROLE" \
    --quiet >/dev/null
done
gcloud artifacts repositories add-iam-policy-binding "$REPOSITORY" \
  --project="$HOST_PROJECT" --location="$REGION" \
  --member="serviceAccount:${DEPLOYER_SA}" \
  --role="roles/artifactregistry.writer" \
  --quiet >/dev/null
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
  --project="$HOST_PROJECT" \
  --member="serviceAccount:${DEPLOYER_SA}" \
  --role="roles/iam.serviceAccountUser" \
  --quiet >/dev/null

# Existing authenticated machine authority submits the build. The build itself
# performs canary, proof, promotion and rollback without an owner runbook.
gcloud builds submit . \
  --project="$HOST_PROJECT" \
  --config=cloudbuild.yaml \
  --service-account="projects/${HOST_PROJECT}/serviceAccounts/${DEPLOYER_SA}" \
  --substitutions="_RELEASE_FENCE=${RELEASE_FENCE},_REGION=${REGION},_SERVICE=${SERVICE},_RUNTIME_SA=${RUNTIME_SA},_ATTEST_PROJECT=${ATTEST_PROJECT},_ATTEST_REGION=${ATTEST_REGION},_ATTEST_SERVICE=${ATTEST_SERVICE},_SERVER_VERSION=0.2.2" \
  --quiet

gcloud run services describe "$SERVICE" \
  --project="$HOST_PROJECT" --region="$REGION" \
  --format='json(status.url,status.latestReadyRevisionName,status.trafficStatuses)'
