from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/aegis-omega-zero-traffic-v1.yml"
POLICY = ROOT / "governance/github_airlock_policy.json"


def text():
    return WORKFLOW.read_text(encoding="utf-8")


def test_owner_only_exact_dispatch_and_no_source_write():
    value=text()
    assert "github.event.issue.title == '[FO-DISPATCH] AEGIS_OMEGA_ZERO_TRAFFIC_V1'" in value
    assert "github.event.issue.author_association == 'OWNER'" in value
    assert re.search(r"(?m)^\s*contents:\s*read\s*$", value)
    assert not re.search(r"(?m)^\s*contents:\s*write\s*$", value)


def test_private_zero_traffic_and_no_prod_promotion():
    value=text()
    assert "--no-allow-unauthenticated" in value
    assert "--no-traffic" in value
    assert "update-traffic --to-latest" not in value
    assert "--allow-unauthenticated" not in value
    assert "production_traffic_changed" in value
    assert "public_invocation" in value


def test_secret_is_provider_managed_and_payload_not_logged():
    value=text()
    assert "gcloud secrets create" in value
    assert "gcloud secrets versions add" in value
    assert "gcloud secrets add-iam-policy-binding" in value
    assert '--set-secrets "AEGIS_HMAC_SECRET=$HMAC_SECRET:latest"' in value
    assert "gcloud secrets versions access" not in value
    assert "secret_payload_logged':False" in value


def test_cross_revision_persistence_and_rollback_are_material():
    value=text()
    assert "firestore_cross_revision_persistence_verified" in value
    assert "gcloud run revisions delete" in value
    assert "candidate_a_alive_after_rollback" in value
    assert '"$URL/v1/cases/$CASE_ID"' in value


def test_external_actions_are_immutable_and_checkout_credentials_disabled():
    value=text()
    refs=re.findall(r"uses:\s*([^\s#]+)", value)
    assert refs
    for ref in refs:
        if ref.startswith("./"):
            continue
        assert re.search(r"@[0-9a-f]{40}$", ref), ref
    assert "persist-credentials: false" in value
    assert 'docker build --pull --file services/aegis_omega/Dockerfile --tag "$IMAGE" services/aegis_omega' in value


def test_airlock_policy_declares_effects_explicitly():
    policy=json.loads(POLICY.read_text(encoding="utf-8"))
    workflow_path=".github/workflows/aegis-omega-zero-traffic-v1.yml"
    assert workflow_path in policy["active_workflow_allowlist"]
    assert policy["allowed_events"][workflow_path] == ["issues"]
    assert workflow_path in policy["oidc_workflow_allowlist"]
    assert workflow_path in policy["provider_mutation_workflow_allowlist"]
    assert policy["provider_mutation_exact_issue_titles"][workflow_path] == "[FO-DISPATCH] AEGIS_OMEGA_ZERO_TRAFFIC_V1"
    required=set(policy["provider_mutation_required_markers"][workflow_path])
    assert {"gcloud secrets create","gcloud secrets add-iam-policy-binding","provider_mutation_performed"} <= required
    assert "--allow-unauthenticated" in policy["provider_mutation_forbidden_markers"][workflow_path]


def test_assessment_canary_sends_required_request_id():
    value=text()
    assert 'REQUEST_ID="provider-canary-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"' in value
    assert '"request_id":"$REQUEST_ID"' in value
    assert '"events":[' in value
