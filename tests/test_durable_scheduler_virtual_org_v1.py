from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from federation.durable_scheduler_virtual_org_v1 import VirtualOrgDurableQueue


class VirtualOrgDurableSchedulerV1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_mission(self, name: str, **overrides):
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
        q = self.root / "virtual-org/durable-queue"
        q.mkdir(parents=True, exist_ok=True)
        path = q / f"{name}.json"
        path.write_text(json.dumps(values), encoding="utf-8")
        return path

    def test_no_effect_canary_executes_and_persists_receipt(self):
        self.write_mission("m1")
        r = VirtualOrgDurableQueue(self.root).tick(now=datetime.now(timezone.utc))
        self.assertEqual("SUCCEEDED", r["processed"][0]["state"])
        self.assertTrue(list((self.root / "virtual-org/runtime/durable-bus/receipts").glob("*.json")))

    def test_terminal_replay_is_suppressed(self):
        self.write_mission("m1")
        q = VirtualOrgDurableQueue(self.root)
        now = datetime.now(timezone.utc)
        q.tick(now=now)
        r = q.tick(now=now + timedelta(minutes=1))
        self.assertEqual("IDEMPOTENT_TERMINAL_REPLAY_SUPPRESSED", r["processed"][0]["state"])

    def test_effectful_mission_is_held(self):
        self.write_mission("m2", effect_class="EXTERNAL_WRITE")
        r = VirtualOrgDurableQueue(self.root).tick(now=datetime.now(timezone.utc))
        self.assertEqual("HELD", r["processed"][0]["state"])

    def test_future_once_is_not_due(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        self.write_mission("m3", schedule_kind="ONCE", not_before=future)
        r = VirtualOrgDurableQueue(self.root).tick(now=datetime.now(timezone.utc))
        self.assertEqual("NOT_DUE", r["processed"][0]["state"])

    def test_interval_reschedules(self):
        now = datetime.now(timezone.utc)
        self.write_mission(
            "m4",
            schedule_kind="INTERVAL",
            not_before=(now - timedelta(seconds=1)).isoformat(),
            interval_seconds=3600,
        )
        q = VirtualOrgDurableQueue(self.root)
        first = q.tick(now=now)
        self.assertEqual("SUCCEEDED", first["processed"][0]["state"])
        second = q.tick(now=now + timedelta(minutes=10))
        self.assertEqual("NOT_DUE", second["processed"][0]["state"])

    def test_condition_watch_waits(self):
        self.write_mission(
            "m5",
            schedule_kind="CONDITION_WATCH",
            payload={"condition": {"kind": "FILE_EXISTS", "path": "ready.json"}},
        )
        r = VirtualOrgDurableQueue(self.root).tick(now=datetime.now(timezone.utc))
        self.assertEqual("WAITING_CONDITION", r["processed"][0]["state"])

    def test_condition_watch_executes_after_condition(self):
        (self.root / "ready.json").write_text("{}", encoding="utf-8")
        self.write_mission(
            "m6",
            schedule_kind="CONDITION_WATCH",
            payload={"condition": {"kind": "FILE_EXISTS", "path": "ready.json"}},
        )
        r = VirtualOrgDurableQueue(self.root).tick(now=datetime.now(timezone.utc))
        self.assertEqual("SUCCEEDED", r["processed"][0]["state"])

    def test_json_field_condition(self):
        (self.root / "state.json").write_text(json.dumps({"device": {"reachable": True}}), encoding="utf-8")
        self.write_mission(
            "m7",
            schedule_kind="CONDITION_WATCH",
            payload={"condition": {
                "kind": "JSON_FIELD_EQUALS",
                "path": "state.json",
                "field": "device.reachable",
                "expected": True,
            }},
        )
        r = VirtualOrgDurableQueue(self.root).tick(now=datetime.now(timezone.utc))
        self.assertEqual("SUCCEEDED", r["processed"][0]["state"])

    def test_condition_path_escape_rejected(self):
        self.write_mission(
            "m8",
            schedule_kind="CONDITION_WATCH",
            payload={"condition": {"kind": "FILE_EXISTS", "path": "../secret"}},
        )
        r = VirtualOrgDurableQueue(self.root).tick(now=datetime.now(timezone.utc))
        self.assertEqual("REJECTED", r["processed"][0]["state"])

    def test_changed_idempotency_parameters_fail_closed(self):
        path = self.write_mission("m9")
        q = VirtualOrgDurableQueue(self.root)
        now = datetime.now(timezone.utc)
        q.tick(now=now)
        data = json.loads(path.read_text())
        data["objective"] = "materially changed"
        path.write_text(json.dumps(data), encoding="utf-8")
        r = q.tick(now=now + timedelta(minutes=1))
        self.assertIn("IDEMPOTENCY_PARAMETER_MISMATCH", r["processed"][0]["error"])


if __name__ == "__main__":
    unittest.main()
