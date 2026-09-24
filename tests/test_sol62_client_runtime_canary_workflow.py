from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "sol62-client-runtime-canary.yml"
POLICY = ROOT / "governance" / "github_airlock_policy.json"
REL = ".github/workflows/sol62-client-runtime-canary.yml"
TITLE = "[FO-DISPATCH] SOL62_CLIENT_RUNTIME_CANARY_V1"

def test_sol62_canary_is_exact_owner_gated_provider_mutation():
    text = WORKFLOW.read_text(encoding="utf-8")
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert REL in policy["active_workflow_allowlist"]
    assert policy["allowed_events"][REL] == ["issues"]
    assert REL in policy["oidc_workflow_allowlist"]
    assert REL in policy["provider_mutation_workflow_allowlist"]
    assert REL in policy["execution_quarantine"]["keep_active"]
    assert policy["provider_mutation_exact_issue_titles"][REL] == TITLE
    assert TITLE in text
    assert "github.event.issue.author_association == 'OWNER'" in text
    assert "contents: read" in text
    assert "id-token: write" in text
    assert "persist-credentials: false" in text

def test_sol62_canary_is_isolated_authenticated_and_nonproduction():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "SERVICE: fuse-sol62-client-canary" in text
    assert "--min 0" in text and "--max 1" in text
    assert "--allow-unauthenticated" not in text
    assert "update-traffic" not in text
    assert "get-iam-policy" in text
    assert "print-identity-token" in text
    assert "PRODUCTION_TRAFFIC_CHANGED: 'false'" in text
    assert "production_traffic_changed" in text
    assert "PUBLIC_INVOCATION=false" in text
    assert "provider_mutation_performed" in text

def test_sol62_canary_proves_meta_intelligence_semantics_before_and_after_deploy():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "services/sol62_client_runtime/Dockerfile" in text
    assert "LOCAL_SEMANTIC_CANARY=PASS" in text
    assert "PROVIDER_SEMANTIC_CANARY=PASS" in text
    assert "sovereign_meta_intelligence" in text
    assert "Kim Kagiso Mosiane" in text
    assert "auto_repair_control" in text
    assert "auto_protect_control" in text
    assert "untrusted_content_has_instruction_authority" in text
    assert "provider_authority_created" in text
    assert "chatgpt_ui_required" in text
