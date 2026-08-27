#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Federation Ω Shared Automation Authority Fabric — bootstrap v1
#
# Run once from an authenticated Google Cloud Shell.
# - no service-account key is created
# - broad authority exists only on a temporary bootstrap identity
# - the permanent worker stays narrow
# - provider-admin commands elevate by short-lived impersonation only while
#   both the mission lease and the IAM expiry window permit it
###############################################################################

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-africa-south1}"
FED_REPO="${FED_REPO:-mosianekk-lang/Federation-Omega}"
FABRIC_SHEET_ID="${FABRIC_SHEET_ID:-17WRSvjj98RbOKZrnTefcZkfK-z9gZYdZX_pACm8VuOQ}"

[[ -n "$PROJECT_ID" && "$PROJECT_ID" != "(unset)" ]] || {
  echo "ERROR: no active Google Cloud project"
  exit 1
}

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
[[ -n "$ACTIVE_ACCOUNT" ]] || { echo "ERROR: no active gcloud identity"; exit 1; }

BOOTSTRAP_SA_NAME="federation-bootstrap-admin"
RUNTIME_SA_NAME="federation-automation-runtime"
BOOTSTRAP_SA="${BOOTSTRAP_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
RUNTIME_SA="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
POOL_ID="fed-automation-pool"
PROVIDER_ID="github-fed-omega-main"
SERVICE="federation-automation-gateway"
SCHEDULER="federation-automation-tick"
EXPIRY_UTC="$(date -u -d '+6 hours' '+%Y-%m-%dT%H:%M:%SZ')"
CONDITION="expression=request.time < timestamp('${EXPIRY_UTC}'),title=fed_automation_bootstrap,description=Temporary_Federation_bootstrap_authority"

BACKUP_DIR="${HOME}/federation-automation-bootstrap-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"
gcloud projects get-iam-policy "$PROJECT_ID" --format=json > "$BACKUP_DIR/project-iam-before.json"
gcloud services list --project="$PROJECT_ID" --enabled --format=json > "$BACKUP_DIR/enabled-services-before.json"

printf '\n[1/8] Enabling required control APIs...\n'
APIS=(
  serviceusage.googleapis.com
  iam.googleapis.com
  iamcredentials.googleapis.com
  sts.googleapis.com
  cloudresourcemanager.googleapis.com
  script.googleapis.com
  drive.googleapis.com
  sheets.googleapis.com
  run.googleapis.com
  cloudbuild.googleapis.com
  artifactregistry.googleapis.com
  cloudscheduler.googleapis.com
  logging.googleapis.com
  monitoring.googleapis.com
)
gcloud services enable "${APIS[@]}" --project="$PROJECT_ID"

printf '\n[2/8] Creating dedicated identities...\n'
for SA_NAME in "$BOOTSTRAP_SA_NAME" "$RUNTIME_SA_NAME"; do
  SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$SA_NAME" \
      --project="$PROJECT_ID" \
      --display-name="$SA_NAME"
  fi
done

printf '\n[3/8] Granting expiring bootstrap authority...\n'
ADMIN_ROLES=(
  roles/resourcemanager.projectIamAdmin
  roles/serviceusage.serviceUsageAdmin
  roles/iam.serviceAccountAdmin
  roles/iam.serviceAccountUser
  roles/iam.serviceAccountTokenCreator
  roles/iam.workloadIdentityPoolAdmin
  roles/run.admin
  roles/cloudbuild.builds.editor
  roles/artifactregistry.admin
  roles/cloudscheduler.admin
  roles/logging.admin
  roles/monitoring.admin
)
for ROLE in "${ADMIN_ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${BOOTSTRAP_SA}" \
    --role="$ROLE" \
    --condition="$CONDITION" \
    --quiet >/dev/null
done

printf '\n[4/8] Granting narrow permanent runtime baseline...\n'
RUNTIME_ROLES=(
  roles/browser
  roles/serviceusage.serviceUsageViewer
  roles/run.viewer
  roles/logging.logWriter
  roles/monitoring.metricWriter
)
for ROLE in "${RUNTIME_ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="$ROLE" \
    --quiet >/dev/null
done

# Runtime may impersonate the temporary bootstrap identity only until expiry.
gcloud iam service-accounts add-iam-policy-binding "$BOOTSTRAP_SA" \
  --project="$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --condition="$CONDITION" \
  --quiet >/dev/null

printf '\n[5/8] Establishing GitHub WIF restricted to Federation-Omega main...\n'
if ! gcloud iam workload-identity-pools describe "$POOL_ID" \
    --location=global --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL_ID" \
    --location=global --project="$PROJECT_ID" \
    --display-name='Federation Automation Pool'
fi

if ! gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
    --location=global --workload-identity-pool="$POOL_ID" \
    --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --location=global \
    --workload-identity-pool="$POOL_ID" \
    --project="$PROJECT_ID" \
    --issuer-uri='https://token.actions.githubusercontent.com' \
    --attribute-mapping='google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref,attribute.workflow=assertion.workflow,attribute.actor=assertion.actor' \
    --attribute-condition="assertion.repository=='${FED_REPO}' && assertion.ref=='refs/heads/main'"
fi

FED_PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${FED_REPO}"
gcloud iam service-accounts add-iam-policy-binding "$BOOTSTRAP_SA" \
  --project="$PROJECT_ID" \
  --member="$FED_PRINCIPAL" \
  --role=roles/iam.workloadIdentityUser \
  --condition="$CONDITION" \
  --quiet >/dev/null

printf '\n[6/8] Deploying the private shared executor from canonical main...\n'
WORKDIR="$(mktemp -d)"
git clone --depth 1 "https://github.com/${FED_REPO}.git" "$WORKDIR/repo"

gcloud run deploy "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --source="$WORKDIR/repo/federation_automation_gateway" \
  --service-account="$RUNTIME_SA" \
  --no-allow-unauthenticated \
  --max-instances=1 \
  --concurrency=1 \
  --set-env-vars="FED_AUTOMATION_SHEET_ID=${FABRIC_SHEET_ID},FED_BOOTSTRAP_SA=${BOOTSTRAP_SA},PROJECT_ID=${PROJECT_ID}" \
  --quiet

SERVICE_URL="$(gcloud run services describe "$SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)')"

gcloud run services add-iam-policy-binding "$SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role=roles/run.invoker \
  --quiet >/dev/null

printf '\n[7/8] Installing one-minute Johannesburg scheduler...\n'
if gcloud scheduler jobs describe "$SCHEDULER" \
    --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud scheduler jobs delete "$SCHEDULER" \
    --location="$REGION" --project="$PROJECT_ID" --quiet
fi

gcloud scheduler jobs create http "$SCHEDULER" \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --schedule='* * * * *' \
  --time-zone='Africa/Johannesburg' \
  --uri="${SERVICE_URL}/tick" \
  --http-method=POST \
  --oidc-service-account-email="$RUNTIME_SA" \
  --oidc-token-audience="$SERVICE_URL" \
  --quiet

printf '\n[8/8] Creating bootstrap revocation helper...\n'
cat > "${HOME}/revoke-federation-automation-bootstrap.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID='${PROJECT_ID}'
BOOTSTRAP_SA='${BOOTSTRAP_SA}'
RUNTIME_SA='${RUNTIME_SA}'
CONDITION='${CONDITION}'
ADMIN_ROLES=(
$(printf "  '%s'\n" "${ADMIN_ROLES[@]}")
)

# Immediate cutoff first.
gcloud iam service-accounts disable "\${BOOTSTRAP_SA}" --project="\${PROJECT_ID}" --quiet || true

gcloud iam service-accounts remove-iam-policy-binding "\${BOOTSTRAP_SA}" \
  --project="\${PROJECT_ID}" \
  --member="serviceAccount:\${RUNTIME_SA}" \
  --role=roles/iam.serviceAccountTokenCreator \
  --condition="\${CONDITION}" \
  --quiet || true

for ROLE in "\${ADMIN_ROLES[@]}"; do
  gcloud projects remove-iam-policy-binding "\${PROJECT_ID}" \
    --member="serviceAccount:\${BOOTSTRAP_SA}" \
    --role="\${ROLE}" \
    --condition="\${CONDITION}" \
    --quiet || true
done

gcloud iam service-accounts delete "\${BOOTSTRAP_SA}" \
  --project="\${PROJECT_ID}" --quiet || true

echo 'Temporary Federation bootstrap authority revoked. Runtime, control plane, scheduler and WIF pool remain.'
EOF
chmod 700 "${HOME}/revoke-federation-automation-bootstrap.sh"

WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

cat <<EOF

=================================================================
FEDERATION_AUTOMATION_BOOTSTRAP_OK=true
PROJECT_ID=${PROJECT_ID}
PROJECT_NUMBER=${PROJECT_NUMBER}
FABRIC_SHEET_ID=${FABRIC_SHEET_ID}
FED_BOOTSTRAP_SA=${BOOTSTRAP_SA}
FED_RUNTIME_SA=${RUNTIME_SA}
WIF_PROVIDER=${WIF_PROVIDER}
SERVICE_URL=${SERVICE_URL}
EXPIRY_UTC=${EXPIRY_UTC}
IAM_BACKUP=${BACKUP_DIR}/project-iam-before.json
REVOCATION_SCRIPT=${HOME}/revoke-federation-automation-bootstrap.sh
NEXT_REQUIRED_ACTION=Share Fabric Sheet and lab Apps Script projects with FED_RUNTIME_SA; then execute the Kernel Stage-A canary.
=================================================================
NO SERVICE-ACCOUNT PRIVATE KEY WAS CREATED.
EOF
