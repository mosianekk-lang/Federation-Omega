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
EXPECTED_OIDC_WORKFLOW_COUNT=19
EXPECTED_OIDC_WORKFLOW_SET_SHA256="8fa0450fdf8b69913b11e42d37fb10ece6da2d3d9ffac731ac8eb063d7ccd2ec"
EXPECTED_TRUST_CONTRACT_SHA256="38fa68df85d793f5491f480ddcf04e46e6e9ffc50dcf1abd67e934714ff98b1e"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
AIRLOCK_POLICY="${AIRLOCK_POLICY:-${SCRIPT_DIR}/../governance/github_airlock_policy.json}"
POOL_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"
EXACT_PRINCIPAL="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository_id/${REPOSITORY_ID}"
BROAD_PRINCIPAL="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository/mosianekk-lang/Federation-Omega"
EXPECTED_MAPPING="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id,attribute.ref=assertion.ref,attribute.event_name=assertion.event_name,attribute.workflow_ref=assertion.workflow_ref"
APPLY_CONFIRMATION="HARDEN_SOVARA_CANONICAL_WIF_V1"
CONVERGENCE_MAX_ATTEMPTS="${SOVARA_WIF_CONVERGENCE_MAX_ATTEMPTS:-6}"
CONVERGENCE_INITIAL_DELAY_SECONDS="${SOVARA_WIF_CONVERGENCE_INITIAL_DELAY_SECONDS:-2}"
CONVERGENCE_MAX_DELAY_SECONDS="${SOVARA_WIF_CONVERGENCE_MAX_DELAY_SECONDS:-10}"

MODE="plan"
case "${1:-}" in
  ""|--plan) MODE="plan" ;;
  --verify) MODE="verify" ;;
  --apply) MODE="apply" ;;
  -h|--help)
    cat <<'USAGE'
Usage: ops/harden_sovara_provider_wif_v1.sh [--plan|--verify|--apply]

--plan   Read-only. Report the exact canonical SOVARA WIF hardening delta.
--verify Read-only. Succeeds only when the canonical provider contract and exact
         repository-ID binding are present and any legacy repository-name binding
         is ineffective because attribute.repository is not mapped by the provider.
--apply  Apply only that hardening delta. Requires:
         SOVARA_WIF_HARDENING_APPROVAL=HARDEN_SOVARA_CANONICAL_WIF_V1

The trust condition is fail-closed to the current, source-reviewed Airlock OIDC
workflow + allowed-event contract on refs/heads/main. Both the exact workflow set
and the full workflow/event trust contract are pinned, so later Airlock changes
cannot silently widen provider trust without a new reviewed hardener.

Google WIF principalSet custom-attribute authorization depends on provider-mapped
custom attributes. The canonical mapping intentionally does not export
attribute.repository. Therefore a legacy policy member keyed by
attribute.repository is reported as PRESENT_BUT_INERT, not silently hidden, and
cannot satisfy verification if the provider maps attribute.repository again.

Provider update acknowledgement is not semantic readback. Apply mode therefore
waits for bounded provider-native describe convergence before declaring success;
transient stale reads do not trigger premature rollback, while timeout still
fails closed so the surrounding transaction can restore the captured prestate.

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
if [[ ",$EXPECTED_MAPPING," == *",attribute.repository="* ]]; then
  echo "Canonical mapping must not export attribute.repository." >&2
  exit 12
fi
if [[ ! "$CONVERGENCE_MAX_ATTEMPTS" =~ ^[0-9]+$ ]] || ((CONVERGENCE_MAX_ATTEMPTS < 1)); then
  echo "SOVARA_WIF_CONVERGENCE_MAX_ATTEMPTS must be a positive integer." >&2
  exit 13
fi
for delay_value in "$CONVERGENCE_INITIAL_DELAY_SECONDS" "$CONVERGENCE_MAX_DELAY_SECONDS"; do
  if [[ ! "$delay_value" =~ ^[0-9]+$ ]]; then
    echo "WIF convergence delays must be non-negative integers." >&2
    exit 14
  fi
done
if ((CONVERGENCE_INITIAL_DELAY_SECONDS > CONVERGENCE_MAX_DELAY_SECONDS)); then
  echo "Initial WIF convergence delay cannot exceed the maximum delay." >&2
  exit 15
