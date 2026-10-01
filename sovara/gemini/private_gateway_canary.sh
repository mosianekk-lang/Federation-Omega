#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sov-hybrid-suite}"
PROJECT_NUMBER="${PROJECT_NUMBER:-257649435135}"
REGION="${REGION:-africa-south1}"
AR_REPOSITORY="${AR_REPOSITORY:-federation-omega}"
SERVICE="${GEMINI_GATEWAY_SERVICE:-sovara-gemini-gateway}"
RUNTIME_SA="${RUNTIME_SA:-superior-logic-runtime@${PROJECT_ID}.iam.gserviceaccount.com}"
DEPLOYER_SA="${DEPLOYER_SA:-superior-logic-deployer@${PROJECT_ID}.iam.gserviceaccount.com}"
MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"
INTERACTIONS_MODEL="${INTERACTIONS_MODEL:-gemini-3.8-flash}"
SOURCE_SHA="${GITHUB_SHA:-${SOURCE_SHA:-}}"
RUN_ID="${GITHUB_RUN_ID:-local}"
RUN_ATTEMPT="${GITHUB_RUN_ATTEMPT:-1}"
RECEIPT_DIR="${SOVARA_RECEIPT_DIR:-${RECEIPT_DIR:-/tmp/sovara-gemini-g3}}"
EXECUTE_CONFIRMATION="DEPLOY_PRIVATE_ZERO_TRAFFIC_GEMINI_CANARY_V1"

MODE="plan"
case "${1:-}" in
  ""|--plan) MODE="plan" ;;
  --execute) MODE="execute" ;;
  -h|--help)
    echo "Usage: sovara/gemini/private_gateway_canary.sh [--plan|--execute]"
    exit 0
    ;;
  *) echo "Unknown mode: ${1}" >&2; exit 2 ;;
esac

for bin in gcloud docker python3 curl; do
  command -v "$bin" >/dev/null 2>&1 || { echo "Missing required command: $bin" >&2; exit 1; }
