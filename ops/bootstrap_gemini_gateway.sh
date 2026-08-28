#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sov-hybrid-suite}"
PROJECT_NUMBER="${PROJECT_NUMBER:-257649435135}"
REGION="${REGION:-africa-south1}"
AR_REPO="${AR_REPO:-federation-omega}"
DEPLOYER_SA="${DEPLOYER_SA:-superior-logic-deployer@${PROJECT_ID}.iam.gserviceaccount.com}"
RUNTIME_SA_NAME="${RUNTIME_SA_NAME:-sv-gemini-runtime}"
RUNTIME_SA="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
APPLY_CONFIRMATION="ATTACH_GEMINI_GATEWAY_ADC_V1"

MODE="plan"
case "${1:-}" in
  ""|--plan) MODE="plan" ;;
  --apply) MODE="apply" ;;
  --verify) MODE="verify" ;;
  -h|--help)
    echo "Usage: ops/bootstrap_gemini_gateway.sh [--plan|--apply|--verify]"
    exit 0
    ;;
  *) echo "Unknown mode: ${1}" >&2; exit 2 ;;
esac

for bin in gcloud python3; do
  command -v "$bin" >/dev/null 2>&1 || { echo "Missing required command: $bin" >&2; exit 1; }
done

read_value() { "$@" 2>/dev/null || true; }
has_project_role() {
  local member="$1" role="$2"
  local found
  found="$(read_value gcloud projects get-iam-policy "$PROJECT_ID" \
    --flatten='bindings[].members' \
    --filter="bindings.role:${role} AND bindings.members:${member}" \
    --format='value(bindings.role)')"
  grep -Fxq "$role" <<<"$found"
}
has_sa_user_binding() {
  local found
  found="$(read_value gcloud iam service-accounts get-iam-policy "$RUNTIME_SA" \
    --project "$PROJECT_ID" \
    --flatten='bindings[].members' \
    --filter="bindings.role:roles/iam.serviceAccountUser AND bindings.members:serviceAccount:${DEPLOYER_SA}" \
    --format='value(bindings.role)')"
  grep -Fxq "roles/iam.serviceAccountUser" <<<"$found"
}
api_enabled() {
  local api="$1"
  local found
  found="$(read_value gcloud services list --enabled --project "$PROJECT_ID" \
    --filter="config.name=${api}" --format='value(config.name)')"
  grep -Fxq "$api" <<<"$found"
}

