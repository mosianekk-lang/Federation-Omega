#!/usr/bin/env bash
set -euo pipefail

# JARVIS ΑΩ5 / Phoenix-compatible bootstrap for a dedicated read-only Google
# identity used only by the active Bubbles provider-surface readback job.
#
# This script deliberately creates NO service-account key and grants NO mutation
# role. It fail-closes if the canonical project identity does not match the
# provider-backed resource project number already recorded by the Federation.

PROJECT_ID="${PROJECT_ID:-sov-hybrid-suite}"
EXPECTED_PROJECT_NUMBER="${EXPECTED_PROJECT_NUMBER:-257649435135}"
REGION="${REGION:-africa-south1}"
SERVICE_ACCOUNT_ID="${SERVICE_ACCOUNT_ID:-bubbles-readonly}"
POOL_ID="${POOL_ID:-github-bubbles-readonly}"
PROVIDER_ID="${PROVIDER_ID:-federation-omega-main}"
REPOSITORY="${REPOSITORY:-mosianekk-lang/Federation-Omega}"
REPOSITORY_ID="${REPOSITORY_ID:-1292795464}"
REPOSITORY_OWNER_ID="${REPOSITORY_OWNER_ID:-261966700}"
WORKFLOW_REF="${WORKFLOW_REF:-mosianekk-lang/Federation-Omega/.github/workflows/bubbles-command-bus.yml@refs/heads/main}"

SA_EMAIL="${SERVICE_ACCOUNT_ID}@${PROJECT_ID}.iam.gserviceaccount.com"

printf '== ΑΩ5 Bubbles GCP read-only WIF bootstrap ==\n'
printf 'project_id=%s\n' "${PROJECT_ID}"
printf 'expected_project_number=%s\n' "${EXPECTED_PROJECT_NUMBER}"
printf 'service_account=%s\n' "${SA_EMAIL}"
printf 'repository=%s\n' "${REPOSITORY}"
printf 'workflow_ref=%s\n' "${WORKFLOW_REF}"

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
if [[ -z "${ACTIVE_ACCOUNT}" ]]; then
  echo 'FAIL: no active gcloud identity.' >&2
  exit 10
fi
printf 'active_gcloud_account=%s\n' "${ACTIVE_ACCOUNT}"

ACTUAL_PROJECT_NUMBER="$(
  gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)'
)"
if [[ "${ACTUAL_PROJECT_NUMBER}" != "${EXPECTED_PROJECT_NUMBER}" ]]; then
  printf 'FAIL: project identity mismatch: expected %s, observed %s\n' \
    "${EXPECTED_PROJECT_NUMBER}" "${ACTUAL_PROJECT_NUMBER}" >&2
  exit 11
fi
printf 'project_identity=VERIFIED\n'

# APIs required only for keyless identity exchange/impersonation. Cloud Run and
# Cloud Build already exist in the target project and are not enabled here.
gcloud services enable \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  --project="${PROJECT_ID}" \
  --quiet

if ! gcloud iam service-accounts describe "${SA_EMAIL}" \
  --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SERVICE_ACCOUNT_ID}" \
    --project="${PROJECT_ID}" \
    --display-name='Bubbles read-only provider verifier' \
    --description='Keyless GitHub OIDC identity for read-only Phoenix/Bubbles provider readback.'
fi

READ_ONLY_ROLES=(
  roles/browser
  roles/run.viewer
  roles/cloudbuild.builds.viewer
  roles/iam.serviceAccountViewer
)

for role in "${READ_ONLY_ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${role}" \
    --condition=None \
    --quiet >/dev/null
done

if ! gcloud iam workload-identity-pools describe "${POOL_ID}" \
  --project="${PROJECT_ID}" \
  --location=global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "${POOL_ID}" \
    --project="${PROJECT_ID}" \
    --location=global \
    --display-name='Bubbles GitHub read-only'
fi