done
[[ "$PROJECT_ID" == "sov-hybrid-suite" ]] || { echo "Canonical project mismatch" >&2; exit 3; }
[[ "$PROJECT_NUMBER" == "257649435135" ]] || { echo "Canonical project number mismatch" >&2; exit 3; }
[[ "$RUNTIME_SA" == "superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com" ]] || { echo "Canonical runtime identity mismatch" >&2; exit 3; }
[[ "$DEPLOYER_SA" == "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com" ]] || { echo "Canonical deployer identity mismatch" >&2; exit 3; }
[[ "$REGION" == "africa-south1" ]] || { echo "Canonical region mismatch" >&2; exit 3; }
[[ -n "$SOURCE_SHA" ]] || { echo "Exact source SHA required" >&2; exit 3; }
[[ "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "SOURCE_SHA must be a 40-character lowercase Git SHA" >&2; exit 3; }
mkdir -p "$RECEIPT_DIR"

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
[[ "$ACTIVE_ACCOUNT" == "$DEPLOYER_SA" ]] || { echo "Active Google account is not the canonical deployer" >&2; exit 4; }
OBSERVED_PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
[[ "$OBSERVED_PROJECT_NUMBER" == "$PROJECT_NUMBER" ]] || { echo "Provider project number mismatch" >&2; exit 4; }

gcloud artifacts repositories describe "$AR_REPOSITORY" \
  --project "$PROJECT_ID" --location "$REGION" --format=json \
  > "$RECEIPT_DIR/G3_ARTIFACT_REPOSITORY_READBACK.json"

set +e
./sovara/gemini/bootstrap_gateway.sh --verify > "$RECEIPT_DIR/G3_ADC_VERIFICATION.json"
ADC_CODE=$?
set -e

python3 - "$RECEIPT_DIR/G3_ADC_VERIFICATION.json" "$ADC_CODE" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
code=int(sys.argv[2])
if code != 0 or p.get('receipt') != 'FEDOMEGA-GEMINI-ADC-VERIFIED' or p.get('state') != 'VERIFIED':
    raise SystemExit('G3 requires FEDOMEGA-GEMINI-ADC-VERIFIED before any build/push/deploy effect')
if p.get('runtime_service_account') != 'superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com':
    raise SystemExit('runtime service account mismatch')
if p.get('deployer_service_account') != 'superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com':
    raise SystemExit('deployer service account mismatch')
if p.get('service_account_key_created') is not False or p.get('secret_payload_accessed') is not False:
    raise SystemExit('credential truth boundary violated')
PY

# Cold-start canary safety requires create/invoke/inspect/delete authority
# before any Cloud Run service-create effect.
ACCESS_TOKEN="$(gcloud auth print-access-token)"
export ACCESS_TOKEN PROJECT_ID
python3 - <<'PY' > "$RECEIPT_DIR/G3_DEPLOYER_PERMISSION_PREFLIGHT.json"
import json, os, urllib.request
required=[
    'run.services.create',
    'run.services.get',
    'run.services.update',
    'run.services.delete',
    'run.operations.get',
    'run.routes.invoke',
]
body=json.dumps({'permissions':required},separators=(',',':')).encode()
req=urllib.request.Request(
    f"https://cloudresourcemanager.googleapis.com/v1/projects/{os.environ['PROJECT_ID']}:testIamPermissions",
    data=body,
    method='POST',
    headers={
        'Authorization':f"Bearer {os.environ['ACCESS_TOKEN']}",
        'Content-Type':'application/json',
        'X-Goog-User-Project':os.environ['PROJECT_ID'],
    },
)
with urllib.request.urlopen(req,timeout=30) as response:
    payload=json.loads(response.read().decode() or '{}')
granted=sorted(payload.get('permissions') or [])
missing=sorted(set(required)-set(granted))
receipt={
    'schema':'SOVARA_G3_DEPLOYER_PERMISSION_PREFLIGHT_V1',
    'required_permissions':required,
    'granted_permissions':granted,
    'missing_permissions':missing,
    'cold_start_create_delete_ready':not missing,
}
print(json.dumps(receipt,sort_keys=True))
if missing:
    raise SystemExit(f'G3 cold-start create/delete permissions missing: {missing}')
PY
unset ACCESS_TOKEN

IMAGE_NAME="sovara-gemini-gateway"
IMAGE_TAG="g3-${SOURCE_SHA:0:12}-${RUN_ID}-${RUN_ATTEMPT}"
IMAGE_TAG_REF="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"
CANARY_TAG="g3-${SOURCE_SHA:0:8}"

if [[ "$MODE" == "plan" ]]; then
  python3 - <<PY
import hashlib, json
r={
  'schema':'SOVARA_GEMINI_PRIVATE_CANARY_PLAN_V1',
  'state':'READY_FOR_PRIVATE_CANARY_EXECUTION',
  'project_id':'${PROJECT_ID}',
  'project_number':'${PROJECT_NUMBER}',
  'region':'${REGION}',
  'service':'${SERVICE}',
  'runtime_service_account':'${RUNTIME_SA}',
  'deployer_service_account':'${DEPLOYER_SA}',
  'source_sha':'${SOURCE_SHA}',
  'image_tag_ref':'${IMAGE_TAG_REF}',
  'canary_tag':'${CANARY_TAG}',
  'production_traffic_change_authorized':False,
  'provider_mutation_performed':False,
}
r['receipt_sha256']=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
print(json.dumps(r,sort_keys=True))
PY
  exit 0
fi

if [[ "${SOVARA_G3_PRIVATE_CANARY_EXECUTE:-}" != "$EXECUTE_CONFIRMATION" ]]; then
  echo "Refusing provider effect without SOVARA_G3_PRIVATE_CANARY_EXECUTE=${EXECUTE_CONFIRMATION}" >&2
  exit 5
fi

# Capture pre-effect provider state for rollback/readback attribution.
SERVICE_PREEXISTED=false
PREVIOUS_READY=""
TARGET_SERVICE="$SERVICE"
DEPLOYMENT_MODE="EXISTING_SERVICE_ZERO_TRAFFIC"
EPHEMERAL_SERVICE=false
EPHEMERAL_CREATED=false
EPHEMERAL_SERVICE_NAME="sovara-gemini-g3-${RUN_ID}-${RUN_ATTEMPT}"

if gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format=json \
  > "$RECEIPT_DIR/G3_SERVICE_BEFORE.json" 2>/dev/null; then
  SERVICE_PREEXISTED=true
  PREVIOUS_READY="$(python3 - "$RECEIPT_DIR/G3_SERVICE_BEFORE.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
print((p.get('status') or {}).get('latestReadyRevisionName') or '')
PY
)"
else
  : > "$RECEIPT_DIR/G3_SERVICE_BEFORE.json"
  TARGET_SERVICE="$EPHEMERAL_SERVICE_NAME"
  DEPLOYMENT_MODE="EPHEMERAL_SERVICE_COLD_START"
  EPHEMERAL_SERVICE=true
fi

cleanup_on_exit() {
  rc=$?
  trap - EXIT
  if [[ "$EPHEMERAL_CREATED" == true ]]; then
    gcloud run services delete "$TARGET_SERVICE" \
      --project "$PROJECT_ID" --region "$REGION" --quiet >/dev/null 2>&1 || true
  fi
  exit "$rc"
}
trap cleanup_on_exit EXIT

# Build and publish exact admitted source. The deploy step uses the immutable digest, not the tag.
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
docker build --pull -f services/gemini_gateway/Dockerfile -t "$IMAGE_TAG_REF" .
docker push "$IMAGE_TAG_REF"
DIGEST="$(gcloud artifacts docker images describe "$IMAGE_TAG_REF" --project "$PROJECT_ID" --format='value(image_summary.digest)')"
[[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo "Immutable Artifact Registry digest missing" >&2; exit 6; }
IMAGE_DIGEST_REF="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}@${DIGEST}"
printf '%s\n' "$IMAGE_DIGEST_REF" > "$RECEIPT_DIR/G3_IMAGE_DIGEST_REF.txt"

if [[ "$SERVICE_PREEXISTED" == true ]]; then
  # Existing canonical service: add a tagged revision with zero normal service traffic.
  gcloud run deploy "$SERVICE" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --image "$IMAGE_DIGEST_REF" \
    --service-account "$RUNTIME_SA" \
    --platform managed \
    --tag "$CANARY_TAG" \
    --no-traffic \
    --no-allow-unauthenticated \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=global,GEMINI_MODEL=${MODEL},INTERACTIONS_MODEL=${INTERACTIONS_MODEL},EXPECTED_RUNTIME_SERVICE_ACCOUNT=${RUNTIME_SA}" \
    --quiet
else
  # Cold start: gcloud does not support --no-traffic for the first revision.
  # Use a uniquely named authenticated ephemeral service, never the production
  # service name; prove semantics, then delete and verify absence.
  gcloud run deploy "$TARGET_SERVICE" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --image "$IMAGE_DIGEST_REF" \
    --service-account "$RUNTIME_SA" \
    --platform managed \
    --no-allow-unauthenticated \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=global,GEMINI_MODEL=${MODEL},INTERACTIONS_MODEL=${INTERACTIONS_MODEL},EXPECTED_RUNTIME_SERVICE_ACCOUNT=${RUNTIME_SA}" \
    --quiet
  EPHEMERAL_CREATED=true
fi

gcloud run services describe "$TARGET_SERVICE" --project "$PROJECT_ID" --region "$REGION" --format=json \
  > "$RECEIPT_DIR/G3_SERVICE_AFTER_DEPLOY.json"

python3 - "$RECEIPT_DIR/G3_SERVICE_AFTER_DEPLOY.json" "$CANARY_TAG" "$IMAGE_DIGEST_REF" "$RUNTIME_SA" "$DEPLOYMENT_MODE" "$SERVICE" "$TARGET_SERVICE" <<'PY' > "$RECEIPT_DIR/G3_CANARY_TARGET.json"
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
tag=sys.argv[2]
expected_image=sys.argv[3]
expected_sa=sys.argv[4]
mode=sys.argv[5]
production_service=sys.argv[6]
target_service=sys.argv[7]
status=p.get('status') or {}
spec=p.get('spec') or {}
template=spec.get('template') or {}
tmpl_spec=template.get('spec') or {}
metadata=p.get('metadata') or {}
created=status.get('latestCreatedRevisionName') or ''
ready=status.get('latestReadyRevisionName') or ''
if not created or created != ready:
    raise SystemExit(f'canary revision not ready: created={created!r}, ready={ready!r}')
observed_name=str(metadata.get('name') or '')
if observed_name and observed_name != target_service:
    raise SystemExit(f'canary service identity mismatch: {observed_name!r}')
containers=tmpl_spec.get('containers') or []
observed_image=str((containers[0] if containers else {}).get('image') or '')
if observed_image != expected_image:
    raise SystemExit(f'image digest readback mismatch: {observed_image!r}')
observed_sa=str(tmpl_spec.get('serviceAccountName') or '')
if observed_sa != expected_sa:
    raise SystemExit(f'runtime service account mismatch: {observed_sa!r}')
traffic=status.get('traffic') or []
if mode == 'EXISTING_SERVICE_ZERO_TRAFFIC':
    tagged=next((x for x in traffic if x.get('tag')==tag),{})
    url=str(tagged.get('url') or '')
    if not url:
        raise SystemExit('tagged canary URL missing')
    canary_percent=sum(int(x.get('percent') or 0) for x in traffic if x.get('revisionName')==created)
    if canary_percent != 0:
        raise SystemExit(f'canary unexpectedly has normal traffic allocation: {canary_percent}')
    ephemeral_percent=None
    production_mutated=True
else:
    url=str(status.get('url') or '')
    if not url:
        raise SystemExit('ephemeral canary service URL missing')
    ephemeral_percent=sum(int(x.get('percent') or 0) for x in traffic if x.get('revisionName')==created)
    if ephemeral_percent != 100:
        raise SystemExit(f'cold-start ephemeral service expected 100 percent private canary traffic: {ephemeral_percent}')
    canary_percent=0
    production_mutated=False
print(json.dumps({
  'revision':created,
  'tag':tag if mode=='EXISTING_SERVICE_ZERO_TRAFFIC' else None,
  'invocation_url':url,
  'image_digest_ref':observed_image,
  'runtime_service_account':observed_sa,
  'deployment_mode':mode,
  'production_service':production_service,
  'canary_service':target_service,
  'ephemeral_service':mode=='EPHEMERAL_SERVICE_COLD_START',
  'ephemeral_service_traffic_percent':ephemeral_percent,
  'normal_traffic_percent':canary_percent,
  'production_service_mutated':production_mutated,
},sort_keys=True))
PY

CANARY_URL="$(python3 - "$RECEIPT_DIR/G3_CANARY_TARGET.json" <<'PY'
import json,sys
print(json.load(open(sys.argv[1]))['invocation_url'])
PY
)"
CANARY_REVISION="$(python3 - "$RECEIPT_DIR/G3_CANARY_TARGET.json" <<'PY'
import json,sys
print(json.load(open(sys.argv[1]))['revision'])
PY
)"

