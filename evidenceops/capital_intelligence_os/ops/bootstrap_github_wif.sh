#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sov-hybrid-suite}"
PROJECT_NUMBER="${PROJECT_NUMBER:-257649435135}"
REGION="${REGION:-africa-south1}"
SERVICE="${SERVICE:-architron9}"
AR_REPO="${AR_REPO:-federation-omega}"
POOL_ID="${POOL_ID:-github-federation-omega}"
PROVIDER_ID="${PROVIDER_ID:-github}"
GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-mosianekk-lang/Federation-Omega}"
GITHUB_OWNER="${GITHUB_OWNER:-mosianekk-lang}"
DEPLOYER_SA="${DEPLOYER_SA:-superior-logic-deployer@${PROJECT_ID}.iam.gserviceaccount.com}"
RUNTIME_SA="${RUNTIME_SA:-superior-logic-runtime@${PROJECT_ID}.iam.gserviceaccount.com}"
PROVIDER_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"
POOL_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"
PRINCIPAL="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository/${GITHUB_REPOSITORY}"
EXPECTED_CONDITION="assertion.repository=='${GITHUB_REPOSITORY}' && assertion.ref=='refs/heads/main'"
EXPECTED_MAPPING="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner,attribute.ref=assertion.ref"
APPLY_CONFIRMATION="APPLY_FEDOMEGA_WIF_LEAST_PRIVILEGE"

MODE="plan"
case "${1:-}" in
  ""|--plan) MODE="plan" ;;
  --apply) MODE="apply" ;;
  --verify) MODE="verify" ;;
  -h|--help)
    cat <<'USAGE'
Usage: ops/bootstrap_github_wif.sh [--plan|--apply|--verify]

--plan   Read-only inspection. This is the default and performs no cloud mutation.
--apply  Apply the exact repository-scoped WIF and least-privilege bindings.
         Requires FEDOMEGA_WIF_APPLY_APPROVAL=APPLY_FEDOMEGA_WIF_LEAST_PRIVILEGE.
--verify Read-only verification. Exits non-zero until every required state is proved.
USAGE
    exit 0
    ;;
  *) echo "Unknown mode: ${1}" >&2; exit 2 ;;
esac

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}
require gcloud
require python3

read_value() {
  "$@" 2>/dev/null || true
}

has_exact_line() {
  local expected="$1"
  grep -Fxq "$expected" <<<"${2:-}"
}

project_role_present() {
  local role="$1"
  local result
  result="$(read_value gcloud projects get-iam-policy "$PROJECT_ID" \
    --flatten='bindings[].members' \
    --filter="bindings.role:${role} AND bindings.members:serviceAccount:${DEPLOYER_SA}" \
    --format='value(bindings.role)')"
  has_exact_line "$role" "$result"
}

service_role_present() {
  local role="$1"
  local result
  result="$(read_value gcloud run services get-iam-policy "$SERVICE" \
    --project "$PROJECT_ID" --region "$REGION" \
    --flatten='bindings[].members' \
    --filter="bindings.role:${role} AND bindings.members:serviceAccount:${DEPLOYER_SA}" \
    --format='value(bindings.role)')"
  has_exact_line "$role" "$result"
}

repo_role_present() {
  local role="$1"
  local result
  result="$(read_value gcloud artifacts repositories get-iam-policy "$AR_REPO" \
    --project "$PROJECT_ID" --location "$REGION" \
    --flatten='bindings[].members' \
    --filter="bindings.role:${role} AND bindings.members:serviceAccount:${DEPLOYER_SA}" \
    --format='value(bindings.role)')"
  has_exact_line "$role" "$result"
}

runtime_sa_role_present() {
  local role="$1"
  local result
  result="$(read_value gcloud iam service-accounts get-iam-policy "$RUNTIME_SA" \
    --project "$PROJECT_ID" \
    --flatten='bindings[].members' \
    --filter="bindings.role:${role} AND bindings.members:serviceAccount:${DEPLOYER_SA}" \
    --format='value(bindings.role)')"
  has_exact_line "$role" "$result"
}

