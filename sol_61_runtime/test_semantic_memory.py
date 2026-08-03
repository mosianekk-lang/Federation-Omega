from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone

from semantic_memory import MemoryRecord, SemanticMemory


class SemanticMemoryTests(unittest.TestCase):
    def test_supersession_contradictions_budget_and_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            memory = SemanticMemory(temp)
            observed = datetime.fromtimestamp(1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            memory.add(MemoryRecord("m1", "cloud state", "cloud run declared", "reg://1", observed, True, 0.8, token_cost=3, workstreams=("ws",)))
            memory.add(MemoryRecord("m2", "cloud state", "cloud run not live", "proof://2", observed, True, 0.99, priority=95, supersedes=("m1",), token_cost=4, workstreams=("ws",)))
            memory.add(MemoryRecord("m3", "authority", "apps script authority verified", "claim://3", observed, False, 0.4, contradicts=("m4",), token_cost=2, workstreams=("ws",)))
            memory.add(MemoryRecord("m4", "authority", "apps script owner consent required", "proof://4", observed, True, 0.98, contradicts=("m3",), token_cost=2, workstreams=("ws",)))

            context = memory.rebuild_context({
                "query": "cloud authority apps script",
                "now_epoch": 1100,
                "token_budget": 6,
                "workstream_id": "ws",
            })
            ids = [row["memory_id"] for row in context["selected"]]
            self.assertNotIn("m1", ids)
            self.assertLessEqual(context["tokens_used"], 6)
            self.assertIn("m1", context["superseded_excluded"])
            self.assertTrue(context["contradictions"])
            self.assertTrue(memory.verify_lineage())

            restarted = SemanticMemory(temp)
            self.assertEqual(len(restarted.records), 4)
            self.assertTrue(restarted.verify_lineage())

    def test_freshness_decay_and_verified_ranking(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            memory = SemanticMemory(temp)
            old = datetime.fromtimestamp(0, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            new = datetime.fromtimestamp(990, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            memory.add(MemoryRecord("old", "runtime", "runtime healthy", "old://1", old, False, 0.5, token_cost=1))
            memory.add(MemoryRecord("new", "runtime", "runtime healthy verified", "new://1", new, True, 0.99, token_cost=1))
            result = memory.retrieve("runtime healthy", now_epoch=1000, token_budget=2, half_life_seconds=100)
            self.assertEqual(result["selected"][0]["memory_id"], "new")
            self.assertGreater(result["selected"][0]["retrieval_score"], result["selected"][1]["retrieval_score"])


if __name__ == "__main__":
    unittest.main()
