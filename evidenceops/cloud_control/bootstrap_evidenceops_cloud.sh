#!/usr/bin/env bash
set -euo pipefail

# EvidenceOps keyless Google Cloud discovery and governed operations bootstrap.
# Run in Cloud Shell. It never creates or downloads a service-account key.

MODE="${1:-discover}"
PROJECT_ID="${EVIDENCEOPS_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${EVIDENCEOPS_REGION:-africa-south1}"
GITHUB_REPOSITORY="${EVIDENCEOPS_GITHUB_REPOSITORY:-}"
AUTHORITY_PROFILE="${EVIDENCEOPS_AUTHORITY_PROFILE:-sovereign-full}"
AUTHORITY_CONFIRMATION="${EVIDENCEOPS_AUTHORITY_CONFIRMATION:-}"
OPERATOR_NAME="evidenceops-cloud-operator"
OPERATOR_SA="${OPERATOR_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
MCP_SA="evidenceops-mcp-runtime@${PROJECT_ID}.iam.gserviceaccount.com"
SCB_NAME="evidenceops-secure-capability-box"
SCB_SA="${SCB_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
WIF_POOL="evidenceops-github"
WIF_PROVIDER="github"
INVENTORY_DIR="${EVIDENCEOPS_INVENTORY_DIR:-$PWD/evidenceops-cloud-inventory}"
MANAGEMENT_CLAIM="${EVIDENCEOPS_MANAGEMENT_CLAIM:-DISCOVERY_ONLY_UNTIL_BOOTSTRAP_AND_ACTION_READBACK}"

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo "Set EVIDENCEOPS_PROJECT_ID or run: gcloud config set project PROJECT_ID" >&2
  exit 2
fi

if [[ "$MODE" == "bootstrap" && "$AUTHORITY_PROFILE" == "sovereign-full" ]]; then
  expected_confirmation="AUTHORISE_EVIDENCEOPS_FULL_PROJECT_CONTROL_${PROJECT_ID}"
  if [[ "$AUTHORITY_CONFIRMATION" != "$expected_confirmation" ]]; then
    echo "Set EVIDENCEOPS_AUTHORITY_CONFIRMATION=${expected_confirmation}" >&2
    echo "This is required because sovereign-full grants project Owner authority to the EvidenceOps operator identity." >&2
    exit 3
  fi
fi

case "$MODE" in
  discover|bootstrap|deploy|verify) ;;
  *) echo "Usage: $0 {discover|bootstrap|deploy|verify}" >&2; exit 2 ;;
esac

scope="projects/${PROJECT_ID}"
mkdir -p "$INVENTORY_DIR"