collect_state() {
  ACTIVE_ACCOUNT="$(read_value gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
  CONFIG_PROJECT="$(read_value gcloud config get-value project | head -n1)"
  ACTUAL_PROJECT_NUMBER="$(read_value gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' | head -n1)"
  RUNTIME_EXISTS=false
  DEPLOYER_EXISTS=false
  REPO_EXISTS=false

  gcloud iam service-accounts describe "$RUNTIME_SA" --project "$PROJECT_ID" >/dev/null 2>&1 && RUNTIME_EXISTS=true || true
  gcloud iam service-accounts describe "$DEPLOYER_SA" --project "$PROJECT_ID" >/dev/null 2>&1 && DEPLOYER_EXISTS=true || true
  gcloud artifacts repositories describe "$AR_REPO" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1 && REPO_EXISTS=true || true

  AI_PLATFORM_USER=false
  SERVICE_USAGE_CONSUMER=false
  DEPLOYER_SA_USER=false
  DEPLOYER_RUN_DEVELOPER=false
  if [[ "$RUNTIME_EXISTS" == true ]]; then
    has_project_role "serviceAccount:${RUNTIME_SA}" "roles/aiplatform.user" && AI_PLATFORM_USER=true || true
    has_project_role "serviceAccount:${RUNTIME_SA}" "roles/serviceusage.serviceUsageConsumer" && SERVICE_USAGE_CONSUMER=true || true
    [[ "$DEPLOYER_EXISTS" == true ]] && has_sa_user_binding && DEPLOYER_SA_USER=true || true
  fi
  if [[ "$DEPLOYER_EXISTS" == true ]]; then
    has_project_role "serviceAccount:${DEPLOYER_SA}" "roles/run.developer" && DEPLOYER_RUN_DEVELOPER=true || true
  fi

  REQUIRED_APIS=(
    aiplatform.googleapis.com
    run.googleapis.com
    artifactregistry.googleapis.com
  )
  MISSING_APIS=()
  for api in "${REQUIRED_APIS[@]}"; do
    api_enabled "$api" || MISSING_APIS+=("$api")
  done

  MISSING=()
  [[ -n "$ACTIVE_ACCOUNT" ]] || MISSING+=("active_gcloud_account")
  [[ "$ACTUAL_PROJECT_NUMBER" == "$PROJECT_NUMBER" ]] || MISSING+=("canonical_project_number")
  [[ "$DEPLOYER_EXISTS" == true ]] || MISSING+=("deployer_service_account")
  [[ "$RUNTIME_EXISTS" == true ]] || MISSING+=("gemini_runtime_service_account")
  [[ "$REPO_EXISTS" == true ]] || MISSING+=("artifact_registry_repository")
  [[ "$AI_PLATFORM_USER" == true ]] || MISSING+=("aiplatform_user_binding")
  [[ "$SERVICE_USAGE_CONSUMER" == true ]] || MISSING+=("service_usage_consumer_binding")
  [[ "$DEPLOYER_SA_USER" == true ]] || MISSING+=("deployer_service_account_user_binding")
  [[ "$DEPLOYER_RUN_DEVELOPER" == true ]] || MISSING+=("deployer_cloud_run_developer_binding")
  ((${#MISSING_APIS[@]} == 0)) || MISSING+=("required_apis")
}

emit() {
  local receipt="$1" state="$2"
  local missing_json missing_apis_json
  missing_json="$(printf '%s\n' "${MISSING[@]:-}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
  missing_apis_json="$(printf '%s\n' "${MISSING_APIS[@]:-}" | python3 -c 'import json,sys; print(json.dumps([x.strip() for x in sys.stdin if x.strip()]))')"
  python3 - <<PY
import json
print(json.dumps({
  "receipt": "${receipt}",
  "state": "${state}",
  "mode": "${MODE}",
  "project_id": "${PROJECT_ID}",
  "project_number_expected": "${PROJECT_NUMBER}",
  "project_number_observed": "${ACTUAL_PROJECT_NUMBER}",
  "active_account": "${ACTIVE_ACCOUNT}",
  "configured_project": "${CONFIG_PROJECT}",
  "region": "${REGION}",
  "artifact_repository": "${AR_REPO}",
  "deployer_service_account": "${DEPLOYER_SA}",
  "runtime_service_account": "${RUNTIME_SA}",
  "runtime_service_account_exists": "${RUNTIME_EXISTS}" == "true",
  "aiplatform_user": "${AI_PLATFORM_USER}" == "true",
  "service_usage_consumer": "${SERVICE_USAGE_CONSUMER}" == "true",
  "deployer_service_account_user": "${DEPLOYER_SA_USER}" == "true",
  "deployer_cloud_run_developer": "${DEPLOYER_RUN_DEVELOPER}" == "true",
  "missing_apis": ${missing_apis_json},
  "missing_controls": ${missing_json},
  "service_account_key_created": False,
  "secret_payload_accessed": False,
  "mutation_performed": "${MUTATION_PERFORMED:-false}" == "true",
}, sort_keys=True))
PY
}

collect_state
MUTATION_PERFORMED=false

if [[ "$MODE" == "plan" ]]; then
  if ((${#MISSING[@]} == 0)); then
    emit "FEDOMEGA-GEMINI-ADC-PLAN" "READY_FOR_VERIFICATION"
  else
    emit "FEDOMEGA-GEMINI-ADC-PLAN" "PLAN_REQUIRES_CHANGES"
  fi
  exit 0
fi

if [[ "$MODE" == "verify" ]]; then
  if ((${#MISSING[@]} != 0)); then
    emit "FEDOMEGA-GEMINI-ADC-VERIFICATION-FAILED" "NOT_VERIFIED"
    exit 1
  fi
  emit "FEDOMEGA-GEMINI-ADC-VERIFIED" "VERIFIED"
  exit 0
fi

if [[ "${FEDOMEGA_GEMINI_GATEWAY_APPLY:-}" != "$APPLY_CONFIRMATION" ]]; then
  echo "Refusing mutation without FEDOMEGA_GEMINI_GATEWAY_APPLY=${APPLY_CONFIRMATION}" >&2
  emit "FEDOMEGA-GEMINI-ADC-APPLY-BLOCKED" "APPROVAL_REQUIRED"
  exit 3
fi
if [[ -z "$ACTIVE_ACCOUNT" || "$ACTUAL_PROJECT_NUMBER" != "$PROJECT_NUMBER" ]]; then
  echo "Refusing mutation: active Google identity or canonical project mismatch." >&2
  emit "FEDOMEGA-GEMINI-ADC-APPLY-BLOCKED" "IDENTITY_OR_PROJECT_MISMATCH"
  exit 4
fi
if [[ "$DEPLOYER_EXISTS" != true || "$REPO_EXISTS" != true ]]; then
  echo "Refusing mutation: existing deployer and Artifact Registry repository are required." >&2
  emit "FEDOMEGA-GEMINI-ADC-APPLY-BLOCKED" "REQUIRED_RESOURCE_MISSING"
  exit 5
fi

MUTATION_PERFORMED=true
gcloud config set project "$PROJECT_ID" >/dev/null

# Only request Service Usage mutation when the readback proves an API is missing.
# This keeps G1 least-privilege and avoids requiring Service Usage Admin merely to
# re-enable services that are already active.
if ((${#MISSING_APIS[@]} > 0)); then
  gcloud services enable "${MISSING_APIS[@]}" --project "$PROJECT_ID"
fi

if [[ "$RUNTIME_EXISTS" != true ]]; then
  gcloud iam service-accounts create "$RUNTIME_SA_NAME" \
    --project "$PROJECT_ID" \
    --display-name "SOVARA Gemini Runtime"
fi

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:${RUNTIME_SA}" \
  --role roles/aiplatform.user \
  --condition=None >/dev/null

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:${RUNTIME_SA}" \
  --role roles/serviceusage.serviceUsageConsumer \
  --condition=None >/dev/null

gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
  --project "$PROJECT_ID" \
  --member "serviceAccount:${DEPLOYER_SA}" \
  --role roles/iam.serviceAccountUser \
  --condition=None >/dev/null

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:${DEPLOYER_SA}" \
  --role roles/run.developer \
  --condition=None >/dev/null

collect_state
if ((${#MISSING[@]} != 0)); then
  emit "FEDOMEGA-GEMINI-ADC-APPLY-PARTIAL" "NOT_VERIFIED"
  exit 1
fi
emit "FEDOMEGA-GEMINI-ADC-VERIFIED" "VERIFIED"
