#!/usr/bin/env bash
set -euo pipefail

# Bubbles / EvidenceOps eCertify ZA Track A provider canary.
# Deploys only LAUNCH-NOW / ZERO-POSSESSION on an already-authorised Google Cloud plane.
# Source existence is not provider execution proof.

PROJECT_ID="${ECERTIFY_PROJECT_ID:-}"
REGION="${ECERTIFY_REGION:-africa-south1}"
AR_REPOSITORY="${ECERTIFY_AR_REPOSITORY:-federation-omega}"
SERVICE="${ECERTIFY_LAUNCH_NOW_SERVICE:-evidenceops-ecertify-za-launch-now}"
RUNTIME_SA="${ECERTIFY_RUNTIME_SA:-}"
SIGNING_SECRET_NAME="${ECERTIFY_INTEGRITY_SIGNING_SECRET_NAME:-}"
KEY_ID="${ECERTIFY_INTEGRITY_KEY_ID:-ecertify-integrity-v1}"
CONFIRMATION="${ECERTIFY_LAUNCH_NOW_DEPLOY_CONFIRMATION:-}"

[[ -n "$PROJECT_ID" ]] || { echo "ECERTIFY_PROJECT_ID required" >&2; exit 2; }
[[ -n "$RUNTIME_SA" ]] || { echo "ECERTIFY_RUNTIME_SA required" >&2; exit 2; }
[[ -n "$SIGNING_SECRET_NAME" ]] || { echo "ECERTIFY_INTEGRITY_SIGNING_SECRET_NAME required" >&2; exit 2; }
[[ -n "$KEY_ID" ]] || { echo "ECERTIFY_INTEGRITY_KEY_ID required" >&2; exit 2; }
[[ "$CONFIRMATION" == "DEPLOY_ECERTIFY_LAUNCH_NOW_ZERO_TRAFFIC_CANARY" ]] || { echo "Explicit Launch-Now canary confirmation required" >&2; exit 3; }
[[ "$SERVICE" != "architron9" ]] || { echo "Refusing reserved service target" >&2; exit 4; }

for cmd in gcloud docker python3 curl; do command -v "$cmd" >/dev/null || { echo "$cmd unavailable" >&2; exit 5; }; done

gcloud config set project "$PROJECT_ID" >/dev/null
test "$(gcloud config get-value project)" = "$PROJECT_ID"
gcloud artifacts repositories describe "$AR_REPOSITORY" --project "$PROJECT_ID" --location "$REGION" >/dev/null
gcloud secrets describe "$SIGNING_SECRET_NAME" --project "$PROJECT_ID" >/dev/null

gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
SHA="${GITHUB_SHA:-$(git rev-parse HEAD)}"
SHORT_SHA="$(printf '%s' "$SHA" | cut -c1-10 | tr '[:upper:]' '[:lower:]')"
CANARY_TAG="bubbles-${SHORT_SHA}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/ecertify-launch-now:${SHA}"

docker build --pull -f evidenceops/ecertify_za/Dockerfile -t "$IMAGE" .
docker push "$IMAGE"

gcloud run deploy "$SERVICE" \
  --project "$PROJECT_ID" --region "$REGION" --image "$IMAGE" \
  --service-account "$RUNTIME_SA" --no-allow-unauthenticated --no-traffic \
  --tag "$CANARY_TAG" \
  --set-env-vars="ECERTIFY_ENV=production,ECERTIFY_MODE=launch_now,ECERTIFY_INTEGRITY_KEY_ID=${KEY_ID}" \
  --set-secrets="ECERTIFY_INTEGRITY_SIGNING_KEY=${SIGNING_SECRET_NAME}:latest" \
  --min-instances=0 --max-instances=3 --concurrency=40 --memory=256Mi --cpu=1 --timeout=30 --quiet

