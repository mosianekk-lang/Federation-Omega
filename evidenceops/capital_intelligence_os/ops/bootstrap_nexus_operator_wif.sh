#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sov-hybrid-suite}"
PROJECT_NUMBER="${PROJECT_NUMBER:-257649435135}"
POOL_ID="${POOL_ID:-github-federation-omega}"
PROVIDER_ID="${PROVIDER_ID:-github}"
GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-mosianekk-lang/Federation-Omega}"
DEPLOYER_SA="${DEPLOYER_SA:-superior-logic-deployer@${PROJECT_ID}.iam.gserviceaccount.com}"
SECRET_ID="${SECRET_ID:-fo-operator-admin-token}"
PROVIDER_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"
POOL_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"
PRINCIPAL="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository/${GITHUB_REPOSITORY}"
EXPECTED_CONDITION="assertion.repository=='${GITHUB_REPOSITORY}' && assertion.ref=='refs/heads/main'"
EXPECTED_MAPPING="attribute.ref=assertion.ref,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner,google.subject=assertion.sub"
APPLY_CONFIRMATION="APPLY_NEXUS_OPERATOR_WIF_LEAST_PRIVILEGE"
MODE="${1:---plan}"

require() { command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }; }
require gcloud
require python3

read_value() { "$@" 2>/dev/null || true; }
exact_line() { grep -Fxq "$1" <<<"${2:-}"; }

collect_state() {
  ACTIVE_ACCOUNT="$(read_value gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
  ACTUAL_PROJECT_NUMBER="$(read_value gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' | head -n1)"
  DEPLOYER_EXISTS=false
  SECRET_EXISTS=false
  POOL_STATE="$(read_value gcloud iam workload-identity-pools describe "$POOL_ID" --project "$PROJECT_ID" --location global --format='value(state)' | head -n1)"
  [[ -n "$POOL_STATE" ]] || POOL_STATE=NOT_FOUND
  PROVIDER_STATE=NOT_FOUND
  PROVIDER_CONDITION=""
  PROVIDER_MAPPING=""

  gcloud iam service-accounts describe "$DEPLOYER_SA" --project "$PROJECT_ID" >/dev/null 2>&1 && DEPLOYER_EXISTS=true
  gcloud secrets describe "$SECRET_ID" --project "$PROJECT_ID" >/dev/null 2>&1 && SECRET_EXISTS=true

  provider_json="$(read_value gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" --project "$PROJECT_ID" --location global --workload-identity-pool "$POOL_ID" --format=json)"
  if [[ -n "$provider_json" ]]; then
    readarray -t fields < <(python3 - "$provider_json" <<'PY'
import json,sys
obj=json.loads(sys.argv[1])
print(obj.get('state','NOT_FOUND'))
print(obj.get('attributeCondition',''))
m=obj.get('attributeMapping',{})
print(','.join(f'{k}={m[k]}' for k in sorted(m)))
PY
)
    PROVIDER_STATE="${fields[0]:-NOT_FOUND}"
    PROVIDER_CONDITION="${fields[1]:-}"
    PROVIDER_MAPPING="${fields[2]:-}"
  fi

  WIF_BINDING=false
  SECRET_ACCESS=false
  if [[ "$DEPLOYER_EXISTS" == true ]]; then
    result="$(read_value gcloud iam service-accounts get-iam-policy "$DEPLOYER_SA" --project "$PROJECT_ID" --flatten='bindings[].members' --filter="bindings.role:roles/iam.workloadIdentityUser AND bindings.members:${PRINCIPAL}" --format='value(bindings.role)')"
    exact_line roles/iam.workloadIdentityUser "$result" && WIF_BINDING=true
  fi
  if [[ "$SECRET_EXISTS" == true ]]; then
    result="$(read_value gcloud secrets get-iam-policy "$SECRET_ID" --project "$PROJECT_ID" --flatten='bindings[].members' --filter="bindings.role:roles/secretmanager.secretAccessor AND bindings.members:serviceAccount:${DEPLOYER_SA}" --format='value(bindings.role)')"
    exact_line roles/secretmanager.secretAccessor "$result" && SECRET_ACCESS=true
  fi

  MISSING=()
  [[ -n "$ACTIVE_ACCOUNT" ]] || MISSING+=(active_gcloud_account)
  [[ "$ACTUAL_PROJECT_NUMBER" == "$PROJECT_NUMBER" ]] || MISSING+=(project_number_match)
  [[ "$DEPLOYER_EXISTS" == true ]] || MISSING+=(deployer_service_account)
  [[ "$SECRET_EXISTS" == true ]] || MISSING+=(operator_secret)
  [[ "$POOL_STATE" == ACTIVE ]] || MISSING+=(wif_pool_active)
  [[ "$PROVIDER_STATE" == ACTIVE ]] || MISSING+=(wif_provider_active)
  [[ "$PROVIDER_CONDITION" == "$EXPECTED_CONDITION" ]] || MISSING+=(provider_attribute_condition)
  [[ "$PROVIDER_MAPPING" == "$EXPECTED_MAPPING" ]] || MISSING+=(provider_attribute_mapping)
  [[ "$WIF_BINDING" == true ]] || MISSING+=(workload_identity_user_binding)
  [[ "$SECRET_ACCESS" == true ]] || MISSING+=(secret_accessor_binding)
}

