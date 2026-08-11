#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ID="${PROJECT_ID:-sov-hybrid-suite}"
EXPECTED_PROJECT_NUMBER="${PROJECT_NUMBER:-257649435135}"
POOL_ID="${POOL_ID:-github-federation-omega}"
PROVIDER_ID="${PROVIDER_ID:-github}"
REPOSITORY="${GITHUB_REPOSITORY:-mosianekk-lang/Federation-Omega}"
BRANCH_REF="${GITHUB_REF_LOCK:-refs/heads/main}"
DEPLOYER_SA="${DEPLOYER_SA:-superior-logic-deployer@${PROJECT_ID}.iam.gserviceaccount.com}"
MODE="${1:---plan}"
APPLY_PHRASE="APPLY_FO_TRANSCRIPTION_WIF_RECOVERY"
CONDITION="assertion.repository=='${REPOSITORY}' && assertion.ref=='${BRANCH_REF}'"
MAPPING="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref,attribute.repository_owner=assertion.repository_owner"
POOL_RESOURCE="projects/${EXPECTED_PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"
PRINCIPAL="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository/${REPOSITORY}"

need(){ command -v "$1" >/dev/null 2>&1 || { echo "Missing command: $1" >&2; exit 90; }; }
need gcloud; need python3
read_json(){ "$@" --format=json 2>/dev/null || true; }

collect(){
  ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -n1 || true)"
  PROJECT_JSON="$(read_json gcloud projects describe "$PROJECT_ID")"
  OBSERVED_NUMBER="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1] or "{}"); print(d.get("projectNumber",""))' "$PROJECT_JSON")"
  DEPLOYER_EXISTS=false
  gcloud iam service-accounts describe "$DEPLOYER_SA" --project "$PROJECT_ID" >/dev/null 2>&1 && DEPLOYER_EXISTS=true

  POOL_JSON="$(gcloud iam workload-identity-pools describe "$POOL_ID" --project "$PROJECT_ID" --location=global --format=json 2>/dev/null || true)"
  if [[ -z "$POOL_JSON" ]]; then
    POOL_JSON="$(gcloud iam workload-identity-pools list --project "$PROJECT_ID" --location=global --show-deleted --filter="name:${POOL_ID}" --format=json 2>/dev/null || echo '[]')"
    POOL_JSON="$(python3 -c 'import json,sys; a=json.loads(sys.argv[1] or "[]"); print(json.dumps(a[0] if a else {}))' "$POOL_JSON")"
  fi
  readarray -t POOL_FIELDS < <(python3 - "$POOL_JSON" <<'PY'
import json,sys
x=json.loads(sys.argv[1] or '{}')
print(x.get('state','NOT_FOUND'))
print(str(x.get('disabled',False)).lower())
PY
)
  POOL_STATE="${POOL_FIELDS[0]:-NOT_FOUND}"; POOL_DISABLED="${POOL_FIELDS[1]:-false}"

  PROVIDER_JSON="$(gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" --project "$PROJECT_ID" --location=global --workload-identity-pool "$POOL_ID" --format=json 2>/dev/null || true)"
  if [[ -z "$PROVIDER_JSON" ]]; then
    PROVIDER_JSON="$(gcloud iam workload-identity-pools providers list --project "$PROJECT_ID" --location=global --workload-identity-pool "$POOL_ID" --show-deleted --filter="name:${PROVIDER_ID}" --format=json 2>/dev/null || echo '[]')"
    PROVIDER_JSON="$(python3 -c 'import json,sys; a=json.loads(sys.argv[1] or "[]"); print(json.dumps(a[0] if a else {}))' "$PROVIDER_JSON")"
  fi
  readarray -t PROVIDER_FIELDS < <(python3 - "$PROVIDER_JSON" <<'PY'
import json,sys
x=json.loads(sys.argv[1] or '{}')
print(x.get('state','NOT_FOUND'))
print(str(x.get('disabled',False)).lower())
print(x.get('attributeCondition',''))
m=x.get('attributeMapping',{})
print(','.join(f'{k}={m[k]}' for k in sorted(m)))
PY
)
  PROVIDER_STATE="${PROVIDER_FIELDS[0]:-NOT_FOUND}"; PROVIDER_DISABLED="${PROVIDER_FIELDS[1]:-false}"
  PROVIDER_CONDITION="${PROVIDER_FIELDS[2]:-}"; PROVIDER_MAPPING="${PROVIDER_FIELDS[3]:-}"

  WIF_BINDING=false
  if [[ "$DEPLOYER_EXISTS" == true ]]; then
    gcloud iam service-accounts get-iam-policy "$DEPLOYER_SA" --project "$PROJECT_ID" --format=json 2>/dev/null | \
      python3 - "$PRINCIPAL" <<'PY' >/tmp/fo_wif_binding.txt
import json,sys
p=sys.argv[1]; d=json.load(sys.stdin)
print('true' if any(b.get('role')=='roles/iam.workloadIdentityUser' and p in b.get('members',[]) for b in d.get('bindings',[])) else 'false')
PY
    WIF_BINDING="$(cat /tmp/fo_wif_binding.txt 2>/dev/null || echo false)"
  fi

  MISSING=()
  [[ -n "$ACTIVE_ACCOUNT" ]] || MISSING+=(active_gcloud_account)
  [[ "$OBSERVED_NUMBER" == "$EXPECTED_PROJECT_NUMBER" ]] || MISSING+=(project_number_match)
  [[ "$DEPLOYER_EXISTS" == true ]] || MISSING+=(deployer_service_account)
  [[ "$POOL_STATE" == ACTIVE && "$POOL_DISABLED" != true ]] || MISSING+=(wif_pool_active_enabled)
  [[ "$PROVIDER_STATE" == ACTIVE && "$PROVIDER_DISABLED" != true ]] || MISSING+=(wif_provider_active_enabled)
  [[ "$PROVIDER_CONDITION" == "$CONDITION" ]] || MISSING+=(provider_attribute_condition)
  EXPECTED_SORTED="$(python3 - "$MAPPING" <<'PY'