fi

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
CONVERGENCE_ATTEMPTS_USED=1
CONVERGENCE_REACHED=false

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
print('true' if 'attribute.repository' in m else 'false')
PY
)
  PROVIDER_STATE="${FIELDS[0]:-NOT_FOUND}"
  OBSERVED_CONDITION="${FIELDS[1]:-}"
  OBSERVED_MAPPING="${FIELDS[2]:-}"
  BROAD_REPOSITORY_ATTRIBUTE_MAPPED="${FIELDS[3]:-true}"
  SORTED_EXPECTED_MAPPING="$(sorted_mapping "$EXPECTED_MAPPING")"

  CONDITION_MATCH=false
  MAPPING_MATCH=false
  EXACT_BINDING=false
  BROAD_BINDING=false
  BROAD_BINDING_EFFECTIVE=false
  LEGACY_BROAD_BINDING_INERT=false
  [[ "$OBSERVED_CONDITION" == "$EXPECTED_CONDITION" ]] && CONDITION_MATCH=true || true
  [[ "$OBSERVED_MAPPING" == "$SORTED_EXPECTED_MAPPING" ]] && MAPPING_MATCH=true || true
  binding_present "$EXACT_PRINCIPAL" && EXACT_BINDING=true || true
  binding_present "$BROAD_PRINCIPAL" && BROAD_BINDING=true || true

  if [[ "$BROAD_BINDING" == true && "$BROAD_REPOSITORY_ATTRIBUTE_MAPPED" == true ]]; then
    BROAD_BINDING_EFFECTIVE=true
  elif [[ "$BROAD_BINDING" == true && "$BROAD_REPOSITORY_ATTRIBUTE_MAPPED" == false ]]; then
    LEGACY_BROAD_BINDING_INERT=true
  fi

  REQUIRED=()
  [[ "$CONDITION_MATCH" == true ]] || REQUIRED+=("UPDATE_PROVIDER_ATTRIBUTE_CONDITION")
  [[ "$MAPPING_MATCH" == true ]] || REQUIRED+=("UPDATE_PROVIDER_ATTRIBUTE_MAPPING")
  [[ "$EXACT_BINDING" == true ]] || REQUIRED+=("ADD_EXACT_REPOSITORY_ID_WIF_BINDING")
  [[ "$BROAD_BINDING_EFFECTIVE" == false ]] || REQUIRED+=("RENDER_BROAD_REPOSITORY_NAME_BINDING_INERT")
}

wait_for_provider_convergence() {
  local attempt=1
  local delay="$CONVERGENCE_INITIAL_DELAY_SECONDS"
  CONVERGENCE_REACHED=false
  while ((attempt <= CONVERGENCE_MAX_ATTEMPTS)); do
    collect_state
    CONVERGENCE_ATTEMPTS_USED="$attempt"
    if ((${#REQUIRED[@]} == 0)); then
      CONVERGENCE_REACHED=true
      return 0
    fi
    if ((attempt == CONVERGENCE_MAX_ATTEMPTS)); then
      break
    fi
    sleep "$delay"
    if ((delay < CONVERGENCE_MAX_DELAY_SECONDS)); then
      delay=$((delay * 2))
      if ((delay > CONVERGENCE_MAX_DELAY_SECONDS)); then
        delay="$CONVERGENCE_MAX_DELAY_SECONDS"
      fi
    fi
    attempt=$((attempt + 1))
  done
  return 1
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
  'broad_repository_attribute_mapped':'${BROAD_REPOSITORY_ATTRIBUTE_MAPPED}' == 'true',
  'broad_repository_name_binding_effective':'${BROAD_BINDING_EFFECTIVE}' == 'true',
  'legacy_broad_repository_name_binding_inert':'${LEGACY_BROAD_BINDING_INERT}' == 'true',
  'physical_legacy_binding_removal_required':False,
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
  'convergence_attempts_used':${CONVERGENCE_ATTEMPTS_USED},
  'convergence_reached':'${CONVERGENCE_REACHED}' == 'true',
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
  CONVERGENCE_REACHED=true
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

# Establish the exact repository-ID binding before tightening the provider. Current
# production prestate already contains this binding. If it is ever absent, the
# operation still fails closed rather than weakening the target contract.
if [[ "$EXACT_BINDING" != true ]]; then
  gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" \
    --project "$PROJECT_ID" \
    --role roles/iam.workloadIdentityUser \
    --member "$EXACT_PRINCIPAL" >/dev/null
fi

# Google WIF principalSet custom attributes exist only when provider attribute
# mapping emits them. The canonical mapping intentionally omits attribute.repository.
# Thus the old attribute.repository policy member can remain physically present
# while being non-authoritative; verification fails closed if that attribute ever
# becomes mapped again. This avoids replaying the known-denied service-account
# setIamPolicy call without widening effective authority.
if [[ "$CONDITION_MATCH" != true || "$MAPPING_MATCH" != true || "$BROAD_BINDING_EFFECTIVE" == true ]]; then
  gcloud iam workload-identity-pools providers update-oidc "$PROVIDER_ID" \
    --project "$PROJECT_ID" \
    --location global \
    --workload-identity-pool "$POOL_ID" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="$EXPECTED_MAPPING" \
    --attribute-condition="$EXPECTED_CONDITION"
fi

# update-oidc can acknowledge the provider operation before subsequent describe
# calls converge on the new condition/mapping. Treat command acknowledgement as an
# intermediate state only; bounded semantic provider readback is the commit court.
if ! wait_for_provider_convergence; then
  emit_receipt "APPLIED_BUT_CONVERGENCE_TIMEOUT" true
  exit 8
fi
emit_receipt "APPLIED_AND_VERIFIED" true