SERVICE_JSON="$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format=json)"
read -r BASE_URL TAG_URL READY_REVISION < <(python3 - "$SERVICE_JSON" "$CANARY_TAG" <<'PY'
import json,sys
payload=json.loads(sys.argv[1]); tag=sys.argv[2]; status=payload.get("status") or {}
base_url=status.get("url") or ""; ready=status.get("latestReadyRevisionName") or ""; tag_url=""
for item in status.get("traffic") or []:
    if item.get("tag")==tag: tag_url=item.get("url") or ""; break
if not base_url or not tag_url or not ready: raise SystemExit("provider readback missing base URL, canary tag URL or ready revision")
print(base_url,tag_url,ready)
PY
)
TOKEN="$(gcloud auth print-identity-token --audiences="$BASE_URL")"
HEALTH="$(curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" "$TAG_URL/health")"
python3 - "$HEALTH" <<'PY'
import json,sys
h=json.loads(sys.argv[1]); assert h.get("ok") is True; assert h.get("version")=="0.9.0"; assert h.get("mode")=="launch_now"; assert h.get("zero_possession_integrity_receipts") is True; assert h.get("identity_provider_required_for_launch") is False; assert h.get("environment")=="production"
print("ECERTIFY_LAUNCH_NOW_CANARY_HEALTH_VERIFIED")
PY
CANARY_HASH="$(python3 - <<'PY'
import hashlib
print(hashlib.sha256(b"Bubbles eCertify Launch-Now provider canary").hexdigest())
PY
)"
CANARY_NONCE="bubbles-provider-canary-${SHORT_SHA}"
ISSUE_PAYLOAD="$(python3 - "$CANARY_HASH" "$CANARY_NONCE" <<'PY'
import json,sys
print(json.dumps({"document_sha256":sys.argv[1],"client_nonce":sys.argv[2]}))
PY
)"
ISSUED="$(curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" -H "content-type: application/json" -d "$ISSUE_PAYLOAD" "$TAG_URL/v1/integrity/receipt/issue")"
VERIFY_PAYLOAD="$(python3 - "$ISSUED" <<'PY'
import json,sys
r=json.loads(sys.argv[1]); required={"verification_code","document_sha256","issued_at","key_id","public_label","client_nonce_sha256","signature_hex","truth_boundary"}; missing=sorted(required.difference(r));
if missing: raise SystemExit(f"issued receipt missing fields: {missing}")
print(json.dumps({k:r[k] for k in sorted(required)}))
PY
)"
VERIFIED="$(curl --fail --silent --show-error -H "Authorization: Bearer $TOKEN" -H "content-type: application/json" -d "$VERIFY_PAYLOAD" "$TAG_URL/v1/integrity/receipt/verify")"
python3 - "$VERIFIED" <<'PY'
import json,sys
r=json.loads(sys.argv[1]); assert r.get("valid") is True; print("ECERTIFY_LAUNCH_NOW_RECEIPT_ROUNDTRIP_VERIFIED")
PY
python3 - "$PROJECT_ID" "$REGION" "$SERVICE" "$READY_REVISION" "$IMAGE" "$CANARY_TAG" "$BASE_URL" "$TAG_URL" "$KEY_ID" <<'PY'
import json,sys
print(json.dumps({"receipt":"ECERTIFY-ZA-LAUNCH-NOW-ZERO-TRAFFIC-CANARY-VERIFIED","project":sys.argv[1],"region":sys.argv[2],"service":sys.argv[3],"ready_revision":sys.argv[4],"image":sys.argv[5],"canary_tag":sys.argv[6],"service_url":sys.argv[7],"canary_url":sys.argv[8],"integrity_key_id":sys.argv[9],"mode":"launch_now","zero_possession":True,"identity_provider_required":False,"document_bytes_transmitted":False,"traffic_promoted":False,"public_unauthenticated":False,"proof_scope":"zero-traffic provider canary only; not public production launch"},sort_keys=True))
PY
