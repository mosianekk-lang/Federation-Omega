#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sov-hybrid-suite}"
PROJECT_NUMBER="${PROJECT_NUMBER:-257649435135}"
POOL_ID="${POOL_ID:-github-federation-omega}"
PROVIDER_ID="${PROVIDER_ID:-github}"
DEPLOYER_SA="${DEPLOYER_SA:-superior-logic-deployer@${PROJECT_ID}.iam.gserviceaccount.com}"
REPOSITORY_ID="1292795464"
OWNER_ID="261966700"
CANONICAL_WORKFLOW="mosianekk-lang/Federation-Omega/.github/workflows/sovara-litellm-v2-3-provider-admission.yml@refs/heads/main"
POOL_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"
EXACT_PRINCIPAL="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository_id/${REPOSITORY_ID}"
BROAD_PRINCIPAL="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository/mosianekk-lang/Federation-Omega"
EXPECTED_CONDITION="assertion.repository_id=='${REPOSITORY_ID}' && assertion.repository_owner_id=='${OWNER_ID}' && assertion.ref=='refs/heads/main' && assertion.job_workflow_ref=='${CANONICAL_WORKFLOW}' && (assertion.event_name=='workflow_dispatch' || assertion.event_name=='push')"
EXPECTED_MAPPING="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id,attribute.ref=assertion.ref,attribute.event_name=assertion.event_name,attribute.workflow_ref=assertion.job_workflow_ref"
APPLY_CONFIRMATION="HARDEN_SOVARA_CANONICAL_WIF_V1"

MODE="plan"
case "${1:-}" in
  ""|--plan) MODE="plan" ;;
  --verify) MODE="verify" ;;
  --apply) MODE="apply" ;;
  -h|--help)
    cat <<'USAGE'
Usage: ops/harden_sovara_provider_wif_v1.sh [--plan|--verify|--apply]

--plan   Read-only. Report the exact canonical SOVARA WIF hardening delta.
--verify Read-only. Succeeds only when the hardened provider contract and exact repository-ID binding are present and the broad repository-name binding is absent.
--apply  Apply only that hardening delta. Requires:
         SOVARA_WIF_HARDENING_APPROVAL=HARDEN_SOVARA_CANONICAL_WIF_V1

This script does not enable APIs, create service accounts, grant project roles,
modify Cloud Run/Artifact Registry, access secrets, run model inference, or
change application traffic.
USAGE
    exit 0
    ;;
  *) echo "Unknown mode: ${1}" >&2; exit 2 ;;
esac

for bin in gcloud python3; do
  command -v "$bin" >/dev/null 2>&1 || { echo "Missing required command: $bin" >&2; exit 1; }
done

read_value() { "$@" 2>/dev/null || true; }

binding_present() {
  local member="$1"
  local result
  result="$(read_value gcloud iam service-accounts get-iam-policy "$DEPLOYER_SA" \
    --project "$PROJECT_ID" \
    --flatten='bindings[].members' \
    --filter="bindings.role:roles/iam.workloadIdentityUser AND bindings.members:${member}" \
    --format='value(bindings.role)')"
  grep -Fxq 'roles/iam.workloadIdentityUser' <<<"$result"
}

sorted_mapping() {
  python3 - "$1" <<'PY'
import sys
print(','.join(sorted(x.strip() for x in sys.argv[1].split(',') if x.strip())))
PY
}

collect_state() {
  ACTIVE_ACCOUNT="$(read_value gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
  ACTUAL_PROJECT_NUMBER="$(read_value gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' | head -n1)"
  PROVIDER_JSON="$(read_value gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
    --project "$PROJECT_ID" --location global --workload-identity-pool "$POOL_ID" --format=json)"
  [[ -n "$PROVIDER_JSON" ]] || { echo "Canonical WIF provider is not readable." >&2; exit 4; }

  readarray -t FIELDS < <(python3 - "$PROVIDER_JSON" <<'PY'
import json,sys
p=json.loads(sys.argv[1])
print(p.get('state','NOT_FOUND'))
print(p.get('attributeCondition',''))
m=p.get('attributeMapping') or {}
print(','.join(f'{k}={m[k]}' for k in sorted(m)))
PY
)
  PROVIDER_STATE="${FIELDS[0]:-NOT_FOUND}"
  OBSERVED_CONDITION="${FIELDS[1]:-}"
  OBSERVED_MAPPING="${FIELDS[2]:-}"
  SORTED_EXPECTED_MAPPING="$(sorted_mapping "$EXPECTED_MAPPING")"

  CONDITION_MATCH=false
  MAPPING_MATCH=false
  EXACT_BINDING=false
  BROAD_BINDING=false
  [[ "$OBSERVED_CONDITION" == "$EXPECTED_CONDITION" ]] && CONDITION_MATCH=true || true
  [[ "$OBSERVED_MAPPING" == "$SORTED_EXPECTED_MAPPING" ]] && MAPPING_MATCH=true || true
  binding_present "$EXACT_PRINCIPAL" && EXACT_BINDING=true || true
  binding_present "$BROAD_PRINCIPAL" && BROAD_BINDING=true || true

  REQUIRED=()
  [[ "$CONDITION_MATCH" == true ]] || REQUIRED+=("UPDATE_PROVIDER_ATTRIBUTE_CONDITION")
  [[ "$MAPPING_MATCH" == true ]] || REQUIRED+=("UPDATE_PROVIDER_ATTRIBUTE_MAPPING")
  [[ "$EXACT_BINDING" == true ]] || REQUIRED+=("ADD_EXACT_REPOSITORY_ID_WIF_BINDING")
  [[ "$BROAD_BINDING" == false ]] || REQUIRED+=("REMOVE_BROAD_REPOSITORY_NAME_WIF_BINDING")
}

