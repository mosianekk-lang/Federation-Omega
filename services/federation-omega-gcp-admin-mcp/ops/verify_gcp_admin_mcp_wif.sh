#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ID="${PROJECT_ID:-sov-hybrid-suite}"
PROJECT_NUMBER="${PROJECT_NUMBER:-257649435135}"
REGION="${REGION:-africa-south1}"
SERVICE="${SERVICE:-federation-omega-gcp-admin-mcp}"
REPOSITORY="${REPOSITORY:-federation-omega}"
DEPLOYER_SA="${DEPLOYER_SA:-federation-omega-deployer@${PROJECT_ID}.iam.gserviceaccount.com}"
RUNTIME_SA="${RUNTIME_SA:-federation-omega-admin@${PROJECT_ID}.iam.gserviceaccount.com}"
WIF_PROVIDER="${WIF_PROVIDER:-projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-federation-omega/providers/github}"
WIF_POOL_ID="${WIF_POOL_ID:-github-federation-omega}"
WIF_PROVIDER_ID="${WIF_PROVIDER_ID:-github}"
GITHUB_REPOSITORY_ID="${GITHUB_REPOSITORY_ID:-1292795464}"
GITHUB_OWNER_ID="${GITHUB_OWNER_ID:-261966700}"

command -v gcloud >/dev/null
work_dir="$(mktemp -d)"
trap 'rm -rf -- "$work_dir"' EXIT

gcloud projects describe "$PROJECT_ID" --format=json > "$work_dir/project.json"
gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER_ID" \
  --location=global --workload-identity-pool="$WIF_POOL_ID" \
  --project="$PROJECT_NUMBER" --format=json > "$work_dir/provider.json"
gcloud iam service-accounts describe "$DEPLOYER_SA" --project="$PROJECT_ID" --format=json > "$work_dir/deployer.json"
gcloud iam service-accounts describe "$RUNTIME_SA" --project="$PROJECT_ID" --format=json > "$work_dir/runtime.json"
gcloud iam service-accounts get-iam-policy "$DEPLOYER_SA" --project="$PROJECT_ID" --format=json > "$work_dir/deployer-policy.json"
gcloud projects get-iam-policy "$PROJECT_ID" --format=json > "$work_dir/project-policy.json"
gcloud services list --enabled --project="$PROJECT_ID" --format=json > "$work_dir/apis.json"
gcloud artifacts repositories describe "$REPOSITORY" --project="$PROJECT_ID" --location="$REGION" --format=json > "$work_dir/repository.json"
gcloud secrets describe federation-omega-approval-token --project="$PROJECT_ID" --format=json > "$work_dir/approval-secret.json"
gcloud secrets describe federation-omega-allowed-script-ids --project="$PROJECT_ID" --format=json > "$work_dir/script-allowlist-secret.json"

python3 - "$work_dir" "$PROJECT_ID" "$PROJECT_NUMBER" "$REGION" "$SERVICE" "$REPOSITORY" "$DEPLOYER_SA" "$RUNTIME_SA" "$WIF_PROVIDER" "$GITHUB_REPOSITORY_ID" "$GITHUB_OWNER_ID" <<'PY'
import hashlib, json, pathlib, sys

(root, project_id, project_number, region, service, repository, deployer, runtime,
 provider_name, repository_id, owner_id) = sys.argv[1:]
root = pathlib.Path(root)
load = lambda name: json.loads((root / name).read_text(encoding="utf-8"))
project = load("project.json")
provider = load("provider.json")
deployer_policy = load("deployer-policy.json")
project_policy = load("project-policy.json")
apis = load("apis.json")
repo = load("repository.json")
approval_secret = load("approval-secret.json")
script_allowlist_secret = load("script-allowlist-secret.json")

assert project.get("projectId") == project_id, "PROJECT_ID_MISMATCH"
assert str(project.get("projectNumber")) == project_number, "PROJECT_NUMBER_MISMATCH"
assert provider.get("name") == provider_name, "WIF_PROVIDER_NAME_MISMATCH"
assert provider.get("state") == "ACTIVE", "WIF_PROVIDER_NOT_ACTIVE"
mapping = provider.get("attributeMapping") or {}
assert mapping.get("google.subject") == "assertion.sub", "WIF_SUBJECT_MAPPING_MISSING"
assert mapping.get("attribute.repository_id") == "assertion.repository_id", "WIF_REPOSITORY_ID_MAPPING_MISSING"
assert mapping.get("attribute.repository_owner_id") == "assertion.repository_owner_id", "WIF_OWNER_ID_MAPPING_MISSING"
condition = (provider.get("attributeCondition") or "").replace(" ", "")
assert f"assertion.repository_id=='{repository_id}'" in condition or f'assertion.repository_id=="{repository_id}"' in condition, "WIF_NUMERIC_REPOSITORY_CONDITION_MISSING"
assert f"assertion.repository_owner_id=='{owner_id}'" in condition or f'assertion.repository_owner_id=="{owner_id}"' in condition, "WIF_NUMERIC_OWNER_CONDITION_MISSING"

members = [member for binding in deployer_policy.get("bindings") or []
           if binding.get("role") == "roles/iam.workloadIdentityUser"
           for member in binding.get("members") or []]
assert any(repository_id in member for member in members), "WIF_DEPLOYER_BINDING_MISSING"

broad = {"roles/owner", "roles/editor"}
for binding in project_policy.get("bindings") or []:
    members = set(binding.get("members") or [])
    if f"serviceAccount:{deployer}" in members or f"serviceAccount:{runtime}" in members:
        assert binding.get("role") not in broad, "BROAD_IAM_ROLE_PROHIBITED"
    if binding.get("role") == "roles/run.admin" and f"serviceAccount:{deployer}" in members:
        condition = binding.get("condition") or {}
        expression = condition.get("expression") or ""
        assert service in expression, "RUN_ADMIN_SERVICE_CONDITION_MISSING"

enabled = {item.get("config", {}).get("name", "").split("/")[-1] for item in apis}
required = {"run.googleapis.com", "cloudbuild.googleapis.com", "artifactregistry.googleapis.com",
            "iamcredentials.googleapis.com", "logging.googleapis.com", "secretmanager.googleapis.com"}
missing = sorted(required - enabled)
assert not missing, "REQUIRED_APIS_MISSING:" + ",".join(missing)
assert repo.get("name", "").endswith(f"/locations/{region}/repositories/{repository}"), "ARTIFACT_REPOSITORY_MISMATCH"
assert approval_secret.get("state") != "DISABLED", "APPROVAL_SECRET_DISABLED"
assert script_allowlist_secret.get("state") != "DISABLED", "SCRIPT_ALLOWLIST_SECRET_DISABLED"

def digest(name):
    return hashlib.sha256((root / name).read_bytes()).hexdigest()

print(json.dumps({
    "receipt": "FEDOMEGA-GCP-ADMIN-MCP-WIF-VERIFIED",
    "state": "VERIFIED",
    "mutationPerformed": False,
    "projectId": project_id,
    "projectNumber": project_number,
    "region": region,
    "service": service,
    "repository": repository,
    "repositoryId": repository_id,
    "ownerId": owner_id,
    "evidenceHashes": {
        name: digest(name) for name in ["project.json", "provider.json", "deployer-policy.json",
                                       "project-policy.json", "apis.json", "repository.json",
                                       "approval-secret.json", "script-allowlist-secret.json"]
    },
}, sort_keys=True))
PY
