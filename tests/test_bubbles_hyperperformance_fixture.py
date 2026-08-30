import json
import unittest
from pathlib import Path

from federation.bubbles_hyperperformance import MissionCapsuleCompiler


class BubblesHyperperformanceFixtureTests(unittest.TestCase):
    def test_compact_fixture_compiles_without_full_estate(self):
        fixture = Path("tests/fixtures/bubbles_hyperperformance_mission_state.json")
        state = json.loads(fixture.read_text(encoding="utf-8"))
        capsule = MissionCapsuleCompiler().compile(state)
        payload = json.dumps(capsule.as_mapping(), sort_keys=True)
        self.assertLess(len(payload), 24_000)
        self.assertEqual(capsule.mission_id, "MISSION-BUBBLES-HYPERPERFORMANCE-CANARY")
        self.assertNotIn("full historical transcript", payload.lower())


if __name__ == "__main__":
    unittest.main()