inventory() {
  gcloud services list --project "$PROJECT_ID" --enabled --format=json \
    > "$INVENTORY_DIR/enabled-services.json"
  gcloud asset search-all-resources --scope "$scope" --format=json \
    > "$INVENTORY_DIR/resources.json"
  gcloud asset search-all-iam-policies --scope "$scope" --format=json \
    > "$INVENTORY_DIR/iam-policies.json"
  gcloud iam service-accounts list --project "$PROJECT_ID" --format=json \
    > "$INVENTORY_DIR/service-accounts.json"
  gcloud run services list --project "$PROJECT_ID" --platform=managed \
    --format=json > "$INVENTORY_DIR/cloud-run-services.json"
  gcloud run jobs list --project "$PROJECT_ID" --format=json \
    > "$INVENTORY_DIR/cloud-run-jobs.json"
  gcloud secrets list --project "$PROJECT_ID" --format=json \
    > "$INVENTORY_DIR/secret-metadata.json"
  gcloud pubsub topics list --project "$PROJECT_ID" --format=json \
    > "$INVENTORY_DIR/pubsub-topics.json"
  gcloud scheduler jobs list --project "$PROJECT_ID" --location "$REGION" \
    --format=json > "$INVENTORY_DIR/scheduler-jobs.json" 2>/dev/null || true
  python3 - "$INVENTORY_DIR" "$PROJECT_ID" "$MANAGEMENT_CLAIM" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
files = sorted(p for p in root.glob("*.json") if p.name != "manifest.json")
manifest = {
    "schema": "EVIDENCEOPS-CLOUD-CAPABILITY-INVENTORY-1",
    "project_id": sys.argv[2],
    "files": {
        p.name: {
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "items": len(json.loads(p.read_text(encoding="utf-8"))),
        }
        for p in files
    },
    "credentials_exported": False,
    "management_claim": sys.argv[3],
}
(root / "manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(json.dumps(manifest, indent=2, sort_keys=True))
PY
}

if [[ "$MODE" == "discover" ]]; then
  gcloud services enable cloudasset.googleapis.com serviceusage.googleapis.com \
    --project "$PROJECT_ID"
  inventory
  exit 0
fi

if [[ "$MODE" == "bootstrap" ]]; then
  apis=(
    artifactregistry.googleapis.com cloudasset.googleapis.com cloudbuild.googleapis.com
    cloudscheduler.googleapis.com iam.googleapis.com iamcredentials.googleapis.com
    logging.googleapis.com monitoring.googleapis.com pubsub.googleapis.com
    recommender.googleapis.com run.googleapis.com secretmanager.googleapis.com
    serviceusage.googleapis.com sts.googleapis.com
  )
  gcloud services enable "${apis[@]}" --project "$PROJECT_ID"

  gcloud iam service-accounts describe "$OPERATOR_SA" --project "$PROJECT_ID" \
    >/dev/null 2>&1 || gcloud iam service-accounts create "$OPERATOR_NAME" \
      --project "$PROJECT_ID" --display-name="EvidenceOps governed cloud operator"

  discovery_roles=(
    roles/browser roles/cloudasset.viewer roles/iam.securityReviewer
    roles/logging.viewer roles/monitoring.viewer
    roles/recommender.viewer roles/serviceusage.serviceUsageConsumer
    roles/serviceusage.serviceUsageViewer
  )
  operation_roles=(
    roles/artifactregistry.writer roles/cloudbuild.builds.editor
    roles/cloudscheduler.admin roles/logging.configWriter roles/monitoring.editor
    roles/pubsub.editor roles/run.admin roles/secretmanager.viewer
  )
  for role in "${discovery_roles[@]}" "${operation_roles[@]}"; do
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="serviceAccount:${OPERATOR_SA}" --role="$role" \
      --condition=None --quiet >/dev/null
  done
  if [[ "$AUTHORITY_PROFILE" == "sovereign-full" ]]; then
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="serviceAccount:${OPERATOR_SA}" --role=roles/owner \
      --condition=None --quiet >/dev/null
  elif [[ "$AUTHORITY_PROFILE" != "scoped" ]]; then
    echo "EVIDENCEOPS_AUTHORITY_PROFILE must be sovereign-full or scoped" >&2
    exit 2
  fi
  gcloud iam service-accounts add-iam-policy-binding "$OPERATOR_SA" \
    --project "$PROJECT_ID" --member="serviceAccount:${OPERATOR_SA}" \
    --role=roles/iam.serviceAccountUser --quiet >/dev/null

  gcloud iam service-accounts describe "$SCB_SA" --project "$PROJECT_ID" \
    >/dev/null 2>&1 || gcloud iam service-accounts create "$SCB_NAME" \
      --project "$PROJECT_ID" --display-name="EvidenceOps Secure Capability Box"

  for secret in evidenceops-heartbeat-token evidenceops-mcp-access-token fo-operator-admin-token omega-mcp-shared-secret secure-capability-box-api-token secure-capability-box-signing-key; do
    gcloud secrets describe "$secret" --project "$PROJECT_ID" >/dev/null 2>&1 || \
      gcloud secrets create "$secret" --project "$PROJECT_ID" \
        --replication-policy=automatic
    gcloud secrets add-iam-policy-binding "$secret" --project "$PROJECT_ID" \
      --member="serviceAccount:${OPERATOR_SA}" \
      --role="roles/secretmanager.secretAccessor" --quiet >/dev/null
    if gcloud iam service-accounts describe "$MCP_SA" --project "$PROJECT_ID" >/dev/null 2>&1; then
      gcloud secrets add-iam-policy-binding "$secret" --project "$PROJECT_ID" \
        --member="serviceAccount:${MCP_SA}" \
        --role="roles/secretmanager.secretAccessor" --quiet >/dev/null
    fi
  done

  for secret in secure-capability-box-api-token secure-capability-box-signing-key; do
    if [[ "$(gcloud secrets versions list "$secret" --project "$PROJECT_ID" --filter='state=ENABLED' --format='value(name)' --limit=1)" == "" ]]; then
      openssl rand -base64 48 | tr '+/' '-_' | tr -d '\n=' | \
        gcloud secrets versions add "$secret" --project "$PROJECT_ID" --data-file=- >/dev/null
    fi
  done
  for secret in secure-capability-box-api-token secure-capability-box-signing-key fo-operator-admin-token; do
    gcloud secrets add-iam-policy-binding "$secret" --project "$PROJECT_ID" \
      --member="serviceAccount:${SCB_SA}" \
      --role="roles/secretmanager.secretAccessor" --quiet >/dev/null
  done

  gcloud pubsub topics describe evidenceops-heartbeat-events --project "$PROJECT_ID" \
    >/dev/null 2>&1 || gcloud pubsub topics create evidenceops-heartbeat-events \
      --project "$PROJECT_ID"
  gcloud pubsub subscriptions describe evidenceops-heartbeat-operator \
    --project "$PROJECT_ID" >/dev/null 2>&1 || \
    gcloud pubsub subscriptions create evidenceops-heartbeat-operator \
      --project "$PROJECT_ID" --topic=evidenceops-heartbeat-events \
      --ack-deadline=60 --message-retention-duration=7d
  gcloud pubsub subscriptions describe evidenceops-heartbeat-verifier \
    --project "$PROJECT_ID" >/dev/null 2>&1 || \
    gcloud pubsub subscriptions create evidenceops-heartbeat-verifier \
      --project "$PROJECT_ID" --topic=evidenceops-heartbeat-events \
      --ack-deadline=60 --message-retention-duration=1d
  gcloud pubsub topics add-iam-policy-binding evidenceops-heartbeat-events \
    --project "$PROJECT_ID" --member="serviceAccount:${OPERATOR_SA}" \
    --role=roles/pubsub.publisher --quiet >/dev/null
  gcloud pubsub subscriptions add-iam-policy-binding evidenceops-heartbeat-operator \
    --project "$PROJECT_ID" --member="serviceAccount:${OPERATOR_SA}" \
    --role=roles/pubsub.subscriber --quiet >/dev/null

  if gcloud iam service-accounts describe "$MCP_SA" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud iam service-accounts add-iam-policy-binding "$MCP_SA" \
      --project "$PROJECT_ID" --member="serviceAccount:${OPERATOR_SA}" \
      --role=roles/iam.serviceAccountUser --quiet >/dev/null
    gcloud pubsub topics add-iam-policy-binding evidenceops-heartbeat-events \
      --project "$PROJECT_ID" --member="serviceAccount:${MCP_SA}" \
      --role=roles/pubsub.publisher --quiet >/dev/null
    for service in evidenceops-sovereign-runtime federation-omega-operator; do
      if gcloud run services describe "$service" --region "$REGION" \
        --project "$PROJECT_ID" >/dev/null 2>&1; then
        gcloud run services add-iam-policy-binding "$service" \
          --region "$REGION" --project "$PROJECT_ID" \
          --member="serviceAccount:${MCP_SA}" --role=roles/run.invoker \
          --quiet >/dev/null
      fi
    done
  fi

  # Optional, keyless GitHub Actions federation. The repository condition is mandatory.
  if [[ -n "$GITHUB_REPOSITORY" ]]; then
    project_number="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
    gcloud iam workload-identity-pools describe "$WIF_POOL" --location=global \
      --project "$PROJECT_ID" >/dev/null 2>&1 || \
      gcloud iam workload-identity-pools create "$WIF_POOL" --location=global \
        --project "$PROJECT_ID" --display-name="EvidenceOps GitHub"
    gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER" \
      --workload-identity-pool="$WIF_POOL" --location=global \
      --project "$PROJECT_ID" >/dev/null 2>&1 || \
      gcloud iam workload-identity-pools providers create-oidc "$WIF_PROVIDER" \
        --workload-identity-pool="$WIF_POOL" --location=global \
        --project "$PROJECT_ID" \
        --issuer-uri="https://token.actions.githubusercontent.com" \
        --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
        --attribute-condition="assertion.repository=='${GITHUB_REPOSITORY}' && assertion.ref=='refs/heads/main'"
    principal="principalSet://iam.googleapis.com/projects/${project_number}/locations/global/workloadIdentityPools/${WIF_POOL}/attribute.repository/${GITHUB_REPOSITORY}"
    gcloud iam service-accounts add-iam-policy-binding "$OPERATOR_SA" \
      --project "$PROJECT_ID" --member="$principal" \
      --role=roles/iam.workloadIdentityUser --quiet >/dev/null
  fi

  inventory
  echo "BOOTSTRAP_COMPLETE_AUTHORITY_PROFILE=${AUTHORITY_PROFILE}_NO_SERVICE_ACCOUNT_KEYS_CREATED"
  exit 0
fi

if [[ "$MODE" == "deploy" ]]; then
  if [[ ! -d omega_control_plane ]]; then
    echo "Run deploy from the Federation-Omega repository root." >&2
    exit 4
  fi
  if [[ ! -d evidenceops/secure_capability_box ]]; then
    echo "Secure Capability Box source is missing." >&2
    exit 4
  fi
  if ! gcloud secrets describe omega-mcp-shared-secret --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud secrets create omega-mcp-shared-secret --project "$PROJECT_ID" \
      --replication-policy=automatic
  fi
  enabled_version="$(gcloud secrets versions list omega-mcp-shared-secret \
    --project "$PROJECT_ID" --filter='state=ENABLED' --format='value(name)' \
    --limit=1)"
  if [[ -z "$enabled_version" ]]; then
    openssl rand -hex 48 | gcloud secrets versions add omega-mcp-shared-secret \
      --project "$PROJECT_ID" --data-file=- >/dev/null
  fi
  gcloud run deploy evidenceops-omega-control-plane \
    --project "$PROJECT_ID" --region "$REGION" --source=omega_control_plane \
    --service-account="$OPERATOR_SA" --allow-unauthenticated \
    --set-env-vars="PROJECT_ID=${PROJECT_ID},REGION=${REGION},ALLOW_MUTATIONS=true" \
    --set-secrets="OMEGA_MCP_SHARED_SECRET=omega-mcp-shared-secret:latest" \
    --min-instances=0 --max-instances=3 --memory=512Mi --cpu=1 \
    --timeout=120 --quiet
  service_url="$(gcloud run services describe evidenceops-omega-control-plane \
    --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
  curl --fail --silent "$service_url/health" > "$INVENTORY_DIR/omega-health.json"
  python3 - "$INVENTORY_DIR/omega-health.json" "$PROJECT_ID" <<'PY'
import json, pathlib, sys
data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert data.get("ok") is True
assert data.get("projectId") == sys.argv[2]
print(json.dumps(data, indent=2, sort_keys=True))
PY
  echo "OMEGA_MCP_URL=${service_url}/mcp"
  python3 - "$INVENTORY_DIR/chatgpt-activation.json" "$service_url" "$PROJECT_ID" <<'PY'
import json, pathlib, sys
path, service_url, project_id = sys.argv[1:]
activation = {
    "schema": "EVIDENCEOPS-CHATGPT-CONNECTOR-ACTIVATION-1",
    "project_id": project_id,
    "mcp_url": service_url + "/mcp",
    "authentication": "BEARER_SECRET_REFERENCE",
    "secret_reference": "omega-mcp-shared-secret:latest",
    "cloud_runtime_state": "DEPLOYED_HEALTH_READBACK_VERIFIED",
    "chatgpt_registration_state": "OPENAI_ADMIN_UI_AUTHORITY_REQUIRED",
    "full_write_requirement": "CHATGPT_BUSINESS_OR_ENTERPRISE_EDU",
    "registration_api_state": "NO_SUPPORTED_PUBLIC_API",
    "mission_complete": False,
}
pathlib.Path(path).write_text(
    json.dumps(activation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
print(json.dumps(activation, indent=2, sort_keys=True))
PY
  fo_service_url="$(gcloud run services describe federation-omega-operator \
    --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
  if [[ -z "$fo_service_url" ]]; then
    echo "Federation Omega operator is not deployed." >&2
    exit 5
  fi
  fo_secret_version="$(gcloud secrets versions list fo-operator-admin-token \
    --project "$PROJECT_ID" --filter='state=ENABLED' --format='value(name)' --limit=1)"
  if [[ -z "$fo_secret_version" ]]; then
    echo "Federation Omega admin token has no enabled version." >&2
    exit 5
  fi
  gcloud run deploy "$SCB_NAME" \
    --project "$PROJECT_ID" --region "$REGION" \
    --source=evidenceops/secure_capability_box \
    --service-account="$SCB_SA" --no-allow-unauthenticated \
    --set-env-vars="SCB_KEY_ID=scb-runtime-v1,SCB_SUBJECT=evidenceops-mcp-runtime,SCB_AUDIENCE=federation-omega,SCB_AUTHORITY=A1,SCB_SECRET_PROJECT=${PROJECT_ID},SCB_SECRET_NAME=fo-operator-admin-token,SCB_SECRET_VERSION=${fo_secret_version},SCB_ALLOWED_ACTIONS=STATUS\\,READ_BUILD\\,READ_CLOUD_RUN_SERVICE\\,VERIFY_ARCHITRON_HEALTH,FO_OPERATOR_URL=${fo_service_url},SCB_DB_PATH=/tmp/secure-capability-box.sqlite" \
    --set-secrets="SCB_API_TOKEN=secure-capability-box-api-token:latest,SCB_SIGNING_KEY=secure-capability-box-signing-key:latest" \
    --min-instances=0 --max-instances=1 --concurrency=1 \
    --memory=512Mi --cpu=1 --timeout=120 --quiet
  for member in "$OPERATOR_SA" "$MCP_SA"; do
    if gcloud iam service-accounts describe "$member" --project "$PROJECT_ID" >/dev/null 2>&1; then
      gcloud run services add-iam-policy-binding "$SCB_NAME" \
        --project "$PROJECT_ID" --region "$REGION" \
        --member="serviceAccount:${member}" --role=roles/run.invoker --quiet >/dev/null
    fi
  done
  scb_url="$(gcloud run services describe "$SCB_NAME" \
    --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
  scb_api_token="$(gcloud secrets versions access latest \
    --secret=secure-capability-box-api-token --project="$PROJECT_ID")"
  identity_token="$(gcloud auth print-identity-token)"
  curl --fail --silent "$scb_url/health" \
    -H "Authorization: Bearer ${identity_token}" > "$INVENTORY_DIR/secure-box-health.json"
  operation_id="scb-canary-$(date -u +%Y%m%dT%H%M%SZ)-${RANDOM}"
  python3 - "$INVENTORY_DIR/secure-box-issue.json" "$operation_id" <<'PY'
import json, pathlib, sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({
  "mission_id":"EVIDENCEOPS-SECURE-BOX-LIVE-ACTIVATION",
  "mission_version":6,"operation_id":sys.argv[2],
  "action":"STATUS","ttl_seconds":120
}),encoding="utf-8")
PY
  curl --fail --silent "$scb_url/v1/capabilities/issue" \
    -H "Authorization: Bearer ${identity_token}" \
    -H "x-scb-api-token: ${scb_api_token}" -H 'content-type: application/json' \
    --data-binary "@$INVENTORY_DIR/secure-box-issue.json" \
    > "$INVENTORY_DIR/secure-box-issued.json"
  python3 - "$INVENTORY_DIR/secure-box-issued.json" "$INVENTORY_DIR/secure-box-execute.json" <<'PY'
import json, pathlib, sys
issued=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert issued.get("handle")
pathlib.Path(sys.argv[2]).write_text(json.dumps({"handle":issued["handle"],"payload":{}}),encoding="utf-8")
PY
  curl --fail --silent "$scb_url/v1/capabilities/execute" \
    -H "Authorization: Bearer ${identity_token}" \
    -H "x-scb-api-token: ${scb_api_token}" -H 'content-type: application/json' \
    --data-binary "@$INVENTORY_DIR/secure-box-execute.json" \
    > "$INVENTORY_DIR/secure-box-receipt.json"
  python3 - "$INVENTORY_DIR/secure-box-receipt.json" <<'PY'
import json, pathlib, sys
receipt=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert receipt.get("state") == "COMPLETED", receipt
assert receipt.get("result_digest"), receipt
print("SECURE_CAPABILITY_BOX_DEPLOYMENT_AND_LIVE_READBACK_VERIFIED")
PY
  unset scb_api_token identity_token
  rm -f "$INVENTORY_DIR/secure-box-issued.json" "$INVENTORY_DIR/secure-box-execute.json"
  echo "SECURE_CAPABILITY_BOX_URL=${scb_url}"
  echo "Cloud deployment is complete; ChatGPT activation remains open until OpenAI's authenticated admin publication gate is satisfied."
  exit 0
fi

# verify
gcloud iam service-accounts describe "$OPERATOR_SA" --project "$PROJECT_ID" \
  --format='yaml(email,disabled,uniqueId)'
gcloud projects get-iam-policy "$PROJECT_ID" \
  --flatten='bindings[].members' \
  --filter="bindings.members:serviceAccount:${OPERATOR_SA}" \
  --format='table(bindings.role)'
gcloud pubsub topics describe evidenceops-heartbeat-events --project "$PROJECT_ID" \
  --format='yaml(name)'
service_url="$(gcloud run services describe evidenceops-omega-control-plane \
  --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
if [[ -z "$service_url" ]]; then
  echo "Omega control plane is not deployed." >&2
  exit 5
fi
mcp_secret="$(gcloud secrets versions access latest \
  --secret=omega-mcp-shared-secret --project="$PROJECT_ID")"
canary_id="OMEGA-CANARY-$(date -u +%Y%m%dT%H%M%SZ)-${RANDOM}"
receipt_hash="$(printf '%s' "${PROJECT_ID}:${canary_id}" | sha256sum | cut -d' ' -f1)"
canary_dir="$(mktemp -d)"
gcloud pubsub subscriptions describe evidenceops-heartbeat-verifier \
  --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud pubsub subscriptions create evidenceops-heartbeat-verifier \
    --project "$PROJECT_ID" --topic=evidenceops-heartbeat-events \
    --ack-deadline=60 --message-retention-duration=1d

python3 - "$canary_dir/inventory-request.json" <<'PY'
import json, pathlib, sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({
    "jsonrpc":"2.0","id":"inventory-canary","method":"tools/call",
    "params":{"name":"omega_inventory","arguments":{}}
}), encoding="utf-8")
PY
curl --fail --silent "$service_url/mcp" \
  -H "Authorization: Bearer ${mcp_secret}" -H 'Content-Type: application/json' \
  --data-binary "@$canary_dir/inventory-request.json" \
  > "$canary_dir/inventory-response.json"
python3 - "$canary_dir/inventory-response.json" "$PROJECT_ID" <<'PY'
import json, pathlib, sys
data=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert "error" not in data, data
result=data["result"]["structuredContent"]
assert result["projectId"] == sys.argv[2]
assert result["resourceCount"] > 0
PY

python3 - "$canary_dir/heartbeat-request.json" "$canary_id" "$receipt_hash" <<'PY'
import json, pathlib, sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({
    "jsonrpc":"2.0","id":"heartbeat-canary","method":"tools/call",
    "params":{"name":"omega_publish_heartbeat","arguments":{
        "eventId":sys.argv[2],"nodeId":"HB-GOOGLE-CLOUD",
        "state":"ACTIVE","receiptHash":sys.argv[3]
    }}
}), encoding="utf-8")
PY
curl --fail --silent "$service_url/mcp" \
  -H "Authorization: Bearer ${mcp_secret}" -H 'Content-Type: application/json' \
  --data-binary "@$canary_dir/heartbeat-request.json" \
  > "$canary_dir/heartbeat-response.json"

