import json
from pathlib import Path

from omega_max_runtime import DigitalTwin, DriftSentinel, QueueConsumer


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_operational_canary_end_to_end(tmp_path):
    before = {"generation": 0, "status": "initial"}
    after = {"generation": 1, "status": "operational"}
    target = tmp_path / "runtime/omega-max/state/canary.json"
    write(target, before)
    write(tmp_path / "runtime/omega-max/queue/CANARY.json", {
        "contract_id": "CANARY",
        "action": "SET_JSON",
        "target": "runtime/omega-max/state/canary.json",
        "desired": after,
        "expected_before": before,
        "authority": "A1",
        "reversible": True,
    })
    first = QueueConsumer(tmp_path).process_queue()
    result = json.loads((tmp_path / "runtime/omega-max/results/CANARY.json").read_text())
    assert first["heartbeat"]["runtime_state"] == "OPERATIONAL"
    assert result["status"] == "VERIFIED"
    assert result["semantic_readback"] is True
    assert result["rollback_test"] is True
    assert json.loads(target.read_text()) == after
    second = QueueConsumer(tmp_path).process_queue()
    assert second["results"][0]["effect"] == "EXACTLY_ONCE_SKIP"
    assert (tmp_path / "runtime/omega-max/proofs/PRF-CANARY.json").exists()


def test_digital_twin_and_drift(tmp_path):
    write(tmp_path / "runtime/omega-max/state/desired.json", {"v": 2})
    write(tmp_path / "runtime/omega-max/state/actual.json", {"v": 1})
    assert DigitalTwin(tmp_path).read(
        "runtime/omega-max/state/desired.json",
        "runtime/omega-max/state/actual.json",
    )["drift"]
    assert DriftSentinel(tmp_path).inspect(
        "runtime/omega-max/state/desired.json",
        "runtime/omega-max/state/actual.json",
    )["classification"] == "DRIFT_DETECTED"


def test_unsafe_target_quarantined(tmp_path):
    write(tmp_path / "runtime/omega-max/queue/BAD.json", {
        "contract_id": "BAD",
        "action": "SET_JSON",
        "target": "../unsafe.json",
        "desired": {},
        "expected_before": None,
        "authority": "A1",
        "reversible": True,
    })
    output = QueueConsumer(tmp_path).process_queue()
    assert output["results"][0]["status"] == "QUARANTINED"
    assert output["heartbeat"]["runtime_state"] == "DEGRADED"
