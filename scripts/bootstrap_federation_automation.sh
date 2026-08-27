#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Federation Ω Shared Automation Authority Fabric — bootstrap v1.1
#
# Run once from an authenticated Google Cloud Shell.
# - no service-account key is created
# - broad Cloud authority exists only on a temporary bootstrap identity
# - the permanent Cloud worker stays narrow
# - provider-admin Cloud commands elevate by short-lived impersonation only
# - Apps Script remains on the separate existing owner-OAuth broker path
###############################################################################

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-africa-south1}"
FED_REPO="${FED_REPO:-mosianekk-lang/Federation-Omega}"
FABRIC_SHEET_ID="${FABRIC_SHEET_ID:-17WRSvjj98RbOKZrnTefcZkfK-z9gZYdZX_pACm8VuOQ}"

# This is not treated as current project truth. It is the consumer project
# number returned by Google's prior Apps Script API 403 from the live owner
# broker. We touch it only if gcloud can independently resolve it for the
# authenticated owner.
OWNER_BROKER_CONSUMER_PROJECT_NUMBER="${OWNER_BROKER_CONSUMER_PROJECT_NUMBER:-516690968552}"

[[ -n "$PROJECT_ID" && "$PROJECT_ID" != "(unset)" ]] || {
  echo "ERROR: no active Google Cloud project"
  exit 1
}

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
CANONICAL_PROJECT_ID_READBACK="$(gcloud projects describe "$PROJECT_NUMBER" --format='value(projectId)')"
ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
[[ -n "$ACTIVE_ACCOUNT" ]] || { echo "ERROR: no active gcloud identity"; exit 1; }

if [[ "$CANONICAL_PROJECT_ID_READBACK" != "$PROJECT_ID" ]]; then
  echo "ERROR: project identity round-trip failed: ${PROJECT_ID} != ${CANONICAL_PROJECT_ID_READBACK}"
  exit 1
fi

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