heartbeat_seen=false
for attempt in 1 2 3 4 5; do
  gcloud pubsub subscriptions pull evidenceops-heartbeat-verifier \
    --project "$PROJECT_ID" --auto-ack --limit=20 --format=json \
    > "$canary_dir/pulled.json"
  if python3 - "$canary_dir/pulled.json" "$canary_id" <<'PY'
import json, pathlib, sys
rows=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8") or "[]")
raise SystemExit(0 if any(
    row.get("message",{}).get("attributes",{}).get("eventId") == sys.argv[2]
    for row in rows
) else 1)
PY
  then heartbeat_seen=true; break; fi
  sleep 2
done
if [[ "$heartbeat_seen" != true ]]; then
  echo "Heartbeat provider readback failed." >&2
  exit 6
fi

topic_url="https://pubsub.googleapis.com/v1/projects/${PROJECT_ID}/topics/evidenceops-heartbeat-events"
gcloud pubsub topics describe evidenceops-heartbeat-events --project "$PROJECT_ID" \
  --format=json > "$canary_dir/topic-before.json"
python3 - "$canary_dir" "$topic_url" "$canary_id" <<'PY'
import json, pathlib, sys
root, url, canary = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
before=json.loads((root/"topic-before.json").read_text(encoding="utf-8"))
labels=dict(before.get("labels") or {})
changed={**labels,"evidenceops_omega_canary":"verified"}
def rpc(ident, labels, ticket, rollback):
    return {"jsonrpc":"2.0","id":ident,"method":"tools/call","params":{
      "name":"omega_execute_change","arguments":{
        "action":"google_api_request","changeTicket":ticket,
        "rollback":rollback,"confirmation":"EXECUTE_SOVEREIGN_PROJECT_CHANGE",
        "payload":{"method":"PATCH","url":url+"?updateMask=labels",
                   "body":{"name":before["name"],"labels":labels},
                   "readbackUrl":url}}}}