ID_TOKEN="$(gcloud auth print-identity-token --audiences="$CANARY_URL")"
[[ -n "$ID_TOKEN" ]] || { echo "Identity token acquisition failed" >&2; exit 7; }

curl --fail --silent --show-error -H "Authorization: Bearer $ID_TOKEN" "$CANARY_URL/health" \
  > "$RECEIPT_DIR/G3_HEALTH.json"
curl --fail --silent --show-error -H "Authorization: Bearer $ID_TOKEN" "$CANARY_URL/ready" \
  > "$RECEIPT_DIR/G3_READY.json"
NONCE="G3-${RUN_ID}-${RUN_ATTEMPT}-${SOURCE_SHA:0:12}"
curl --fail --silent --show-error \
  -H "Authorization: Bearer $ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"semantic_nonce\":\"${NONCE}\"}" \
  "$CANARY_URL/v1/handshake" > "$RECEIPT_DIR/G3_HANDSHAKE.json"

INTERACTIONS_NONCE="G3I-${RUN_ID}-${RUN_ATTEMPT}-${SOURCE_SHA:0:12}"
curl --fail --silent --show-error \
  -H "Authorization: Bearer $ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"semantic_nonce\":\"${INTERACTIONS_NONCE}\"}" \
  "$CANARY_URL/v2/interactions-handshake" > "$RECEIPT_DIR/G3_INTERACTIONS_HANDSHAKE.json"

