from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from services.aegis_omega.src.aegis_omega.storage import (
    IdempotencyCollision,
    InMemoryCaseStore,
    _legacy_request_doc_key_if_safe,
    _request_doc_key,
)
from services.fuse_mobile_gateway.aegis_edge_bridge import submit_posture

ROOT = Path(__file__).resolve().parents[1]


class _FakeAssessment:
    def __init__(self, case_id: str = "case-001"):
        self.case_id = case_id

    def model_dump(self, mode="json"):
        return {"case_id": self.case_id, "risk_score": 0.1, "confidence": 0.9, "disposition": "monitor"}


def test_firestore_request_key_is_provider_safe_and_deterministic():
    raw = "event:unsafe/request/../__name__"
    key = _request_doc_key(raw)
    assert re.fullmatch(r"[0-9a-f]{64}", key)
    assert key == _request_doc_key(raw)
    assert "/" not in key
    assert _legacy_request_doc_key_if_safe(raw) is None
    assert _legacy_request_doc_key_if_safe(".") is None
    assert _legacy_request_doc_key_if_safe("..") is None
    assert _legacy_request_doc_key_if_safe("__reserved__") is None
    assert _legacy_request_doc_key_if_safe("legacy-safe-id") == "legacy-safe-id"


def test_inmemory_idempotency_and_single_winner_outbox_claim():
    store = InMemoryCaseStore()
    assessment = _FakeAssessment()
    stored = store.put(assessment, [], request_id="request-001", request_hash="hash-a")
    assert store.resolve_request("request-001", "hash-a") == stored
    with pytest.raises(IdempotencyCollision, match="AEGIS_IDEMPOTENCY_KEY_COLLISION"):
        store.resolve_request("request-001", "hash-b")

    assert store.claim_outbox(assessment.case_id, "publisher-a", ttl_seconds=60) is True
    assert store.claim_outbox(assessment.case_id, "publisher-b", ttl_seconds=60) is False
    store.release_outbox_claim(assessment.case_id, "publisher-a")
    assert store.claim_outbox(assessment.case_id, "publisher-b", ttl_seconds=60) is True
    store.mark_outbox_delivered(assessment.case_id, "pubsub-message-1", claimant="publisher-b")
    state = store.outbox_state(assessment.case_id)
    assert state["delivered"] is True
    assert state["provider_ref"] == "pubsub-message-1"
    assert state["claim_owner"] == ""
    assert store.claim_outbox(assessment.case_id, "publisher-c", ttl_seconds=60) is False


def test_outbox_claim_owner_mismatch_fails_closed():
    store = InMemoryCaseStore()
    assessment = _FakeAssessment("case-claim")
    store.put(assessment, [], request_id="request-claim", request_hash="hash-c")
    assert store.claim_outbox(assessment.case_id, "publisher-a", ttl_seconds=60)
    with pytest.raises(RuntimeError, match="AEGIS_OUTBOX_CLAIM_MISMATCH"):
        store.mark_outbox_delivered(assessment.case_id, "provider-ref", claimant="publisher-b")


def test_healthy_posture_is_no_change_and_never_calls_provider_sink():
    calls = []

    async def sink(request_id, events):
        calls.append((request_id, events))
        return {
            "request_id": request_id,
            "status": "ACCEPTED",
            "case_id": "unexpected",
            "provider_state_verified": True,
            "provider_effect_performed": True,
        }

    posture = {
        "schema": "AEGIS_EDGE_POSTURE_V1",
        "sample_id": "healthy-001",
        "collected_at": "2026-09-10T12:00:00+00:00",
        "consent": True,
        "platform": "android",
        "os_major": "16",
        "screen_lock_configured": True,
        "developer_mode": False,
        "adb_enabled": False,
        "app_debuggable": False,
        "secure_store_available": True,
        "gateway_https": True,
        "session_present": True,
    }
    receipt = asyncio.run(
        submit_posture(
            subject="owner-session",
            device_hash="a" * 64,
            posture=posture,
            sink=sink,
            allow_provider_effect=True,
        )
    )
    assert calls == []
    assert receipt.status == "NO_CHANGE"
    assert receipt.event_count == 0
    assert receipt.case_id is None
    assert receipt.provider_state_verified is False
    assert receipt.provider_effect_performed is False


def test_provider_state_write_is_not_mislabeled_no_effect():
    adapter = (ROOT / "services/fuse_mobile_gateway/aegis_edge_adapter.py").read_text(encoding="utf-8")
    assert '"provider_effect_performed": True' in adapter
    assert '"provider_effect_performed": False' not in adapter


def test_api_uses_claim_publish_mark_with_retry_safe_failure():
    api = (ROOT / "services/aegis_omega/src/aegis_omega/api.py").read_text(encoding="utf-8")
    claim = api.index("store.claim_outbox")
    publish = api.index("event_bus.publish_assessment")
    mark = api.index("store.mark_outbox_delivered")
    assert claim < publish < mark
    assert "store.release_outbox_claim" in api
    assert "AEGIS_OUTBOX_DELIVERY_IN_PROGRESS" in api
    assert "at-least-once-with-deterministic-dedup" in api


def test_pubsub_payload_carries_deterministic_idempotency_key():
    event_bus = (ROOT / "services/aegis_omega/src/aegis_omega/event_bus.py").read_text(encoding="utf-8")
    assert '"idempotency_key":f"aegis.assessment:{assessment.case_id}"' in event_bus