printf '\n[1/9] Enabling canonical Google Cloud control APIs...\n'
APIS=(
  serviceusage.googleapis.com
  iam.googleapis.com
  iamcredentials.googleapis.com
  sts.googleapis.com
  cloudresourcemanager.googleapis.com
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

printf '\n[2/9] Re-attesting/repairing owner-OAuth Apps Script API consumer...\n'
OWNER_BROKER_PROJECT_ID=""
OWNER_BROKER_API_STATE="NOT_PROVIDER_VISIBLE"
if OWNER_BROKER_PROJECT_ID="$(gcloud projects describe "$OWNER_BROKER_CONSUMER_PROJECT_NUMBER" --format='value(projectId)' 2>/dev/null)" \
   && [[ -n "$OWNER_BROKER_PROJECT_ID" ]]; then
  echo "Owner broker consumer resolves to project: ${OWNER_BROKER_PROJECT_ID} (${OWNER_BROKER_CONSUMER_PROJECT_NUMBER})"
  gcloud projects get-iam-policy "$OWNER_BROKER_PROJECT_ID" --format=json \
    > "$BACKUP_DIR/owner-broker-project-iam-before.json" || true
  if gcloud services enable \
      serviceusage.googleapis.com \
      script.googleapis.com \
      drive.googleapis.com \
      sheets.googleapis.com \
      --project="$OWNER_BROKER_PROJECT_ID"; then
    OWNER_BROKER_API_STATE="ENABLE_REQUEST_ACCEPTED"
  else
    OWNER_BROKER_API_STATE="ENABLE_FAILED"
  fi
else
  OWNER_BROKER_PROJECT_ID=""
  echo "Owner broker consumer project ${OWNER_BROKER_CONSUMER_PROJECT_NUMBER} is not visible to this gcloud identity; leaving it unchanged."
fi

printf '\n[3/9] Creating dedicated Cloud identities...\n'
for SA_NAME in "$BOOTSTRAP_SA_NAME" "$RUNTIME_SA_NAME"; do
  SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$SA_NAME" \
      --project="$PROJECT_ID" \
      --display-name="$SA_NAME"
  fi
done

printf '\n[4/9] Granting expiring bootstrap Cloud authority...\n'
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

printf '\n[5/9] Granting narrow permanent Cloud runtime baseline...\n'
RUNTIME_ROLES=(
  roles/browser
  roles/serviceusage.serviceUsageViewer
  roles/serviceusage.serviceUsageConsumer
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

printf '\n[6/9] Establishing GitHub WIF restricted to Federation-Omega main...\n'
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

printf '\n[7/9] Deploying private Google Cloud executor from canonical main...\n'
WORKDIR="$(mktemp -d)"
git clone --depth 1 "https://github.com/${FED_REPO}.git" "$WORKDIR/repo"

SOURCE_HEAD="$(git -C "$WORKDIR/repo" rev-parse HEAD)"
echo "Deploying canonical main ${SOURCE_HEAD}"

gcloud run deploy "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --source="$WORKDIR/repo/federation_automation_gateway" \
  --service-account="$RUNTIME_SA" \
  --no-allow-unauthenticated \
  --max-instances=1 \
  --concurrency=1 \
  --set-env-vars="FED_AUTOMATION_SHEET_ID=${FABRIC_SHEET_ID},FED_BOOTSTRAP_SA=${BOOTSTRAP_SA},PROJECT_ID=${PROJECT_ID},FED_SOURCE_HEAD=${SOURCE_HEAD}" \
  --quiet

SERVICE_URL="$(gcloud run services describe "$SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)')"

gcloud run services add-iam-policy-binding "$SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role=roles/run.invoker \
  --quiet >/dev/null

printf '\n[8/9] Installing one-minute Johannesburg Cloud executor scheduler...\n'
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

printf '\n[9/9] Creating bootstrap revocation helper...\n'
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

echo 'Temporary Federation bootstrap authority revoked. Narrow runtime, control plane, scheduler, owner-OAuth broker and WIF pool remain.'
EOF
chmod 700 "${HOME}/revoke-federation-automation-bootstrap.sh"

WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

# Provider readback: do not declare bootstrap successful unless the Cloud Run
# identity and scheduler are visible after mutation.
SERVICE_SA_READBACK="$(gcloud run services describe "$SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" --format='value(spec.template.spec.serviceAccountName)')"
SCHEDULER_STATE="$(gcloud scheduler jobs describe "$SCHEDULER" \
  --location="$REGION" --project="$PROJECT_ID" --format='value(state)')"

[[ "$SERVICE_SA_READBACK" == "$RUNTIME_SA" ]] || {
  echo "ERROR: Cloud Run service-account readback mismatch"
  exit 2
}

cat <<EOF

=================================================================
FEDERATION_AUTOMATION_BOOTSTRAP_OK=true
PROJECT_ID=${PROJECT_ID}
PROJECT_NUMBER=${PROJECT_NUMBER}
PROJECT_ID_ROUNDTRIP=${CANONICAL_PROJECT_ID_READBACK}
FABRIC_SHEET_ID=${FABRIC_SHEET_ID}
FED_BOOTSTRAP_SA=${BOOTSTRAP_SA}
FED_RUNTIME_SA=${RUNTIME_SA}
WIF_PROVIDER=${WIF_PROVIDER}
SERVICE_URL=${SERVICE_URL}
SERVICE_IDENTITY_READBACK=${SERVICE_SA_READBACK}
SCHEDULER_STATE=${SCHEDULER_STATE}
SOURCE_HEAD=${SOURCE_HEAD}
OWNER_BROKER_CONSUMER_PROJECT_NUMBER=${OWNER_BROKER_CONSUMER_PROJECT_NUMBER}
OWNER_BROKER_PROJECT_ID=${OWNER_BROKER_PROJECT_ID}
OWNER_BROKER_API_STATE=${OWNER_BROKER_API_STATE}
EXPIRY_UTC=${EXPIRY_UTC}
IAM_BACKUP=${BACKUP_DIR}/project-iam-before.json
REVOCATION_SCRIPT=${HOME}/revoke-federation-automation-bootstrap.sh
NEXT_REQUIRED_ACTION=Share Fabric Sheet with FED_RUNTIME_SA; prove Cloud queue canary; if OWNER_BROKER_API_STATE is healthy, install FED_Automation_Broker.gs through existing owner-OAuth CODE_APPLY and prove Apps Script source/deployment readback.
=================================================================
NO SERVICE-ACCOUNT PRIVATE KEY WAS CREATED.
NO OWNER OAUTH TOKEN WAS EXPORTED.
EOF