(root/"mutation-request.json").write_text(json.dumps(
    rpc("mutation-canary",changed,canary,"restore exact prior topic labels")
),encoding="utf-8")
(root/"rollback-request.json").write_text(json.dumps(
    rpc("rollback-canary",labels,canary+"-ROLLBACK","restore prior labels completed")
),encoding="utf-8")
PY
for phase in mutation rollback; do
  curl --fail --silent "$service_url/mcp" \
    -H "Authorization: Bearer ${mcp_secret}" -H 'Content-Type: application/json' \
    --data-binary "@$canary_dir/${phase}-request.json" \
    > "$canary_dir/${phase}-response.json"
  python3 - "$canary_dir/${phase}-response.json" <<'PY'
import json, pathlib, sys
data=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert "error" not in data, data
assert data["result"]["structuredContent"]["state"] == "MUTATION_AND_PROVIDER_READBACK_COMPLETED"
PY
done

python3 - "$INVENTORY_DIR/management-readback.json" "$canary_dir" "$canary_id" "$receipt_hash" <<'PY'
import hashlib, json, pathlib, sys
out, root, canary, receipt_hash = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3], sys.argv[4]
files=["inventory-response.json","heartbeat-response.json","mutation-response.json","rollback-response.json"]
record={
  "schema":"EVIDENCEOPS-CLOUD-MANAGEMENT-READBACK-1",
  "canary_id":canary,"receipt_hash":receipt_hash,
  "states":["INVENTORY_READBACK_VERIFIED","HEARTBEAT_PUBLISH_PULL_VERIFIED",
            "MUTATION_READBACK_VERIFIED","ROLLBACK_READBACK_VERIFIED"],
  "proof_hashes":{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files},
  "credentials_persisted":False,
}
out.write_text(json.dumps(record,indent=2,sort_keys=True)+"\n",encoding="utf-8")
print(json.dumps(record,indent=2,sort_keys=True))
PY
unset mcp_secret
find "$canary_dir" -depth -delete
MANAGEMENT_CLAIM="PROJECT_OWNER_CLOUD_MANAGEMENT_HEARTBEAT_AND_ROLLBACK_READBACK_VERIFIED"
inventory
echo "VERIFY_COMPLETE_REVIEW_MANIFEST_AT=${INVENTORY_DIR}/manifest.json"
