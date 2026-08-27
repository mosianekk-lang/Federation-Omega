import json
import tempfile
import unittest
from pathlib import Path

from realityguard.faultbook import FaultBookManager, FaultRecord, verify_jsonl_chain


def event(event_id, previous, content):
    import hashlib
    payload = {"event_id": event_id, "content": content}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256((previous + "\n" + canonical).encode()).hexdigest()
    return {**payload, "prev_hash": previous, "event_hash": digest}


class FaultBookManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.manager = FaultBookManager(self.root / "registry.json")

    def tearDown(self):
        self.tmp.cleanup()

    def ledger(self):
        first = event("E1", "GENESIS", "fault")
        second = event("E2", first["event_hash"], "finding")
        path = self.root / "fault.jsonl"
        path.write_text("\n".join(json.dumps(item) for item in (first, second)) + "\n")
        return path, second["event_hash"]

    def metadata(self):
        return dict(fault_id="FAULT-1", title="Authorization continuity", scope="chatgpt", status="SYSTEMIC_OPEN", source_kind="HASH_CHAINED_JSONL", owner_authority="Kim Kagiso Mosiane", truth_state="PARTIAL_CHECKPOINTED", lifecycle_state="REGISTERED", registered_at="2026-08-27T02:45:00+02:00", fault_classes=("AUTHORIZATION_CONSERVATION_FAILURE",), open_requirements=("NT-01",))

    def test_registers_verified_chain_and_queries(self):
        path, head = self.ledger()
        result = self.manager.register_jsonl(path, **self.metadata())
        self.assertEqual(result["decision"], "REGISTERED")
        self.assertEqual(result["record"]["chain_head"], head)
        self.assertEqual(len(self.manager.query(scope="chatgpt")), 1)
        self.assertEqual(self.manager.state()["provider_binding"], "ADAPTER_REQUIRED")

    def test_idempotent_duplicate_does_not_create_second_fault(self):
        path, _ = self.ledger()
        self.manager.register_jsonl(path, **self.metadata())
        result = self.manager.register_jsonl(path, **self.metadata())
        self.assertEqual(result["decision"], "DEDUPLICATED")
        self.assertEqual(self.manager.state()["registered_fault_books"], 1)

    def test_rejects_tampered_chain(self):
        path, _ = self.ledger()
        events = [json.loads(line) for line in path.read_text().splitlines()]
        events[1]["content"] = "changed"
        with self.assertRaisesRegex(ValueError, "CHAIN_HASH_MISMATCH"):
            verify_jsonl_chain(json.dumps(item) for item in events)

    def test_rejects_false_closure(self):
        record = FaultRecord(source_ref="x", source_sha256="a" * 64, event_count=1, chain_head="b" * 64, **{**self.metadata(), "status": "PROVEN_CLOSED"})
        with self.assertRaisesRegex(ValueError, "FALSE_FAULT_CLOSURE"):
            self.manager.register(record)

    def test_rejects_equal_length_fork(self):
        path, _ = self.ledger()
        self.manager.register_jsonl(path, **self.metadata())
        data = self.manager.load()
        prior = data["faults"][0]
        fork = FaultRecord(**{**prior, "source_sha256": "c" * 64, "chain_head": "d" * 64, "fault_classes": tuple(prior["fault_classes"]), "open_requirements": tuple(prior["open_requirements"]), "supersedes": tuple(prior["supersedes"])})
        with self.assertRaisesRegex(ValueError, "FAULT_BRANCH_MERGE_REQUIRED"):
            self.manager.register(fork)


if __name__ == "__main__":
    unittest.main()
