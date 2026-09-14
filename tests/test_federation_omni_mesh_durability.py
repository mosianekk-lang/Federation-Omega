import json

import pytest

from federation_omni_mesh_v1 import DeliveryLedger, MeshEnvelope
from federation_omni_mesh_v1.durability import AtomicJsonFileLedgerStore


def envelope():
    return MeshEnvelope(
        event_id="EV-1",
        event_type="STATE",
        source="SOVARA",
        topic="state.v1",
        idempotency_key="IDEMP-1",
        correlation_id="CORR-1",
        capability_required="SYNC",
        payload={"state": "ACTIVE"},
    )


def ledger_snapshot():
    ledger = DeliveryLedger()
    ledger.admit(envelope())
    ledger.register_targets("EV-1", ["NODE-1"])
    return ledger.snapshot()


def test_atomic_store_round_trip_and_generation(tmp_path):
    store = AtomicJsonFileLedgerStore(tmp_path / "ledger.json")
    first = store.save(ledger_snapshot())
    assert first.generation == 1
    assert store.load() == first

    updated = dict(first.snapshot)
    updated["marker"] = "next"
    second = store.save(
        updated,
        expected_current_sha256=first.snapshot_sha256,
    )
    assert second.generation == 2
    assert second.snapshot["marker"] == "next"


def test_atomic_store_compare_and_set_conflict(tmp_path):
    store = AtomicJsonFileLedgerStore(tmp_path / "ledger.json")
    store.save(ledger_snapshot())
    with pytest.raises(ValueError, match="compare-and-set"):
        store.save(
            {"schema_version": 1},
            expected_current_sha256="0" * 64,
        )


def test_atomic_store_detects_tampering(tmp_path):
    path = tmp_path / "ledger.json"
    store = AtomicJsonFileLedgerStore(path)
    stored = store.save(ledger_snapshot())
    envelope_data = json.loads(path.read_text(encoding="utf-8"))
    envelope_data["snapshot"]["tampered"] = True
    path.write_text(json.dumps(envelope_data), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        store.load()
    assert stored.snapshot_sha256 != "0" * 64
