#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sov-hybrid-suite}"
PROJECT_NUMBER="${PROJECT_NUMBER:-257649435135}"
POOL_ID="${POOL_ID:-github-federation-omega}"
PROVIDER_ID="${PROVIDER_ID:-github}"
DEPLOYER_SA="${DEPLOYER_SA:-superior-logic-deployer@${PROJECT_ID}.iam.gserviceaccount.com}"
REPOSITORY_ID="1292795464"
OWNER_ID="261966700"
REPOSITORY_SLUG="mosianekk-lang/Federation-Omega"
MAIN_REF="refs/heads/main"
EXPECTED_OIDC_WORKFLOW_COUNT=18
EXPECTED_OIDC_WORKFLOW_SET_SHA256="65e4cc0a148c4a0d7f0fa646692f369becc7d47db7aa68591371fa593de1c07c"
EXPECTED_TRUST_CONTRACT_SHA256="98a3ca770f05b91b425b335f5b1ea7210b139a916fc3a90e30bb3881a54db391"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
AIRLOCK_POLICY="${AIRLOCK_POLICY:-${SCRIPT_DIR}/../governance/github_airlock_policy.json}"
POOL_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"
EXACT_PRINCIPAL="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository_id/${REPOSITORY_ID}"
BROAD_PRINCIPAL="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository/mosianekk-lang/Federation-Omega"
EXPECTED_MAPPING="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id,attribute.ref=assertion.ref,attribute.event_name=assertion.event_name,attribute.workflow_ref=assertion.workflow_ref"
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

The trust condition is fail-closed to the current, source-reviewed Airlock OIDC
workflow + allowed-event contract on refs/heads/main. Both the exact workflow set
and the full workflow/event trust contract are pinned, so later Airlock changes
cannot silently widen provider trust without a new reviewed hardener.

This script does not enable APIs, create service accounts, grant project roles,
modify Cloud Run/Artifact Registry, access secrets, run model inference, or
change application traffic.
USAGE
    exit 0
    ;;
  *) echo "Unknown mode: ${1}" >&2; exit 2 ;;
esac

for bin in gcloud python3 sha256sum; do
  command -v "$bin" >/dev/null 2>&1 || { echo "Missing required command: $bin" >&2; exit 1; }
done
[[ -f "$AIRLOCK_POLICY" ]] || { echo "Airlock policy is not readable: $AIRLOCK_POLICY" >&2; exit 9; }

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