import sys
x={k:v for k,v in (i.split('=',1) for i in sys.argv[1].split(','))}
print(','.join(f'{k}={x[k]}' for k in sorted(x)))
PY
)"
  [[ "$PROVIDER_MAPPING" == "$EXPECTED_SORTED" ]] || MISSING+=(provider_attribute_mapping)
  [[ "$WIF_BINDING" == true ]] || MISSING+=(workload_identity_user_binding)
}

emit(){
  local state="$1" mutation="${2:-false}"
  MISSING_JSON="$(printf '%s\n' "${MISSING[@]:-}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
  python3 - <<PY
import json
print(json.dumps({
 'contract':'FO_TRANSCRIPTION_WIF_RECOVERY_V1',
 'mode':'$MODE','state':'$state','mutation_performed':$mutation,
 'project_id':'$PROJECT_ID','project_number_expected':'$EXPECTED_PROJECT_NUMBER','project_number_observed':'$OBSERVED_NUMBER',
 'active_account':'$ACTIVE_ACCOUNT','repository':'$REPOSITORY','branch_ref':'$BRANCH_REF',
 'deployer_service_account':'$DEPLOYER_SA',
 'pool':{'id':'$POOL_ID','state':'$POOL_STATE','disabled':'$POOL_DISABLED'},
 'provider':{'id':'$PROVIDER_ID','state':'$PROVIDER_STATE','disabled':'$PROVIDER_DISABLED','condition_matches':$([[ "$PROVIDER_CONDITION" == "$CONDITION" ]] && echo true || echo false),'mapping_matches':$([[ "$PROVIDER_MAPPING" == "$EXPECTED_SORTED" ]] && echo true || echo false)},
 'wif_binding':$WIF_BINDING,'missing_controls':json.loads('''$MISSING_JSON'''),
 'secret_values_recorded':False
},sort_keys=True))
PY
}

collect
case "$MODE" in
  --plan) [[ ${#MISSING[@]} -eq 0 ]] && emit READY_FOR_CANARY false || emit PLAN_REQUIRES_CHANGES false ;;
  --verify) [[ ${#MISSING[@]} -eq 0 ]] || { emit NOT_VERIFIED false; exit 1; }; emit VERIFIED false ;;
  --apply)
    [[ "${FO_WIF_RECOVERY_APPROVAL:-}" == "$APPLY_PHRASE" ]] || { emit APPROVAL_REQUIRED false; exit 3; }
    [[ -n "$ACTIVE_ACCOUNT" && "$OBSERVED_NUMBER" == "$EXPECTED_PROJECT_NUMBER" ]] || { emit IDENTITY_OR_PROJECT_MISMATCH false; exit 4; }
    gcloud services enable iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com serviceusage.googleapis.com --project "$PROJECT_ID" --quiet
    if [[ "$DEPLOYER_EXISTS" != true ]]; then
      gcloud iam service-accounts create "${DEPLOYER_SA%@*}" --project "$PROJECT_ID" --display-name='Federation Omega GitHub deployer' --quiet
    fi
    if [[ "$POOL_STATE" == DELETED ]]; then
      gcloud iam workload-identity-pools undelete "$POOL_ID" --location=global --project "$PROJECT_ID" --quiet
    elif [[ "$POOL_STATE" == NOT_FOUND ]]; then
      gcloud iam workload-identity-pools create "$POOL_ID" --location=global --project "$PROJECT_ID" --display-name='Federation Omega GitHub' --quiet
    fi
    if [[ "$POOL_DISABLED" == true ]]; then
      gcloud iam workload-identity-pools update "$POOL_ID" --location=global --project "$PROJECT_ID" --no-disabled --quiet
    fi
    if [[ "$PROVIDER_STATE" == DELETED ]]; then
      gcloud iam workload-identity-pools providers undelete "$PROVIDER_ID" --workload-identity-pool "$POOL_ID" --location=global --project "$PROJECT_ID" --quiet
    elif [[ "$PROVIDER_STATE" == NOT_FOUND ]]; then
      gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" --workload-identity-pool "$POOL_ID" --location=global --project "$PROJECT_ID" --issuer-uri='https://token.actions.githubusercontent.com' --attribute-mapping="$MAPPING" --attribute-condition="$CONDITION" --quiet
    fi
    gcloud iam workload-identity-pools providers update-oidc "$PROVIDER_ID" --workload-identity-pool "$POOL_ID" --location=global --project "$PROJECT_ID" --issuer-uri='https://token.actions.githubusercontent.com' --attribute-mapping="$MAPPING" --attribute-condition="$CONDITION" --no-disabled --quiet
    gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" --project "$PROJECT_ID" --role=roles/iam.workloadIdentityUser --member="$PRINCIPAL" --quiet >/dev/null
    sleep 10
    collect
    [[ ${#MISSING[@]} -eq 0 ]] || { emit APPLIED_BUT_NOT_VERIFIED true; exit 6; }
    emit APPLIED_AND_VERIFIED true
    ;;
  *) echo 'Usage: recover_fo_transcription_wif.sh [--plan|--verify|--apply]' >&2; exit 2 ;;
esac
