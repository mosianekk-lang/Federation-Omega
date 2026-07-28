#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="sov-hybrid-suite"
PROJECT_NUMBER="257649435135"
REGION="africa-south1"
SERVICE="architron9"
AR_REPO="federation-omega"
RUNTIME_SA="superior-logic-runtime@${PROJECT_ID}.iam.gserviceaccount.com"
DEPLOYER_SA="superior-logic-deployer@${PROJECT_ID}.iam.gserviceaccount.com"
REPO="mosianekk-lang/Federation-Omega"
POOL_ID="github-federation-omega"
PROVIDER_ID="github"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE}:manual-$(date -u +%Y%m%dT%H%M%SZ)"

require() { command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }; }
require gcloud
require git
require python3
require curl

gcloud config set project "$PROJECT_ID" >/dev/null

# Ensure APIs.
gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  --project "$PROJECT_ID"

# Ensure WIF pool/provider and binding.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "${SCRIPT_DIR}/bootstrap_github_wif.sh"

# Ensure Artifact Registry repository.
gcloud artifacts repositories describe "$AR_REPO" \
  --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "$AR_REPO" \
    --repository-format=docker \
    --location "$REGION" \
    --description="Federation Omega runtime images" \
    --project "$PROJECT_ID"

# Build through Cloud Build so no local Docker daemon is required.
gcloud builds submit \
  --tag "$IMAGE" \
  --project "$PROJECT_ID" \
  .

# Deploy.
gcloud run deploy "$SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --image "$IMAGE" \
  --service-account "$RUNTIME_SA" \
  --platform managed \
  --quiet

CREATED="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.latestCreatedRevisionName)')"
READY="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.latestReadyRevisionName)')"
URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"

[[ -n "$CREATED" ]]
[[ "$CREATED" == "$READY" ]]
[[ -n "$URL" ]]

TOKEN="$(gcloud auth print-identity-token)"
HEALTH="$(curl --fail --silent --show-error -H "Authorization: Bearer ${TOKEN}" "${URL}/health")"
python3 - "$HEALTH" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])
assert payload.get("status") == "HEALTHY", payload
assert payload.get("event_chain_valid") is True, payload
PY

python3 - <<PY
import json
print(json.dumps({
  "receipt": "FEDOMEGA-WIF-AND-CLOUDRUN-VERIFIED",
  "project": "${PROJECT_ID}",
  "project_number": "${PROJECT_NUMBER}",
  "region": "${REGION}",
  "service": "${SERVICE}",
  "image": "${IMAGE}",
  "latest_created_revision": "${CREATED}",
  "latest_ready_revision": "${READY}",
  "url": "${URL}",
  "runtime_service_account": "${RUNTIME_SA}",
  "deployer_service_account": "${DEPLOYER_SA}",
  "repository": "${REPO}",
  "pool": "${POOL_ID}",
  "provider": "${PROVIDER_ID}",
  "health": ${HEALTH}
}, sort_keys=True))
PY
