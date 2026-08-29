#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sov-hybrid-suite}"
PROJECT_NUMBER="${PROJECT_NUMBER:-257649435135}"
DEPLOYER_SA="superior-logic-deployer@${PROJECT_ID}.iam.gserviceaccount.com"
RUNTIME_SA="superior-logic-runtime@${PROJECT_ID}.iam.gserviceaccount.com"
APPLY_CONFIRMATION="ATTACH_EXACT_GEMINI_ADC_BINDINGS_V1"
ROLLBACK_CONFIRMATION="ROLLBACK_EXACT_GEMINI_ADC_BINDINGS_V1"
RECEIPT_DIR="${SOVARA_OWNER_IAM_RECEIPT_DIR:-./receipts/sovara-gemini-owner-iam}"
MODE="plan"
RECEIPT_FILE=""

case "${1:-}" in
  ""|--plan) MODE="plan" ;;
  --apply) MODE="apply" ;;
  --rollback)
    MODE="rollback"
    RECEIPT_FILE="${2:-}"
    [[ -n "$RECEIPT_FILE" ]] || { echo "--rollback requires a prior receipt path" >&2; exit 2; }
    ;;
  -h|--help)
    echo "Usage: sovara/gemini/owner_iam_bootstrap.sh [--plan|--apply|--rollback RECEIPT.json]"
    exit 0
    ;;
  *) echo "Unknown mode: ${1}" >&2; exit 2 ;;
esac

for bin in gcloud python3; do
  command -v "$bin" >/dev/null 2>&1 || { echo "Missing required command: $bin" >&2; exit 1; }
done
[[ "$PROJECT_ID" == "sov-hybrid-suite" ]] || { echo "Canonical project mismatch" >&2; exit 3; }
[[ "$PROJECT_NUMBER" == "257649435135" ]] || { echo "Canonical project number mismatch" >&2; exit 3; }

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
[[ -n "$ACTIVE_ACCOUNT" ]] || { echo "No active Google identity" >&2; exit 4; }
[[ "$ACTIVE_ACCOUNT" != "$DEPLOYER_SA" ]] || { echo "Refusing to use the ordinary deployment identity for project-IAM administration" >&2; exit 4; }
OBSERVED_PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
[[ "$OBSERVED_PROJECT_NUMBER" == "$PROJECT_NUMBER" ]] || { echo "Provider project number mismatch" >&2; exit 4; }

ACCESS_TOKEN="$(gcloud auth print-access-token)"
[[ -n "$ACCESS_TOKEN" ]] || { echo "Unable to obtain access token for active owner/admin identity" >&2; exit 4; }
export ACCESS_TOKEN PROJECT_ID
python3 - <<'PY'
import json, os, urllib.request
body=json.dumps({'permissions':['resourcemanager.projects.getIamPolicy','resourcemanager.projects.setIamPolicy']},separators=(',',':')).encode()
req=urllib.request.Request(
    f"https://cloudresourcemanager.googleapis.com/v1/projects/{os.environ['PROJECT_ID']}:testIamPermissions",
    data=body,
    method='POST',
    headers={'Authorization':f"Bearer {os.environ['ACCESS_TOKEN']}",'Content-Type':'application/json','X-Goog-User-Project':os.environ['PROJECT_ID']},
)
with urllib.request.urlopen(req,timeout=30) as r:
    granted=set(json.loads(r.read().decode() or '{}').get('permissions') or [])
required={'resourcemanager.projects.getIamPolicy','resourcemanager.projects.setIamPolicy'}
if not required <= granted:
    raise SystemExit(f"Active identity lacks exact project-IAM authority: missing={sorted(required-granted)}")
PY
unset ACCESS_TOKEN

has_binding() {
  local member="$1" role="$2"
  local found
  found="$(gcloud projects get-iam-policy "$PROJECT_ID" \
    --flatten='bindings[].members' \
    --filter="bindings.role:${role} AND bindings.members:${member}" \
    --format='value(bindings.role)' 2>/dev/null || true)"
  grep -Fxq "$role" <<<"$found"
}

RUNTIME_AI=false
RUNTIME_SERVICE_USAGE=false
DEPLOYER_RUN=false
has_binding "serviceAccount:${RUNTIME_SA}" "roles/aiplatform.user" && RUNTIME_AI=true || true
has_binding "serviceAccount:${RUNTIME_SA}" "roles/serviceusage.serviceUsageConsumer" && RUNTIME_SERVICE_USAGE=true || true
has_binding "serviceAccount:${DEPLOYER_SA}" "roles/run.developer" && DEPLOYER_RUN=true || true

emit_plan() {
  python3 - "$ACTIVE_ACCOUNT" "$RUNTIME_AI" "$RUNTIME_SERVICE_USAGE" "$DEPLOYER_RUN" <<'PY'
import hashlib,json,sys
principal_sha=hashlib.sha256(sys.argv[1].encode()).hexdigest()
r={
 'schema':'SOVARA_GEMINI_OWNER_IAM_PLAN_V1',
 'project_id':'sov-hybrid-suite',
 'project_number':'257649435135',
 'active_admin_principal_sha256':principal_sha,
 'runtime_service_account':'superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com',
 'deployer_service_account':'superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com',
 'before':{
   'runtime_aiplatform_user':sys.argv[2].lower()=='true',
   'runtime_service_usage_consumer':sys.argv[3].lower()=='true',
   'deployer_run_developer':sys.argv[4].lower()=='true',
 },
 'required_mutation_count':sum(1 for x in sys.argv[2:5] if x.lower()!='true'),
 'service_account_creation_allowed':False,
 'key_creation_allowed':False,
 'wif_mutation_allowed':False,
 'api_enablement_allowed':False,
}
r['receipt_sha256']=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
print(json.dumps(r,indent=2,sort_keys=True))
PY
}

