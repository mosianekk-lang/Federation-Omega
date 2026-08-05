from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "attachment",
    ROOT / "federation_consolidation/provider_authority_attachment.py",
)
attachment = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = attachment
spec.loader.exec_module(attachment)


BASE = dict(
    active_account="mosianekk@gmail.com",
    expected_account="mosianekk@gmail.com",
    project_id="sov-hybrid-suite",
    expected_project_id="sov-hybrid-suite",
    project_number="257649435135",
    expected_project_number="257649435135",
    service_usage_enabled=True,
    secret_manager_enabled=True,
    cloud_run_enabled=True,
    cloud_build_enabled=True,
    metadata_probe_passed=True,
    sealed_packet_sha256="a" * 64,
    sealed_packet_verified=True,
    openai_existing_key_management_available=False,
)


def test_plan_ready_for_read_only_handle():
    plan = attachment.build_plan(attachment.AttachmentState(**BASE))
    assert plan["provider_read_ready"] is True
    assert plan["next_gate"] == "ISSUE_READ_ONLY_HANDLE"
    assert plan["provider_mutation_performed"] is False


def test_identity_mismatch_fails():
    state = attachment.AttachmentState(
        **{**BASE, "active_account": "other@example.com"}
    )
    try:
        attachment.build_plan(state)
    except attachment.AttachmentError:
        return
    raise AssertionError("identity mismatch must fail")


def test_metadata_receipt_rejects_secret_payload():
    receipt = {
        "active_account": "mosianekk@gmail.com",
        "project_id": "sov-hybrid-suite",
        "secret_metadata": [{}, {}],
        "cloud_run_metadata": {},
        "secret_payload_accessed": False,
        "raw_environment_recorded": False,
        "provider_mutation_performed": False,
        "access_token": "not-allowed",
    }
    try:
        attachment.verify_metadata_receipt(receipt)
    except attachment.AttachmentError:
        return
    raise AssertionError("secret payload field must fail")


def test_handle_lifetime_is_capped():
    now = datetime(2026, 8, 5, tzinfo=timezone.utc)
    handle = attachment.issue_read_only_handle(
        capability_id="GCP_METADATA",
        requester_id="federation-chat",
        mission_id="mission-1",
        provider_reference="sov-hybrid-suite",
        metadata_receipt_sha256="b" * 64,
        lifetime_seconds=600,
        now=now,
    )
    assert handle["secret_exposed"] is False
    assert handle["provider_mutation_performed"] is False
    assert handle["revocation_state"] == "ACTIVE"
    try:
        attachment.issue_read_only_handle(
            capability_id="GCP_METADATA",
            requester_id="federation-chat",
            mission_id="mission-1",
            provider_reference="sov-hybrid-suite",
            metadata_receipt_sha256="b" * 64,
            lifetime_seconds=601,
            now=now,
        )
    except attachment.AttachmentError:
        return
    raise AssertionError("overlong handle must fail")


def test_revoke_handle():
    now = datetime(2026, 8, 5, tzinfo=timezone.utc)
    handle = attachment.issue_read_only_handle(
        capability_id="GCP_METADATA",
        requester_id="federation-chat",
        mission_id="mission-1",
        provider_reference="sov-hybrid-suite",
        metadata_receipt_sha256="b" * 64,
        lifetime_seconds=60,
        now=now,
    )
    revoked = attachment.revoke_handle(handle, reason="probe complete", now=now)
    assert revoked["revocation_state"] == "REVOKED"
    assert revoked["status"] == "REVOKED"


def test_gcp_scripts_never_access_secret_payloads():
    probe = (ROOT / "tools/provider_metadata_probe.py").read_text()
    shell = (ROOT / "tools/gcp_provider_authority_attach.sh").read_text()
    assert "versions access" not in probe
    assert "versions access" not in shell
    assert "roles/owner" not in shell
    assert "roles/editor" not in shell
