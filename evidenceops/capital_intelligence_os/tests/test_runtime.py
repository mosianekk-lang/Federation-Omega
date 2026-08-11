import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from superior_logic.ecasp import CorpusObject, CorpusStatus, ECASPRequest
from superior_logic.runtime import DONE_PREDICATES, SuperiorLogicRuntime


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = SuperiorLogicRuntime(Path(self.tmp.name) / "runtime.db")

    def tearDown(self):
        self.runtime.close()
        self.tmp.cleanup()

    def test_mission_and_event_chain(self):
        mission_id = self.runtime.create_mission("Kim Kagiso Mosiane", "Deploy and verify")
        self.assertTrue(mission_id)
        self.assertTrue(self.runtime.verify_event_chain())
        self.assertEqual(1, self.runtime.snapshot()["mission_count"])

    def test_completion_requires_every_predicate(self):
        predicates = {name: True for name in DONE_PREDICATES}
        predicates["source_readback_verified"] = False
        done, missing = self.runtime.derive_done(predicates)
        self.assertFalse(done)
        self.assertEqual(["source_readback_verified"], missing)

    def test_complete_predicate_set_closes(self):
        predicates = {name: True for name in DONE_PREDICATES}
        done, missing = self.runtime.derive_done(predicates)
        self.assertTrue(done)
        self.assertEqual([], missing)

    def test_ecasp_evaluation_is_hash_chained(self):
        result = self.runtime.evaluate_corpus_selection(
            ECASPRequest(
                instruction="Do a full sweep",
                intended_claim="final best stack",
                expected_object_count=1,
                objects=(CorpusObject(object_id="a", indexed=True),),
            )
        )
        self.assertEqual(CorpusStatus.INVENTORY_COMPLETE_ANALYSIS_INCOMPLETE, result.status)
        self.assertTrue(self.runtime.verify_event_chain())
        self.assertEqual(1, self.runtime.snapshot()["event_count"])

    def test_concurrent_event_writes_preserve_hash_chain(self):
        def write_event(index: int) -> None:
            self.runtime.append_event("CONCURRENT_TEST", {"index": index})

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(write_event, range(40)))

        state = self.runtime.snapshot()
        self.assertEqual(40, state["event_count"])
        self.assertTrue(state["event_chain_valid"])


if __name__ == "__main__":
    unittest.main()