if [[ "$MODE" == "plan" ]]; then
  emit_plan
  exit 0
fi

if [[ "$MODE" == "rollback" ]]; then
  [[ "${SOVARA_OWNER_IAM_ROLLBACK:-}" == "$ROLLBACK_CONFIRMATION" ]] || { echo "Rollback confirmation missing" >&2; exit 5; }
  python3 - "$RECEIPT_FILE" <<'PY' > /tmp/sovara-owner-iam-rollback.tsv
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
assert p.get('schema')=='SOVARA_GEMINI_OWNER_IAM_APPLY_RECEIPT_V1', p
assert p.get('project_id')=='sov-hybrid-suite', p
for item in p.get('bindings_added') or []:
    print(item['member'], item['role'], sep='\t')
PY
  while IFS=$'\t' read -r member role; do
    [[ -n "$member" && -n "$role" ]] || continue
    gcloud projects remove-iam-policy-binding "$PROJECT_ID" --member "$member" --role "$role" --condition=None --quiet >/dev/null
  done < /tmp/sovara-owner-iam-rollback.tsv
  echo "Rollback completed for only the bindings recorded as added by the referenced receipt."
  exit 0
fi

[[ "${SOVARA_OWNER_IAM_APPLY:-}" == "$APPLY_CONFIRMATION" ]] || { echo "Refusing IAM mutation without SOVARA_OWNER_IAM_APPLY=${APPLY_CONFIRMATION}" >&2; exit 5; }
mkdir -p "$RECEIPT_DIR"
BINDINGS_ADDED_FILE="$(mktemp)"

add_if_missing() {
  local member="$1" role="$2" present="$3"
  if [[ "$present" != true ]]; then
    gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "$member" --role "$role" --condition=None --quiet >/dev/null
    printf '%s\t%s\n' "$member" "$role" >> "$BINDINGS_ADDED_FILE"
  fi
}

add_if_missing "serviceAccount:${RUNTIME_SA}" "roles/aiplatform.user" "$RUNTIME_AI"
add_if_missing "serviceAccount:${RUNTIME_SA}" "roles/serviceusage.serviceUsageConsumer" "$RUNTIME_SERVICE_USAGE"
add_if_missing "serviceAccount:${DEPLOYER_SA}" "roles/run.developer" "$DEPLOYER_RUN"

AFTER_RUNTIME_AI=false
AFTER_RUNTIME_SERVICE_USAGE=false
AFTER_DEPLOYER_RUN=false
has_binding "serviceAccount:${RUNTIME_SA}" "roles/aiplatform.user" && AFTER_RUNTIME_AI=true || true
has_binding "serviceAccount:${RUNTIME_SA}" "roles/serviceusage.serviceUsageConsumer" && AFTER_RUNTIME_SERVICE_USAGE=true || true
has_binding "serviceAccount:${DEPLOYER_SA}" "roles/run.developer" && AFTER_DEPLOYER_RUN=true || true
[[ "$AFTER_RUNTIME_AI" == true && "$AFTER_RUNTIME_SERVICE_USAGE" == true && "$AFTER_DEPLOYER_RUN" == true ]] || { echo "Post-IAM provider readback failed" >&2; exit 6; }

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$RECEIPT_DIR/SOVARA_GEMINI_OWNER_IAM_APPLY_${STAMP}.json"
python3 - "$OUT" "$ACTIVE_ACCOUNT" "$RUNTIME_AI" "$RUNTIME_SERVICE_USAGE" "$DEPLOYER_RUN" "$BINDINGS_ADDED_FILE" <<'PY'
import hashlib,json,sys
out,active=sys.argv[1:3]
before=[x.lower()=='true' for x in sys.argv[3:6]]
added=[]
for line in open(sys.argv[6],encoding='utf-8'):
    member,role=line.rstrip('\n').split('\t',1)
    added.append({'member':member,'role':role})
r={
 'schema':'SOVARA_GEMINI_OWNER_IAM_APPLY_RECEIPT_V1',
 'state':'VERIFIED',
 'project_id':'sov-hybrid-suite',
 'project_number':'257649435135',
 'active_admin_principal_sha256':hashlib.sha256(active.encode()).hexdigest(),
 'runtime_service_account':'superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com',
 'deployer_service_account':'superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com',
 'before':{
   'runtime_aiplatform_user':before[0],
   'runtime_service_usage_consumer':before[1],
   'deployer_run_developer':before[2],
 },
 'after':{
   'runtime_aiplatform_user':True,
   'runtime_service_usage_consumer':True,
   'deployer_run_developer':True,
 },
 'bindings_added':added,
 'provider_readback_verified':True,
 'service_account_created':False,
 'service_account_key_created':False,
 'wif_mutated':False,
 'api_enablement_mutated':False,
}
r['receipt_sha256']=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
open(out,'w',encoding='utf-8').write(json.dumps(r,indent=2,sort_keys=True)+'\n')
print(json.dumps(r,indent=2,sort_keys=True))
PY
printf 'Receipt: %s\n' "$OUT"