python3 - "$RECEIPT_DIR/G3_HEALTH.json" "$RECEIPT_DIR/G3_READY.json" "$RECEIPT_DIR/G3_HANDSHAKE.json" "$RECEIPT_DIR/G3_INTERACTIONS_HANDSHAKE.json" "$RECEIPT_DIR/G3_CANARY_TARGET.json" "$NONCE" "$INTERACTIONS_NONCE" "$PROJECT_ID" "$PROJECT_NUMBER" "$RUNTIME_SA" "$SOURCE_SHA" "$SERVICE_PREEXISTED" "$PREVIOUS_READY" <<'PY' > "$RECEIPT_DIR/G3_PRIVATE_CANARY_RECEIPT.json"
import hashlib,json,sys
health=json.load(open(sys.argv[1],encoding='utf-8'))
ready=json.load(open(sys.argv[2],encoding='utf-8'))
hs=json.load(open(sys.argv[3],encoding='utf-8'))
ihs=json.load(open(sys.argv[4],encoding='utf-8'))
target=json.load(open(sys.argv[5],encoding='utf-8'))
nonce,interactions_nonce,project,number,runtime,source=sys.argv[6:12]
service_preexisted=(sys.argv[12].lower()=='true')
previous_ready=sys.argv[13]
assert health.get('status')=='HEALTHY', health
assert health.get('provider_execution_verified') is False, health
assert ready.get('status')=='READY_IDENTITY_VERIFIED', ready
identity=ready.get('provider_identity') or {}
assert identity.get('project_id')==project, ready
assert str(identity.get('project_number'))==number, ready
assert identity.get('service_account')==runtime, ready
assert hs.get('schema')=='SOVARA_GEMINI_HANDSHAKE_RECEIPT_V1', hs
assert hs.get('status')=='VERIFIED' and hs.get('semantic_verified') is True, hs
assert hs.get('semantic_nonce')==nonce, hs
assert hs.get('provider_request_id'), hs
assert hs.get('model_identity'), hs
assert hs.get('finish_state'), hs
assert isinstance(hs.get('usage'),dict), hs
assert len(str(hs.get('receipt_sha256') or ''))==64, hs
assert ihs.get('schema')=='SOVARA_GEMINI_INTERACTIONS_HANDSHAKE_RECEIPT_V2', ihs
assert ihs.get('status')=='VERIFIED' and ihs.get('semantic_verified') is True, ihs
assert ihs.get('semantic_nonce')==interactions_nonce, ihs
assert ihs.get('protocol')=='VERTEX_AI_INTERACTIONS_REST', ihs
assert ihs.get('configured_model')=='gemini-3.8-flash', ihs
assert ihs.get('interaction_id') and ihs.get('provider_request_id'), ihs
assert ihs.get('interaction_status')=='completed', ihs
assert ihs.get('store') is False, ihs
assert isinstance(ihs.get('usage'),dict), ihs
assert len(str(ihs.get('receipt_sha256') or ''))==64, ihs
assert target.get('normal_traffic_percent')==0, target
r={
  'receipt':'FEDOMEGA-GEMINI-GATEWAY-CANARY-VERIFIED',
  'state':'VERIFIED',
  'project_id':project,
  'project_number':number,
  'source_sha':source,
  'service':'sovara-gemini-gateway',
  'revision':target['revision'],
  'tag':target['tag'],
  'image_digest_ref':target['image_digest_ref'],
  'runtime_service_account':runtime,
  'normal_traffic_percent':0,
  'provider_request_id':hs['provider_request_id'],
  'model_identity':hs['model_identity'],
  'semantic_nonce_sha256':hs['semantic_nonce_sha256'],
  'handshake_receipt_sha256':hs['receipt_sha256'],
  'interactions_provider_request_id':ihs['provider_request_id'],
  'interactions_interaction_id':ihs['interaction_id'],
  'interactions_model_identity':ihs['model_identity'],
  'interactions_semantic_nonce_sha256':ihs['semantic_nonce_sha256'],
  'interactions_handshake_receipt_sha256':ihs['receipt_sha256'],
  'interactions_store':ihs['store'],
  'service_preexisted':service_preexisted,
  'previous_ready_revision':previous_ready,
  'production_promotion_performed':False,
  'case_data_processed':False,
  'credential_values_recorded':False,
}
r['receipt_sha256']=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
print(json.dumps(r,indent=2,sort_keys=True))
PY

cat "$RECEIPT_DIR/G3_PRIVATE_CANARY_RECEIPT.json"