wif_binding_present() {
  local result
  result="$(read_value gcloud iam service-accounts get-iam-policy "$DEPLOYER_SA" \
    --project "$PROJECT_ID" \
    --flatten='bindings[].members' \
    --filter="bindings.role:roles/iam.workloadIdentityUser AND bindings.members:${PRINCIPAL}" \
    --format='value(bindings.role)')"
  has_exact_line "roles/iam.workloadIdentityUser" "$result"
}

api_enabled() {
  local api="$1"
  local result
  result="$(read_value gcloud services list --enabled --project "$PROJECT_ID" \
    --filter="config.name=${api}" --format='value(config.name)')"
  has_exact_line "$api" "$result"
}

collect_state() {
  ACTIVE_ACCOUNT="$(read_value gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
  CONFIG_PROJECT="$(read_value gcloud config get-value project | head -n1)"
  ACTUAL_PROJECT_NUMBER="$(read_value gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' | head -n1)"
  DEPLOYER_EXISTS="false"
  RUNTIME_EXISTS="false"
  SERVICE_EXISTS="false"
  REPO_EXISTS="false"
  POOL_STATE="NOT_FOUND"
  PROVIDER_STATE="NOT_FOUND"
  PROVIDER_CONDITION=""
  PROVIDER_MAPPING=""

  if gcloud iam service-accounts describe "$DEPLOYER_SA" --project "$PROJECT_ID" >/dev/null 2>&1; then DEPLOYER_EXISTS="true"; fi
  if gcloud iam service-accounts describe "$RUNTIME_SA" --project "$PROJECT_ID" >/dev/null 2>&1; then RUNTIME_EXISTS="true"; fi
  if gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" >/dev/null 2>&1; then SERVICE_EXISTS="true"; fi
  if gcloud artifacts repositories describe "$AR_REPO" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1; then REPO_EXISTS="true"; fi

  POOL_STATE="$(read_value gcloud iam workload-identity-pools describe "$POOL_ID" \
    --project "$PROJECT_ID" --location global --format='value(state)' | head -n1)"
  [[ -n "$POOL_STATE" ]] || POOL_STATE="NOT_FOUND"

  local provider_json
  provider_json="$(read_value gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
    --project "$PROJECT_ID" --location global --workload-identity-pool "$POOL_ID" --format=json)"
  if [[ -n "$provider_json" ]]; then
    readarray -t provider_fields < <(python3 - "$provider_json" <<'PY'
import json, sys
obj = json.loads(sys.argv[1])
print(obj.get("state", "NOT_FOUND"))
print(obj.get("attributeCondition", ""))
mapping = obj.get("attributeMapping", {})
print(",".join(f"{key}={mapping[key]}" for key in sorted(mapping)))
PY
)
    PROVIDER_STATE="${provider_fields[0]:-NOT_FOUND}"
    PROVIDER_CONDITION="${provider_fields[1]:-}"
    PROVIDER_MAPPING="${provider_fields[2]:-}"
  fi

  WIF_BINDING="false"
  PROJECT_SERVICE_USAGE="false"
  SERVICE_RUN_DEVELOPER="false"
  SERVICE_RUN_INVOKER="false"
  REPO_WRITER="false"
  RUNTIME_SA_USER="false"
  if [[ "$DEPLOYER_EXISTS" == "true" ]]; then
    if wif_binding_present; then WIF_BINDING="true"; fi
    if project_role_present "roles/serviceusage.serviceUsageConsumer"; then PROJECT_SERVICE_USAGE="true"; fi
  fi
  if [[ "$DEPLOYER_EXISTS" == "true" && "$SERVICE_EXISTS" == "true" ]]; then
    if service_role_present "roles/run.developer"; then SERVICE_RUN_DEVELOPER="true"; fi
    if service_role_present "roles/run.invoker"; then SERVICE_RUN_INVOKER="true"; fi
  fi
  if [[ "$DEPLOYER_EXISTS" == "true" && "$REPO_EXISTS" == "true" ]]; then
    if repo_role_present "roles/artifactregistry.writer"; then REPO_WRITER="true"; fi
  fi
  if [[ "$DEPLOYER_EXISTS" == "true" && "$RUNTIME_EXISTS" == "true" ]]; then
    if runtime_sa_role_present "roles/iam.serviceAccountUser"; then RUNTIME_SA_USER="true"; fi
  fi

  REQUIRED_APIS=(
    iamcredentials.googleapis.com
    sts.googleapis.com
    run.googleapis.com
    artifactregistry.googleapis.com
  )
  ENABLED_APIS=()
  MISSING_APIS=()
  local api
  for api in "${REQUIRED_APIS[@]}"; do
    if api_enabled "$api"; then ENABLED_APIS+=("$api"); else MISSING_APIS+=("$api"); fi
  done

  MISSING=()
  [[ -n "$ACTIVE_ACCOUNT" ]] || MISSING+=("active_gcloud_account")
  [[ "$ACTUAL_PROJECT_NUMBER" == "$PROJECT_NUMBER" ]] || MISSING+=("project_number_match")
  [[ "$DEPLOYER_EXISTS" == "true" ]] || MISSING+=("deployer_service_account")
  [[ "$RUNTIME_EXISTS" == "true" ]] || MISSING+=("runtime_service_account")
  [[ "$SERVICE_EXISTS" == "true" ]] || MISSING+=("existing_cloud_run_service")
  [[ "$REPO_EXISTS" == "true" ]] || MISSING+=("existing_artifact_registry_repository")
  [[ "$POOL_STATE" == "ACTIVE" ]] || MISSING+=("wif_pool_active")
  [[ "$PROVIDER_STATE" == "ACTIVE" ]] || MISSING+=("wif_provider_active")
  [[ "$PROVIDER_CONDITION" == "$EXPECTED_CONDITION" ]] || MISSING+=("provider_attribute_condition")
  local sorted_expected_mapping
  sorted_expected_mapping="$(python3 - "$EXPECTED_MAPPING" <<'PY'
