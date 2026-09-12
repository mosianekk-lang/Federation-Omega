import sqlite3
import tempfile
import unittest
from pathlib import Path

from cfbe_chatperf.ledger_head import FenceRejected, LedgerConflict, LedgerHead


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/"ledger.db"; self.ledger=LedgerHead(self.path)
    def tearDown(self): self.tmp.cleanup()
    def test_append_and_head(self):
        row=self.ledger.append(task_id="t",generation=1,slot="B1",fence=1,payload={"x":1})
        self.assertEqual(self.ledger.head("t")["receipt_hash"],row["receipt_hash"])
    def test_idempotent_replay(self):
        self.ledger.append(task_id="t",generation=1,slot="B1",fence=1,payload={"x":1})
        row=self.ledger.append(task_id="t",generation=1,slot="B1",fence=1,payload={"x":1})
        self.assertTrue(row["idempotent_replay"])
    def test_divergent_duplicate(self):
        self.ledger.append(task_id="t",generation=1,slot="B1",fence=1,payload={"x":1})
        with self.assertRaises(LedgerConflict): self.ledger.append(task_id="t",generation=1,slot="B1",fence=1,payload={"x":2})
    def test_stale_fence(self):
        self.ledger.append(task_id="t",generation=1,slot="B1",fence=2,payload={})
        with self.assertRaises(FenceRejected): self.ledger.append(task_id="t",generation=1,slot="B2",fence=1,payload={})
    def test_stale_generation(self):
        self.ledger.append(task_id="t",generation=2,slot="B1",fence=2,payload={})
        with self.assertRaises(FenceRejected): self.ledger.append(task_id="t",generation=1,slot="B2",fence=3,payload={})
    def test_cas_mismatch(self):
        self.ledger.append(task_id="t",generation=1,slot="B1",fence=1,payload={})
        with self.assertRaises(FenceRejected): self.ledger.append(task_id="t",generation=1,slot="B2",fence=2,payload={},expected_head_hash="wrong")
    def test_chain_verifies(self):
        for i in range(3): self.ledger.append(task_id="t",generation=1,slot=str(i),fence=1,payload={"i":i})
        self.assertEqual(self.ledger.verify_chain("t")["decision"],"VERIFIED")
    def test_tamper_detected(self):
        self.ledger.append(task_id="t",generation=1,slot="B1",fence=1,payload={"x":1})
        with sqlite3.connect(self.path) as db: db.execute("UPDATE receipts SET payload_json='{}'")
        self.assertEqual(self.ledger.verify_chain("t")["decision"],"REJECTED")


if __name__ == "__main__": unittest.main()
