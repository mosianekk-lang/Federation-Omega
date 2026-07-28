import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
