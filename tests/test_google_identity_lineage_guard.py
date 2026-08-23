from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "attachment_lineage",
    ROOT / "federation_consolidation/provider_authority_attachment.py",
)
attachment = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = attachment
spec.loader.exec_module(attachment)


BASE = dict(
    target_project_id="sov-hybrid-suite",
    target_project_number="257649435135",
    oauth_consumer_project_number="516690968552",
    transport_project_number="516699068552",
)


def classify(**overrides):
    state = attachment.GoogleIdentityLineageState(**{**BASE, **overrides})
    return attachment.classify_google_identity_lineage(state)


def test_legacy_transport_does_not_grant_canonical_authority():
    result = classify()
    assert result["status"] == "BLOCKED_OAUTH_CONSUMER_BINDING"
    assert result["target"]["role"] == "CANONICAL_PROVIDER_AUTHORITY_TARGET"
    assert result["transport"]["role"] == "LEGACY_CLOUDOPS_TRANSPORT_ONLY"
    assert result["transport"]["legacy_transport_reuse_only"] is True
    assert result["transport"]["authority_inherited"] is False
    assert result["provider_authority_ready"] is False


def test_target_change_does_not_repair_cloudops_oauth_consumer():
    result = classify(
        consumer_identity_verified=True,
        consumer_api_enabled=False,
    )
    assert result["target"]["canonical_match"] is True
    assert result["oauth_consumer"]["role"] == "CLOUDOPS_OAUTH_CONSUMER_BLOCKED"
    assert result["oauth_consumer"]["binding_ready"] is False
    assert result["invariants"]["target_change_repairs_oauth_consumer"] is False
    assert result["provider_authority_ready"] is False


def test_fogas_consumer_is_classified_separately():
    result = classify(
        oauth_consumer_project_number="979287460558",
        transport_project_number=None,
    )
    assert result["oauth_consumer"]["role"] == "FOGAS_OAUTH_CONSUMER_BLOCKED"
    assert result["transport"]["role"] == "NO_PROJECT_LINEAGE"
    assert result["status"] == "BLOCKED_OAUTH_CONSUMER_BINDING"


def test_public_web_app_approval_default_is_security_hold():
    result = classify(
        consumer_identity_verified=True,
        consumer_api_enabled=True,
        target_authority_verified=True,
        token_issued=True,
        provider_authenticated=True,
        semantic_readback_verified=True,
        deployment_inventory_verified=True,
        active_principal="redacted-principal",
        public_web_app=True,
        approval_default_injected=True,
    )
    assert result["status"] == "SECURITY_HOLD_PUBLIC_APPROVAL_BYPASS"
    assert result["security"]["public_approval_bypass"] is True
    assert result["provider_authority_ready"] is False


def test_distinct_consumer_can_be_ready_only_after_independent_proof():
    result = classify(
        oauth_consumer_project_number="979287460558",
        transport_project_number=None,
        consumer_identity_verified=True,
        consumer_api_enabled=True,
        target_authority_verified=True,
        token_issued=True,
        provider_authenticated=True,
        semantic_readback_verified=True,
        deployment_inventory_verified=True,
        active_principal="redacted-principal",
    )
    assert result["invariants"]["consumer_project_must_equal_target_project"] is False
    assert result["oauth_consumer"]["binding_ready"] is True
    assert result["status"] == "PROVIDER_AUTHORITY_VERIFIED"
    assert result["provider_authority_ready"] is True
    assert result["provider_mutation_authorized_by_this_receipt"] is False


def test_authentication_without_token_proof_fails_closed():
    try:
        classify(provider_authenticated=True)
    except attachment.AttachmentError as error:
        assert "token issuance" in str(error)
        return
    raise AssertionError("authentication without token proof must fail")


def test_unproved_provider_mutation_is_an_incident_state():
    result = classify(provider_mutation_performed=True)
    assert result["status"] == "PROVIDER_MUTATION_WITHOUT_AUTHORITY_PROOF"
    assert result["provider_authority_ready"] is False
    assert (
        result["next_gate"]
        == "CONTAIN_PRESERVE_AND_INDEPENDENTLY_READ_BACK"
    )
