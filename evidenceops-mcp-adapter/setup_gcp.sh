#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sov-hybrid-suite}"
REGION="${REGION:-africa-south1}"
RUNTIME_SA="evidenceops-mcp-runtime@${PROJECT_ID}.iam.gserviceaccount.com"

# Create only the missing runtime identity; do not grant Owner.
gcloud iam service-accounts describe "$RUNTIME_SA" --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud iam service-accounts create evidenceops-mcp-runtime \
    --project "$PROJECT_ID" --display-name="EvidenceOps MCP Runtime"

for api in run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com logging.googleapis.com; do
  gcloud services enable "$api" --project "$PROJECT_ID"
done

gcloud artifacts repositories describe evidenceops --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud artifacts repositories create evidenceops --repository-format=docker \
    --location "$REGION" --project "$PROJECT_ID"

# Runtime may read only the two named secrets and write logs.
for secret in fo-operator-admin-token evidenceops-mcp-access-token; do
  gcloud secrets describe "$secret" --project "$PROJECT_ID" >/dev/null 2>&1 || \
    gcloud secrets create "$secret" --replication-policy=automatic --project "$PROJECT_ID"
  gcloud secrets add-iam-policy-binding "$secret" --project "$PROJECT_ID" \
    --member="serviceAccount:$RUNTIME_SA" --role="roles/secretmanager.secretAccessor"
done

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$RUNTIME_SA" --role="roles/logging.logWriter"

cat <<EOF
READY_FOR_SECRET_VERSION_AND_BUILD
Runtime service account: $RUNTIME_SA
Required secrets:
  fo-operator-admin-token (existing operator credential)
  evidenceops-mcp-access-token (new random bearer token)
Build command:
  gcloud builds submit --config evidenceops-mcp-adapter/cloudbuild.yaml --project $PROJECT_ID .
EOF
