from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "sovara-project-iam-bridge.yml"
REQUEST = ROOT / "governance" / "sovara_project_iam_binding_request_v1.json"
POLICY = ROOT / "governance" / "github_airlock_policy.json"


def test_fkcm_option_a_request_is_exact_and_reversible():
    p = json.loads(REQUEST.read_text(encoding="utf-8"))
    assert p["mode"] == "FKCM_OPTION_A_CANARY"
    assert p["owner_authority"] == "EXPLICIT_CURRENT_CHAT_2026-09-05_FKCM_OPTION_A"
    assert p["required_bindings"] == []
    assert p["topic_id"] == "evidenceops-heartbeat-events"
    assert set(p["temporary_role"]["included_permissions"]) == {
        "pubsub.subscriptions.create",
        "pubsub.topics.attachSubscription",
        "pubsub.subscriptions.get",
        "pubsub.subscriptions.consume",
        "pubsub.subscriptions.delete",
        "pubsub.topics.publish",
    }
    assert p["temporary_role"]["delete_after_canary"] is True
    assert p["temporary_binding_remove_after_canary"] is True
    assert p["existing_subscriptions_may_be_touched"] is False
    assert p["production_traffic_allowed"] is False


def test_bridge_uses_separate_admin_and_deployer_tokens_and_forces_cleanup():
    w = WORKFLOW.read_text(encoding="utf-8")
    assert "ADMIN_ACCESS_TOKEN" in w
    assert "DEPLOYER_ACCESS_TOKEN" in w
    assert "workload_identity_provider" in w
    assert "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com" in w
    assert "FKCM_OPTION_A_CANARY" in w
    assert "iam.roles.create" in w and "iam.roles.delete" in w
    assert "pubsub.subscriptions.create" in w
    assert "pubsub.topics.publish" in w
    assert "finally:" in w
    assert "binding_absent" in w
    assert "role_deleted_or_absent" in w
    assert "permission_state_restored_to_baseline" in w
    assert "existing_subscriptions_touched':False" in w
    assert "production_traffic_changed':False" in w
    assert "billing_configuration_changed':False" in w


def test_airlock_only_adds_oidc_to_existing_iam_bridge():
    p = json.loads(POLICY.read_text(encoding="utf-8"))
    path = ".github/workflows/sovara-project-iam-bridge.yml"
    assert path in p["active_workflow_allowlist"]
    assert path in p["oidc_workflow_allowlist"]
    assert p["allowed_events"][path] == ["push", "workflow_dispatch"]
    assert p["required_push_branches"][path] == ["main"]
