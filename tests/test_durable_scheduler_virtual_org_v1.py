from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from federation.durable_scheduler_virtual_org_v1 import VirtualOrgDurableQueue


def write_mission(root: Path, name: str, **overrides):
    values = {
        "schema": "FUSE_DURABLE_MISSION_V1",
        "mission_id": name,
        "idempotency_key": name + "-idem",
        "task_type": "NO_EFFECT_CANARY",
        "objective": "prove durable execution",
        "schedule_kind": "IMMEDIATE",
        "not_before": "",
        "interval_seconds": 0,
        "authority_class": "A0_INTERNAL",
        "effect_class": "NO_EFFECT",
        "required_capabilities": [],
        "payload": {},
        "max_attempts": 3,
        "source_epoch": "test",
    }
    values.update(overrides)
    q = root / "virtual-org/durable-queue"
    q.mkdir(parents=True, exist_ok=True)
    path = q / f"{name}.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


def test_no_effect_canary_executes_and_persists_receipt(tmp_path):
    write_mission(tmp_path, "m1")
    r = VirtualOrgDurableQueue(tmp_path).tick(now=datetime.now(timezone.utc))
    assert r["processed"][0]["state"] == "SUCCEEDED"
    assert list((tmp_path / "virtual-org/runtime/durable-bus/receipts").glob("*.json"))


def test_terminal_replay_is_suppressed(tmp_path):
    write_mission(tmp_path, "m1")
    q = VirtualOrgDurableQueue(tmp_path)
    now = datetime.now(timezone.utc)
    q.tick(now=now)
    r = q.tick(now=now + timedelta(minutes=1))
    assert r["processed"][0]["state"] == "IDEMPOTENT_TERMINAL_REPLAY_SUPPRESSED"


def test_effectful_mission_is_held(tmp_path):
    write_mission(tmp_path, "m2", effect_class="EXTERNAL_WRITE")
    r = VirtualOrgDurableQueue(tmp_path).tick(now=datetime.now(timezone.utc))
    assert r["processed"][0]["state"] == "HELD"


def test_future_once_is_not_due(tmp_path):
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    write_mission(tmp_path, "m3", schedule_kind="ONCE", not_before=future)
    r = VirtualOrgDurableQueue(tmp_path).tick(now=datetime.now(timezone.utc))
    assert r["processed"][0]["state"] == "NOT_DUE"


def test_interval_reschedules(tmp_path):
    now = datetime.now(timezone.utc)
    write_mission(
        tmp_path, "m4", schedule_kind="INTERVAL",
        not_before=(now - timedelta(seconds=1)).isoformat(),
        interval_seconds=3600,
    )
    q = VirtualOrgDurableQueue(tmp_path)
    first = q.tick(now=now)
    assert first["processed"][0]["state"] == "SUCCEEDED"
    second = q.tick(now=now + timedelta(minutes=10))
    assert second["processed"][0]["state"] == "NOT_DUE"


def test_condition_watch_waits(tmp_path):
    write_mission(
        tmp_path, "m5", schedule_kind="CONDITION_WATCH",
        payload={"condition": {"kind": "FILE_EXISTS", "path": "ready.json"}},
    )
    r = VirtualOrgDurableQueue(tmp_path).tick(now=datetime.now(timezone.utc))
    assert r["processed"][0]["state"] == "WAITING_CONDITION"


def test_condition_watch_executes_after_condition(tmp_path):
    (tmp_path / "ready.json").write_text("{}", encoding="utf-8")
    write_mission(
        tmp_path, "m6", schedule_kind="CONDITION_WATCH",
        payload={"condition": {"kind": "FILE_EXISTS", "path": "ready.json"}},
    )
    r = VirtualOrgDurableQueue(tmp_path).tick(now=datetime.now(timezone.utc))
    assert r["processed"][0]["state"] == "SUCCEEDED"


def test_json_field_condition(tmp_path):
    (tmp_path / "state.json").write_text(json.dumps({"device": {"reachable": True}}), encoding="utf-8")
    write_mission(
        tmp_path, "m7", schedule_kind="CONDITION_WATCH",
        payload={"condition": {
            "kind": "JSON_FIELD_EQUALS",
            "path": "state.json",
            "field": "device.reachable",
            "expected": True,
        }},
    )
    r = VirtualOrgDurableQueue(tmp_path).tick(now=datetime.now(timezone.utc))
    assert r["processed"][0]["state"] == "SUCCEEDED"


def test_condition_path_escape_rejected(tmp_path):
    write_mission(
        tmp_path, "m8", schedule_kind="CONDITION_WATCH",
        payload={"condition": {"kind": "FILE_EXISTS", "path": "../secret"}},
    )
    r = VirtualOrgDurableQueue(tmp_path).tick(now=datetime.now(timezone.utc))
    assert r["processed"][0]["state"] == "REJECTED"


def test_changed_idempotency_parameters_fail_closed(tmp_path):
    path = write_mission(tmp_path, "m9")
    q = VirtualOrgDurableQueue(tmp_path)
    now = datetime.now(timezone.utc)
    q.tick(now=now)
    data = json.loads(path.read_text())
    data["objective"] = "materially changed"
    path.write_text(json.dumps(data), encoding="utf-8")
    r = q.tick(now=now + timedelta(minutes=1))
    assert "IDEMPOTENCY_PARAMETER_MISMATCH" in r["processed"][0]["error"]