emit() {
  local receipt="$1" state="$2"
  missing_json="$(printf '%s\n' "${MISSING[@]:-}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
  RECEIPT="$receipt" STATE="$state" MISSING_JSON="$missing_json" \
  WIF_BINDING_VALUE="$WIF_BINDING" SECRET_ACCESS_VALUE="$SECRET_ACCESS" \
  MUTATION_VALUE="${MUTATION_PERFORMED:-false}" python3 - <<'PY'
import json, os
as_bool=lambda name: os.environ.get(name,'false').lower() == 'true'
print(json.dumps({
  'receipt':os.environ['RECEIPT'],
  'state':os.environ['STATE'],
  'mode':os.environ['MODE'],
  'project':os.environ['PROJECT_ID'],
  'project_number_expected':os.environ['PROJECT_NUMBER'],
  'project_number_observed':os.environ.get('ACTUAL_PROJECT_NUMBER',''),
  'active_account':os.environ.get('ACTIVE_ACCOUNT',''),
  'repository':os.environ['GITHUB_REPOSITORY'],
  'provider':os.environ['PROVIDER_RESOURCE'],
  'provider_state':os.environ.get('PROVIDER_STATE',''),
  'provider_condition':os.environ.get('PROVIDER_CONDITION',''),
  'provider_condition_expected':os.environ['EXPECTED_CONDITION'],
  'deployer_service_account':os.environ['DEPLOYER_SA'],
  'operator_secret':os.environ['SECRET_ID'],
  'wif_binding':as_bool('WIF_BINDING_VALUE'),
  'secret_accessor_binding':as_bool('SECRET_ACCESS_VALUE'),
  'missing_controls':json.loads(os.environ['MISSING_JSON']),
  'mutation_performed':as_bool('MUTATION_VALUE')
}, sort_keys=True))
PY
}

export MODE PROJECT_ID PROJECT_NUMBER GITHUB_REPOSITORY PROVIDER_RESOURCE EXPECTED_CONDITION DEPLOYER_SA SECRET_ID
collect_state
export ACTIVE_ACCOUNT ACTUAL_PROJECT_NUMBER PROVIDER_STATE PROVIDER_CONDITION
MUTATION_PERFORMED=false

case "$MODE" in
  --plan)
    if ((${#MISSING[@]}==0)); then emit NEXUS-OPERATOR-WIF-PLAN READY_FOR_AUTH_CANARY; else emit NEXUS-OPERATOR-WIF-PLAN PLAN_REQUIRES_CHANGES; fi
    ;;
  --verify)
    if ((${#MISSING[@]})); then emit NEXUS-OPERATOR-WIF-VERIFICATION-FAILED NOT_VERIFIED; exit 1; fi
    emit NEXUS-OPERATOR-WIF-CLOUD-VERIFIED VERIFIED
    ;;
  --apply)
    if [[ "${NEXUS_WIF_APPLY_APPROVAL:-}" != "$APPLY_CONFIRMATION" ]]; then
      emit NEXUS-OPERATOR-WIF-APPLY-BLOCKED APPROVAL_REQUIRED
      exit 3
    fi
    if [[ -z "$ACTIVE_ACCOUNT" || "$ACTUAL_PROJECT_NUMBER" != "$PROJECT_NUMBER" ]]; then
      emit NEXUS-OPERATOR-WIF-APPLY-BLOCKED IDENTITY_OR_PROJECT_MISMATCH
      exit 4
    fi
    MUTATION_PERFORMED=true
    gcloud services enable iamcredentials.googleapis.com sts.googleapis.com secretmanager.googleapis.com --project "$PROJECT_ID"
    if [[ "$DEPLOYER_EXISTS" != true ]]; then
      gcloud iam service-accounts create "${DEPLOYER_SA%@*}" --project "$PROJECT_ID" --display-name='NEXUS operator GitHub deployer'
    fi
    if [[ "$POOL_STATE" == NOT_FOUND ]]; then
      gcloud iam workload-identity-pools create "$POOL_ID" --location global --project "$PROJECT_ID" --display-name='Federation Omega GitHub'
    fi
    if [[ "$PROVIDER_STATE" == NOT_FOUND ]]; then
      gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" --workload-identity-pool "$POOL_ID" --location global --project "$PROJECT_ID" --issuer-uri='https://token.actions.githubusercontent.com' --attribute-mapping='google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner,attribute.ref=assertion.ref' --attribute-condition="$EXPECTED_CONDITION"
    else
      gcloud iam workload-identity-pools providers update-oidc "$PROVIDER_ID" --workload-identity-pool "$POOL_ID" --location global --project "$PROJECT_ID" --issuer-uri='https://token.actions.githubusercontent.com' --attribute-mapping='google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner,attribute.ref=assertion.ref' --attribute-condition="$EXPECTED_CONDITION"
    fi
    gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" --project "$PROJECT_ID" --role roles/iam.workloadIdentityUser --member "$PRINCIPAL" >/dev/null
    gcloud secrets add-iam-policy-binding "$SECRET_ID" --project "$PROJECT_ID" --role roles/secretmanager.secretAccessor --member "serviceAccount:${DEPLOYER_SA}" >/dev/null
    collect_state
    export ACTIVE_ACCOUNT ACTUAL_PROJECT_NUMBER PROVIDER_STATE PROVIDER_CONDITION
    if ((${#MISSING[@]})); then emit NEXUS-OPERATOR-WIF-APPLY-INCOMPLETE APPLIED_BUT_VERIFICATION_FAILED; exit 6; fi
    emit NEXUS-OPERATOR-WIF-CLOUD-VERIFIED APPLIED_AND_VERIFIED
    ;;
  *) echo 'Usage: bootstrap_nexus_operator_wif.sh [--plan|--verify|--apply]' >&2; exit 2 ;;
esac
