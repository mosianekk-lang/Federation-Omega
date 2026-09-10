from __future__ import annotations

import asyncio
import concurrent.futures
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AEGIS_SRC = ROOT / "services" / "aegis_omega" / "src"
if str(AEGIS_SRC) not in sys.path:
    sys.path.insert(0, str(AEGIS_SRC))

from aegis_omega.schemas import Assessment
from aegis_omega.storage import (
    InMemoryCaseStore,
    _legacy_request_id_safe,
    _request_doc_key,
)
from services.fuse_mobile_gateway.aegis_edge_bridge import submit_posture


def _assessment(case_id: str = "case-reliability-1") -> Assessment:
    return Assessment(
        case_id=case_id,
        risk_score=0.2,
        confidence=0.9,
        disposition="observe",
        signals=[],
    )


def _healthy_posture() -> dict:
    return {
        "schema": "AEGIS_EDGE_POSTURE_V1",
        "sample_id": "healthy-001",
        "collected_at": "2026-09-10T13:50:00+02:00",
        "consent": True,
        "platform": "android",
        "os_major": "16",
        "security_patch_month": "2026-09",
        "app_version_major_minor": "1.0",
        "screen_lock_configured": True,
        "developer_mode": False,
        "adb_enabled": False,
        "app_debuggable": False,
        "secure_store_available": True,
        "gateway_https": True,
        "session_present": True,
    }


def test_healthy_posture_is_local_no_change_and_never_calls_provider_sink():
    calls = []

    async def sink(request_id, events):
        calls.append((request_id, events))
        raise AssertionError("healthy posture must not call provider")

    receipt = asyncio.run(
        submit_posture(
            subject="owner",
            device_hash="a" * 64,
            posture=_healthy_posture(),
            sink=sink,
            allow_provider_effect=True,
        )
    )
    assert receipt.status == "NO_CHANGE"
    assert receipt.event_count == 0
    assert receipt.case_id is None
    assert receipt.provider_state_verified is False
    assert receipt.provider_effect_performed is False
    assert calls == []


def test_request_document_key_is_deterministic_provider_safe_and_non_reversible_shape():
    key = _request_doc_key("event:device/path/../__bad__")
    assert key == _request_doc_key("event:device/path/../__bad__")
    assert key.startswith("r_")
    assert len(key) == 66
    assert "/" not in key
    assert key not in {".", ".."}
    assert not (key.startswith("__") and key.endswith("__"))
    assert key != _request_doc_key("event:other")


@pytest.mark.parametrize(
    ("request_id", "expected"),
    [
        ("request-safe", True),
        ("event:colon-is-safe", True),
        ("contains/slash", False),
        (".", False),
        ("..", False),
        ("__reserved__", False),
        ("", False),
    ],
)
def test_legacy_request_key_probe_is_fail_closed(request_id, expected):
    assert _legacy_request_id_safe(request_id) is expected


def test_in_memory_outbox_claim_has_exactly_one_concurrent_winner():
    store = InMemoryCaseStore()
    store.put(_assessment(), [], request_id="request-claim", request_hash="hash-claim")

    def claim(i: int) -> bool:
        return bool(store.claim_outbox_delivery("case-reliability-1", f"worker-{i}", lease_seconds=30)["claimed"])

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(claim, range(8)))
    assert sum(outcomes) == 1
    state = store.outbox_state("case-reliability-1")
    assert state["delivered"] is False
    assert state["claim_owner"].startswith("worker-")


def test_outbox_claim_release_allows_retry_and_owner_mismatch_fails_closed():
    store = InMemoryCaseStore()
    store.put(_assessment(), [], request_id="request-release", request_hash="hash-release")
    first = store.claim_outbox_delivery("case-reliability-1", "worker-a", lease_seconds=30)
    assert first["claimed"] is True
    with pytest.raises(RuntimeError, match="AEGIS_OUTBOX_CLAIM_OWNERSHIP_MISMATCH"):
        store.mark_outbox_delivered("case-reliability-1", "provider-1", claimant_id="worker-b")
    store.release_outbox_claim("case-reliability-1", "worker-a")
    second = store.claim_outbox_delivery("case-reliability-1", "worker-b", lease_seconds=30)
    assert second["claimed"] is True
    store.mark_outbox_delivered("case-reliability-1", "provider-1", claimant_id="worker-b")
    final = store.outbox_state("case-reliability-1")
    assert final["delivered"] is True
    assert final["provider_ref"] == "provider-1"
    assert final["claim_owner"] == ""


def test_source_declares_at_least_once_dedup_and_truthful_remote_provider_effect():
    api = (ROOT / "services/aegis_omega/src/aegis_omega/api.py").read_text(encoding="utf-8")
    bus = (ROOT / "services/aegis_omega/src/aegis_omega/event_bus.py").read_text(encoding="utf-8")
    adapter = (ROOT / "services/fuse_mobile_gateway/aegis_edge_adapter.py").read_text(encoding="utf-8")
    assert "AT_LEAST_ONCE_WITH_DETERMINISTIC_DEDUP" in api
    assert 'idempotency_key":f"aegis.assessment:{assessment.case_id}' in bus
    assert "'provider_effect_performed':True" in adapter
    assert "REMOTE_CASE_STATE_WRITE_AND_READBACK" in adapter
    assert "AEGIS_EDGE_EMPTY_PROVIDER_WRITE_FORBIDDEN" in adapter