import sys
parts = sorted(item.strip() for item in sys.argv[1].split(",") if item.strip())
print(",".join(parts))
PY
)"
  [[ "$PROVIDER_MAPPING" == "$sorted_expected_mapping" ]] || MISSING+=("provider_attribute_mapping")
  [[ "$WIF_BINDING" == "true" ]] || MISSING+=("workload_identity_user_binding")
  [[ "$PROJECT_SERVICE_USAGE" == "true" ]] || MISSING+=("service_usage_consumer_role")
  [[ "$SERVICE_RUN_DEVELOPER" == "true" ]] || MISSING+=("cloud_run_developer_role")
  [[ "$SERVICE_RUN_INVOKER" == "true" ]] || MISSING+=("cloud_run_invoker_role")
  [[ "$REPO_WRITER" == "true" ]] || MISSING+=("artifact_registry_writer_role")
  [[ "$RUNTIME_SA_USER" == "true" ]] || MISSING+=("runtime_service_account_user_role")
  if ((${#MISSING_APIS[@]})); then MISSING+=("required_apis"); fi
}

emit_state() {
  local receipt="$1"
  local state="$2"
  MISSING_JSON="$(printf '%s\n' "${MISSING[@]:-}" | python3 -c 'import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))')"
  MISSING_APIS_JSON="$(printf '%s\n' "${MISSING_APIS[@]:-}" | python3 -c 'import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))')"
  python3 - <<PY
import json
print(json.dumps({
  "receipt": "${receipt}",
  "mode": "${MODE}",
  "state": "${state}",
  "project": "${PROJECT_ID}",
  "project_number_expected": "${PROJECT_NUMBER}",
  "project_number_observed": "${ACTUAL_PROJECT_NUMBER}",
  "active_account": "${ACTIVE_ACCOUNT}",
  "configured_project": "${CONFIG_PROJECT}",
  "region": "${REGION}",
  "service": "${SERVICE}",
  "artifact_repository": "${AR_REPO}",
  "deployer_service_account": "${DEPLOYER_SA}",
  "runtime_service_account": "${RUNTIME_SA}",
  "workload_identity_provider": "${PROVIDER_RESOURCE}",
  "pool_state": "${POOL_STATE}",
  "provider_state": "${PROVIDER_STATE}",
  "provider_condition": "${PROVIDER_CONDITION}",
  "provider_condition_expected": "${EXPECTED_CONDITION}",
  "deployer_exists": "${DEPLOYER_EXISTS}" == "true",
  "runtime_service_account_exists": "${RUNTIME_EXISTS}" == "true",
  "service_exists": "${SERVICE_EXISTS}" == "true",
  "artifact_repository_exists": "${REPO_EXISTS}" == "true",
  "wif_binding": "${WIF_BINDING}" == "true",
  "service_usage_consumer": "${PROJECT_SERVICE_USAGE}" == "true",
  "cloud_run_developer": "${SERVICE_RUN_DEVELOPER}" == "true",
  "cloud_run_invoker": "${SERVICE_RUN_INVOKER}" == "true",
  "artifact_registry_writer": "${REPO_WRITER}" == "true",
  "runtime_service_account_user": "${RUNTIME_SA_USER}" == "true",
  "missing_apis": ${MISSING_APIS_JSON},
  "missing_controls": ${MISSING_JSON},
  "mutation_performed": "${MUTATION_PERFORMED:-false}" == "true",
  "rollback": {
    "remove_wif_binding": "gcloud iam service-accounts remove-iam-policy-binding ${DEPLOYER_SA} --project ${PROJECT_ID} --role roles/iam.workloadIdentityUser --member '${PRINCIPAL}'",
    "disable_provider": "gcloud iam workload-identity-pools providers update-oidc ${PROVIDER_ID} --project ${PROJECT_ID} --location global --workload-identity-pool ${POOL_ID} --disabled"
  }
}, sort_keys=True))
PY
}

collect_state
MUTATION_PERFORMED=false

if [[ "$MODE" == "plan" ]]; then
  if ((${#MISSING[@]} == 0)); then
    emit_state "FEDOMEGA-WIF-PLAN" "READY_FOR_VERIFICATION"
  else
    emit_state "FEDOMEGA-WIF-PLAN" "PLAN_REQUIRES_CHANGES"
  fi
  exit 0
fi

if [[ "$MODE" == "verify" ]]; then
  if ((${#MISSING[@]} != 0)); then
    emit_state "FEDOMEGA-WIF-VERIFICATION-FAILED" "NOT_VERIFIED"
    exit 1
  fi
  emit_state "FEDOMEGA-WIF-CLOUD-VERIFIED" "VERIFIED"
  exit 0
fi

if [[ "${FEDOMEGA_WIF_APPLY_APPROVAL:-}" != "$APPLY_CONFIRMATION" ]]; then
  echo "Refusing WIF mutation without FEDOMEGA_WIF_APPLY_APPROVAL=${APPLY_CONFIRMATION}" >&2
  emit_state "FEDOMEGA-WIF-APPLY-BLOCKED" "APPROVAL_REQUIRED"
  exit 3
fi

if [[ -z "$ACTIVE_ACCOUNT" || "$ACTUAL_PROJECT_NUMBER" != "$PROJECT_NUMBER" ]]; then
  echo "Refusing mutation: active account or project-number preflight failed." >&2
  emit_state "FEDOMEGA-WIF-APPLY-BLOCKED" "IDENTITY_OR_PROJECT_MISMATCH"
  exit 4
fi

if [[ "$SERVICE_EXISTS" != "true" || "$REPO_EXISTS" != "true" ]]; then
  echo "Refusing mutation: target Cloud Run service and Artifact Registry repository must already exist." >&2
  emit_state "FEDOMEGA-WIF-APPLY-BLOCKED" "TARGET_RESOURCE_MISSING"
  exit 5
fi

MUTATION_PERFORMED=true
gcloud config set project "$PROJECT_ID" >/dev/null

gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  --project "$PROJECT_ID"

if [[ "$DEPLOYER_EXISTS" != "true" ]]; then
  gcloud iam service-accounts create "${DEPLOYER_SA%@*}" \
    --project "$PROJECT_ID" --display-name="Federation Omega GitHub deployer"
fi
if [[ "$RUNTIME_EXISTS" != "true" ]]; then
  gcloud iam service-accounts create "${RUNTIME_SA%@*}" \
    --project "$PROJECT_ID" --display-name="Superior Logic runtime"
fi

if [[ "$POOL_STATE" == "NOT_FOUND" ]]; then
  gcloud iam workload-identity-pools undelete "$POOL_ID" \
    --location global --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools create "$POOL_ID" \
    --location global --project "$PROJECT_ID" \
    --display-name="Federation Omega GitHub"
elif [[ "$POOL_STATE" != "ACTIVE" ]]; then
  gcloud iam workload-identity-pools undelete "$POOL_ID" \
    --location global --project "$PROJECT_ID"
fi

if [[ "$PROVIDER_STATE" == "NOT_FOUND" ]]; then
  gcloud iam workload-identity-pools providers undelete "$PROVIDER_ID" \
    --workload-identity-pool "$POOL_ID" \
    --location global --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --workload-identity-pool "$POOL_ID" \
    --location global --project "$PROJECT_ID" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="$EXPECTED_MAPPING" \
    --attribute-condition="$EXPECTED_CONDITION"
else
  if [[ "$PROVIDER_STATE" != "ACTIVE" ]]; then
    gcloud iam workload-identity-pools providers undelete "$PROVIDER_ID" \
      --workload-identity-pool "$POOL_ID" \
      --location global --project "$PROJECT_ID"
  fi
  gcloud iam workload-identity-pools providers update-oidc "$PROVIDER_ID" \
    --workload-identity-pool "$POOL_ID" \
    --location global --project "$PROJECT_ID" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="$EXPECTED_MAPPING" \
    --attribute-condition="$EXPECTED_CONDITION"
fi

gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" \
  --project "$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="$PRINCIPAL" >/dev/null

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --role="roles/serviceusage.serviceUsageConsumer" \
  --member="serviceAccount:${DEPLOYER_SA}" >/dev/null

gcloud run services add-iam-policy-binding "$SERVICE" \
  --project "$PROJECT_ID" --region "$REGION" \
  --role="roles/run.developer" \
  --member="serviceAccount:${DEPLOYER_SA}" >/dev/null

gcloud run services add-iam-policy-binding "$SERVICE" \
  --project "$PROJECT_ID" --region "$REGION" \
  --role="roles/run.invoker" \
  --member="serviceAccount:${DEPLOYER_SA}" >/dev/null

gcloud artifacts repositories add-iam-policy-binding "$AR_REPO" \
  --project "$PROJECT_ID" --location "$REGION" \
  --role="roles/artifactregistry.writer" \
  --member="serviceAccount:${DEPLOYER_SA}" >/dev/null

gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
  --project "$PROJECT_ID" \
  --role="roles/iam.serviceAccountUser" \
  --member="serviceAccount:${DEPLOYER_SA}" >/dev/null

collect_state
if ((${#MISSING[@]} != 0)); then
  emit_state "FEDOMEGA-WIF-APPLY-INCOMPLETE" "APPLIED_BUT_VERIFICATION_FAILED"
  exit 6
fi
emit_state "FEDOMEGA-WIF-CLOUD-VERIFIED" "APPLIED_AND_VERIFIED"