emit_receipt() {
  local state="$1"
  local mutation="${2:-false}"
  local required_json
  required_json="$(printf '%s\n' "${REQUIRED[@]:-}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
  EXPECTED_CONDITION_SHA="$(printf '%s' "$EXPECTED_CONDITION" | sha256sum | awk '{print $1}')"
  OBSERVED_CONDITION_SHA="$(printf '%s' "$OBSERVED_CONDITION" | sha256sum | awk '{print $1}')"
  EXPECTED_MAPPING_SHA="$(printf '%s' "$SORTED_EXPECTED_MAPPING" | sha256sum | awk '{print $1}')"
  OBSERVED_MAPPING_SHA="$(printf '%s' "$OBSERVED_MAPPING" | sha256sum | awk '{print $1}')"
  python3 - <<PY
import hashlib,json
r={
  'schema':'SOVARA_WIF_HARDENING_V1',
  'mode':'${MODE}',
  'state':'${state}',
  'project_id':'${PROJECT_ID}',
  'project_number_expected':'${PROJECT_NUMBER}',
  'project_number_observed':'${ACTUAL_PROJECT_NUMBER}',
  'active_account':'${ACTIVE_ACCOUNT}',
  'provider_state':'${PROVIDER_STATE}',
  'condition_match':${CONDITION_MATCH},
  'mapping_match':${MAPPING_MATCH},
  'exact_repository_id_binding_present':${EXACT_BINDING},
  'broad_repository_name_binding_present':${BROAD_BINDING},
  'expected_condition_sha256':'${EXPECTED_CONDITION_SHA}',
  'observed_condition_sha256':'${OBSERVED_CONDITION_SHA}',
  'expected_mapping_sha256':'${EXPECTED_MAPPING_SHA}',
  'observed_mapping_sha256':'${OBSERVED_MAPPING_SHA}',
  'required_mutations':${required_json},
  'mutation_performed':${mutation},
  'api_enablement_performed':False,
  'project_role_binding_performed':False,
  'service_account_created':False,
  'secret_payload_accessed':False,
  'model_inference_performed':False,
  'traffic_change_performed':False,
}
r['receipt_sha256']=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
print(json.dumps(r,sort_keys=True))
PY
}

collect_state
[[ "$ACTUAL_PROJECT_NUMBER" == "$PROJECT_NUMBER" ]] || { emit_receipt "PROJECT_MISMATCH" false; exit 5; }
[[ "$PROVIDER_STATE" == "ACTIVE" ]] || { emit_receipt "PROVIDER_NOT_ACTIVE" false; exit 6; }

if [[ "$MODE" == "plan" ]]; then
  if ((${#REQUIRED[@]} == 0)); then emit_receipt "ALREADY_HARDENED" false; else emit_receipt "HARDENING_REQUIRED" false; fi
  exit 0
fi

if [[ "$MODE" == "verify" ]]; then
  if ((${#REQUIRED[@]} != 0)); then emit_receipt "NOT_VERIFIED" false; exit 1; fi
  emit_receipt "VERIFIED" false
  exit 0
fi

if [[ "${SOVARA_WIF_HARDENING_APPROVAL:-}" != "$APPLY_CONFIRMATION" ]]; then
  emit_receipt "APPROVAL_REQUIRED" false
  echo "Refusing mutation without SOVARA_WIF_HARDENING_APPROVAL=${APPLY_CONFIRMATION}" >&2
  exit 3
fi
[[ "$ACTIVE_ACCOUNT" == "$DEPLOYER_SA" ]] || {
  emit_receipt "ACTIVE_ACCOUNT_MISMATCH" false
  echo "Refusing mutation: active Google account is not the canonical deployer." >&2
  exit 7
}

# Safe ordering: establish the exact repository-ID binding first. Then harden the
# provider mapping/condition. Remove the old broad repository-name binding last.
# If the final removal fails, the new provider mapping no longer exports
# attribute.repository, so the broad binding is inert rather than authoritative.
if [[ "$EXACT_BINDING" != true ]]; then
  gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" \
    --project "$PROJECT_ID" \
    --role roles/iam.workloadIdentityUser \
    --member "$EXACT_PRINCIPAL" >/dev/null
fi

if [[ "$CONDITION_MATCH" != true || "$MAPPING_MATCH" != true ]]; then
  gcloud iam workload-identity-pools providers update-oidc "$PROVIDER_ID" \
    --project "$PROJECT_ID" \
    --location global \
    --workload-identity-pool "$POOL_ID" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="$EXPECTED_MAPPING" \
    --attribute-condition="$EXPECTED_CONDITION"
fi

if [[ "$BROAD_BINDING" == true ]]; then
  gcloud iam service-accounts remove-iam-policy-binding "$DEPLOYER_SA" \
    --project "$PROJECT_ID" \
    --role roles/iam.workloadIdentityUser \
    --member "$BROAD_PRINCIPAL" >/dev/null
fi

collect_state
if ((${#REQUIRED[@]} != 0)); then
  emit_receipt "APPLIED_BUT_VERIFICATION_FAILED" true
  exit 8
fi
emit_receipt "APPLIED_AND_VERIFIED" true