ATTRIBUTE_MAPPING='google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id,attribute.ref=assertion.ref,attribute.workflow_ref=assertion.workflow_ref'
ATTRIBUTE_CONDITION="assertion.repository_id=='${REPOSITORY_ID}' && assertion.repository_owner_id=='${REPOSITORY_OWNER_ID}' && assertion.ref=='refs/heads/main' && assertion.workflow_ref=='${WORKFLOW_REF}'"

if gcloud iam workload-identity-pools providers describe "${PROVIDER_ID}" \
  --project="${PROJECT_ID}" \
  --location=global \
  --workload-identity-pool="${POOL_ID}" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers update-oidc "${PROVIDER_ID}" \
    --project="${PROJECT_ID}" \
    --location=global \
    --workload-identity-pool="${POOL_ID}" \
    --issuer-uri='https://token.actions.githubusercontent.com' \
    --attribute-mapping="${ATTRIBUTE_MAPPING}" \
    --attribute-condition="${ATTRIBUTE_CONDITION}"
else
  gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_ID}" \
    --project="${PROJECT_ID}" \
    --location=global \
    --workload-identity-pool="${POOL_ID}" \
    --display-name='Federation Omega Bubbles main' \
    --issuer-uri='https://token.actions.githubusercontent.com' \
    --attribute-mapping="${ATTRIBUTE_MAPPING}" \
    --attribute-condition="${ATTRIBUTE_CONDITION}"
fi

POOL_NAME="$(
  gcloud iam workload-identity-pools describe "${POOL_ID}" \
    --project="${PROJECT_ID}" \
    --location=global \
    --format='value(name)'
)"
PROVIDER_NAME="$(
  gcloud iam workload-identity-pools providers describe "${PROVIDER_ID}" \
    --project="${PROJECT_ID}" \
    --location=global \
    --workload-identity-pool="${POOL_ID}" \
    --format='value(name)'
)"

# The member is repository-ID scoped; the provider condition narrows admission
# further to the exact owner ID, main ref and Bubbles workflow_ref.
PRINCIPAL_SET="principalSet://iam.googleapis.com/${POOL_NAME}/attribute.repository_id/${REPOSITORY_ID}"

gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --project="${PROJECT_ID}" \
  --role='roles/iam.workloadIdentityUser' \
  --member="${PRINCIPAL_SET}" \
  --quiet >/dev/null

# Provider-native readback. No credential values are emitted.
printf '\n== Provider readback ==\n'
gcloud projects describe "${PROJECT_ID}" \
  --format='json(projectId,projectNumber,lifecycleState,name)'
gcloud iam workload-identity-pools providers describe "${PROVIDER_ID}" \
  --project="${PROJECT_ID}" \
  --location=global \
  --workload-identity-pool="${POOL_ID}" \
  --format='json(name,state,attributeMapping,attributeCondition,oidc.issuerUri)'
gcloud iam service-accounts get-iam-policy "${SA_EMAIL}" \
  --project="${PROJECT_ID}" \
  --format=json

gcloud projects get-iam-policy "${PROJECT_ID}" \
  --flatten='bindings[].members' \
  --filter="bindings.members:serviceAccount:${SA_EMAIL}" \
  --format='table(bindings.role,bindings.members)'

printf '\nBUBBLES_GCP_WIF_PROVIDER=%s\n' "${PROVIDER_NAME}"
printf 'BUBBLES_GCP_SERVICE_ACCOUNT=%s\n' "${SA_EMAIL}"
printf 'BUBBLES_GCP_AUTH_MODEL=KEYLESS_WIF_SERVICE_ACCOUNT_IMPERSONATION\n'
printf 'BUBBLES_GCP_MUTATION_ROLES_GRANTED=NONE\n'
printf 'BUBBLES_GCP_READ_ONLY_BOOTSTRAP=COMPLETE_PROVIDER_READBACK_REQUIRED\n'