load_authorized_trust_contract() {
  local contract_json
  contract_json="$(python3 - "$AIRLOCK_POLICY" "$REPOSITORY_SLUG" "$MAIN_REF" "$REPOSITORY_ID" "$OWNER_ID" <<'PY'
import hashlib, json, re, sys
from pathlib import Path

policy=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
slug, main_ref, repository_id, owner_id = sys.argv[2:6]
paths=policy.get('oidc_workflow_allowlist') or []
allowed=policy.get('allowed_events') or {}
if not isinstance(paths,list) or not paths:
    raise SystemExit('OIDC_WORKFLOW_ALLOWLIST_EMPTY')
if len(paths) != len(set(paths)):
    raise SystemExit('OIDC_WORKFLOW_ALLOWLIST_DUPLICATE')
if not isinstance(allowed,dict):
    raise SystemExit('ALLOWED_EVENTS_INVALID')

refs=[]
records=[]
pairs=[]
for path in sorted(paths):
    if not isinstance(path,str) or not re.fullmatch(r'\.github/workflows/[A-Za-z0-9._/-]+\.(?:yml|yaml)', path):
        raise SystemExit(f'OIDC_WORKFLOW_PATH_INVALID:{path!r}')
    events=allowed.get(path)
    if not isinstance(events,list) or not events:
        raise SystemExit(f'OIDC_WORKFLOW_ALLOWED_EVENTS_MISSING:{path}')
    if len(events) != len(set(events)):
        raise SystemExit(f'OIDC_WORKFLOW_ALLOWED_EVENTS_DUPLICATE:{path}')
    for event in events:
        if not isinstance(event,str) or not re.fullmatch(r'[A-Za-z0-9_]+', event):
            raise SystemExit(f'OIDC_WORKFLOW_EVENT_INVALID:{path}:{event!r}')
    workflow_ref=f'{slug}/{path}@{main_ref}'
    sorted_events=sorted(events)
    refs.append(workflow_ref)
    records.append(json.dumps(
        {'workflow_ref':workflow_ref,'events':sorted_events},
        sort_keys=True,separators=(',',':')
    ))
    event_expr=' || '.join(f"assertion.event_name=='{event}'" for event in sorted_events)
    pairs.append(f"(assertion.workflow_ref=='{workflow_ref}' && ({event_expr}))")

refs_blob='\n'.join(sorted(refs))+'\n'
contract_blob='\n'.join(records)+'\n'
condition=(
    f"assertion.repository_id=='{repository_id}' && "
    f"assertion.repository_owner_id=='{owner_id}' && "
    f"assertion.ref=='{main_ref}' && ("
    + ' || '.join(pairs)
    + ')'
)
print(json.dumps({
    'count':len(refs),
    'workflow_set_sha256':hashlib.sha256(refs_blob.encode()).hexdigest(),
    'trust_contract_sha256':hashlib.sha256(contract_blob.encode()).hexdigest(),
    'condition':condition,
},sort_keys=True,separators=(',',':')))
PY
  )"

  readarray -t CONTRACT_FIELDS < <(python3 - "$contract_json" <<'PY'
import json,sys
p=json.loads(sys.argv[1])
print(p['count'])
print(p['workflow_set_sha256'])
print(p['trust_contract_sha256'])
print(p['condition'])
PY
  )
  AUTHORIZED_WORKFLOW_COUNT="${CONTRACT_FIELDS[0]:-0}"
  AUTHORIZED_WORKFLOW_SET_SHA="${CONTRACT_FIELDS[1]:-}"
  TRUST_CONTRACT_SHA="${CONTRACT_FIELDS[2]:-}"
  EXPECTED_CONDITION="${CONTRACT_FIELDS[3]:-}"

  if [[ "$AUTHORIZED_WORKFLOW_COUNT" -ne "$EXPECTED_OIDC_WORKFLOW_COUNT" \
     || "$AUTHORIZED_WORKFLOW_SET_SHA" != "$EXPECTED_OIDC_WORKFLOW_SET_SHA256" \
     || "$TRUST_CONTRACT_SHA" != "$EXPECTED_TRUST_CONTRACT_SHA256" ]]; then
    echo "Airlock OIDC trust contract drifted; refusing silent WIF trust expansion/contraction." >&2
    exit 10
  fi
  if ((${#EXPECTED_CONDITION} > 4096)); then
    echo "Generated WIF condition exceeds Google Cloud 4096-character limit." >&2
    exit 11
  fi
}

load_authorized_trust_contract

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
  'schema':'SOVARA_WIF_HARDENING_V3',
  'mode':'${MODE}',
  'state':'${state}',
  'project_id':'${PROJECT_ID}',
  'project_number_expected':'${PROJECT_NUMBER}',
  'project_number_observed':'${ACTUAL_PROJECT_NUMBER}',
  'active_account':'${ACTIVE_ACCOUNT}',
  'provider_state':'${PROVIDER_STATE}',
  'condition_match':'${CONDITION_MATCH}' == 'true',
  'mapping_match':'${MAPPING_MATCH}' == 'true',
  'exact_repository_id_binding_present':'${EXACT_BINDING}' == 'true',
  'broad_repository_name_binding_present':'${BROAD_BINDING}' == 'true',
  'authorized_workflow_count':${AUTHORIZED_WORKFLOW_COUNT},
  'authorized_workflow_set_sha256':'${AUTHORIZED_WORKFLOW_SET_SHA}',
  'trust_contract_sha256':'${TRUST_CONTRACT_SHA}',
  'condition_length':${#EXPECTED_CONDITION},
  'workflow_claim':'workflow_ref',
  'event_claim':'event_name',
  'event_surface_bound_per_workflow':True,
  'expected_condition_sha256':'${EXPECTED_CONDITION_SHA}',
  'observed_condition_sha256':'${OBSERVED_CONDITION_SHA}',
  'expected_mapping_sha256':'${EXPECTED_MAPPING_SHA}',
  'observed_mapping_sha256':'${OBSERVED_MAPPING_SHA}',
  'required_mutations':${required_json},
  'mutation_performed':'${mutation}' == 'true',
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

# --apply is idempotent and proof-truthful. If the exact hardened state is already
# present, there is no mutation to authorize or claim.
if ((${#REQUIRED[@]} == 0)); then
  emit_receipt "ALREADY_HARDENED" false
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
