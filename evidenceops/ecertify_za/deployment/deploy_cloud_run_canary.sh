#!/usr/bin/env bash
set -euo pipefail

# EvidenceOps eCertify ZA isolated Cloud Run canary bundle.
# This script is intentionally not executed by source CI. It requires an authorised
# Google Cloud identity and provider-specific production bindings at execution time.

PROJECT_ID="${ECERTIFY_PROJECT_ID:-}"
REGION="${ECERTIFY_REGION:-africa-south1}"
AR_REPOSITORY="${ECERTIFY_AR_REPOSITORY:-federation-omega}"
PRIVATE_SERVICE="${ECERTIFY_PRIVATE_SERVICE:-evidenceops-ecertify-za-private}"
PUBLIC_SERVICE="${ECERTIFY_PUBLIC_SERVICE:-evidenceops-ecertify-za-public}"
RUNTIME_SA="${ECERTIFY_RUNTIME_SA:-}"
IDP_PROVIDER="${ECERTIFY_IDP_PROVIDER:-}"
IDP_KEY_ID="${ECERTIFY_IDP_KEY_ID:-}"
IDP_SECRET_NAME="${ECERTIFY_IDP_SECRET_NAME:-}"
DB_FACTORY="${ECERTIFY_DB_FACTORY:-}"
CLOUDSQL_INSTANCE="${ECERTIFY_CLOUDSQL_INSTANCE:-}"
CONFIRMATION="${ECERTIFY_DEPLOY_CONFIRMATION:-}"

[[ -n "$PROJECT_ID" ]] || { echo "ECERTIFY_PROJECT_ID required" >&2; exit 2; }
[[ -n "$RUNTIME_SA" ]] || { echo "ECERTIFY_RUNTIME_SA required" >&2; exit 2; }
[[ -n "$IDP_PROVIDER" && -n "$IDP_KEY_ID" && -n "$IDP_SECRET_NAME" ]] || { echo "Identity provider binding required" >&2; exit 2; }
[[ -n "$DB_FACTORY" && -n "$CLOUDSQL_INSTANCE" ]] || { echo "Distributed PostgreSQL replay binding required" >&2; exit 2; }
[[ "$CONFIRMATION" == "DEPLOY_ECERTIFY_ISOLATED_ZERO_TRAFFIC_CANARY" ]] || { echo "Explicit canary confirmation required" >&2; exit 3; }
[[ "$PRIVATE_SERVICE" != "architron9" && "$PUBLIC_SERVICE" != "architron9" ]] || { echo "Refusing reserved service target" >&2; exit 4; }
[[ "$PRIVATE_SERVICE" != "$PUBLIC_SERVICE" ]] || { echo "Public/private service names must differ" >&2; exit 4; }

for cmd in gcloud docker python3; do command -v "$cmd" >/dev/null || { echo "$cmd unavailable" >&2; exit 5; }; done

gcloud config set project "$PROJECT_ID" >/dev/null
test "$(gcloud config get-value project)" = "$PROJECT_ID"
gcloud artifacts repositories describe "$AR_REPOSITORY" --project "$PROJECT_ID" --location "$REGION" >/dev/null
gcloud secrets describe "$IDP_SECRET_NAME" --project "$PROJECT_ID" >/dev/null

gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
SHA="${GITHUB_SHA:-$(git rev-parse HEAD)}"
PRIVATE_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/ecertify-private:${SHA}"
PUBLIC_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/ecertify-public:${SHA}"

docker build --pull -f evidenceops/ecertify_za/Dockerfile -t "$PRIVATE_IMAGE" .
docker build --pull -f evidenceops/ecertify_za/Dockerfile.public -t "$PUBLIC_IMAGE" .
docker push "$PRIVATE_IMAGE"
docker push "$PUBLIC_IMAGE"

# Both services remain authenticated and zero traffic. Public unauthenticated access is
# a later explicit release gate after legal/privacy/abuse-control approval.
gcloud run deploy "$PRIVATE_SERVICE" \
  --project "$PROJECT_ID" --region "$REGION" --image "$PRIVATE_IMAGE" \
  --service-account "$RUNTIME_SA" --no-allow-unauthenticated --no-traffic \
  --add-cloudsql-instances "$CLOUDSQL_INSTANCE" \
  --set-env-vars="ECERTIFY_ENV=production,ECERTIFY_IDP_PROVIDER=${IDP_PROVIDER},ECERTIFY_IDP_KEY_ID=${IDP_KEY_ID},ECERTIFY_REPLAY_BACKEND=postgres,ECERTIFY_DB_FACTORY=${DB_FACTORY}" \
  --set-secrets="ECERTIFY_IDP_HMAC_SECRET=${IDP_SECRET_NAME}:latest" \
  --min-instances=0 --max-instances=5 --concurrency=40 --memory=512Mi --cpu=1 --timeout=60 --quiet

gcloud run deploy "$PUBLIC_SERVICE" \
  --project "$PROJECT_ID" --region "$REGION" --image "$PUBLIC_IMAGE" \
  --service-account "$RUNTIME_SA" --no-allow-unauthenticated --no-traffic \
  --min-instances=0 --max-instances=5 --concurrency=80 --memory=256Mi --cpu=1 --timeout=30 --quiet

PRIVATE_URL="$(gcloud run services describe "$PRIVATE_SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
PUBLIC_URL="$(gcloud run services describe "$PUBLIC_SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"

test -n "$PRIVATE_URL"; test -n "$PUBLIC_URL"
TOKEN_PRIVATE="$(gcloud auth print-identity-token --audiences="$PRIVATE_URL")"
TOKEN_PUBLIC="$(gcloud auth print-identity-token --audiences="$PUBLIC_URL")"
PRIVATE_HEALTH="$(curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN_PRIVATE" "$PRIVATE_URL/health")"
PUBLIC_HEALTH="$(curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN_PUBLIC" "$PUBLIC_URL/health")"

python3 - "$PRIVATE_HEALTH" "$PUBLIC_HEALTH" <<'PY'
import json,sys
private=json.loads(sys.argv[1]); public=json.loads(sys.argv[2])
assert private.get("ok") is True, private
assert private.get("version") == "0.4.0", private
assert private.get("provider_auth_configured") is True, private
assert private.get("environment") == "production", private
assert public.get("ok") is True, public
assert public.get("version") == "0.4.0", public
print("ECERTIFY_ZERO_TRAFFIC_CANARY_HEALTH_VERIFIED")
PY

python3 - "$PROJECT_ID" "$REGION" "$PRIVATE_SERVICE" "$PUBLIC_SERVICE" "$PRIVATE_IMAGE" "$PUBLIC_IMAGE" <<'PY'
import json,sys
print(json.dumps({
  "receipt":"ECERTIFY-ZA-ZERO-TRAFFIC-CANARY-HEALTH-VERIFIED",
  "project":sys.argv[1],"region":sys.argv[2],
  "private_service":sys.argv[3],"public_service":sys.argv[4],
  "private_image":sys.argv[5],"public_image":sys.argv[6],
  "traffic_promoted":False,"public_unauthenticated":False
},sort_keys=True))
PY
