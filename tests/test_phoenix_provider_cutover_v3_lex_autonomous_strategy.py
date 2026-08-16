from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LASE_SRC = ROOT / "systems" / "lex-autonomous-strategy" / "src"
sys.path.insert(0, str(LASE_SRC))

from lex_strategy.engine import LexAutonomousStrategyEngine  # noqa: E402


def base_packet() -> dict:
    return {
        "matter_id": "LASE-CI-1",
        "objective": "Protect the legal position while closing decisive proof gaps",
        "forum": "TEST FORUM",
        "unknowns": [
            {
                "unknown_id": "U1",
                "question": "What does the primary record say?",
                "decision_impact": 1.0,
                "information_gain": 1.0,
                "urgency": 0.8,
                "source_hints": ["Drive"],
            }
        ],
        "sources": [
            {
                "name": "Drive primary corpus",
                "available": True,
                "authority": "PRIMARY",
                "freshness": "CURRENT",
                "cost": 1,
                "latency": 1,
            }
        ],
        "cross_lane_risks": ["waiver"],
        "opponent_capabilities": ["jurisdiction objection"],
    }


class LexAutonomousStrategyAirlockTests(unittest.TestCase):
    def test_access_before_ask_blocks_owner_request_while_route_exists(self):
        with tempfile.TemporaryDirectory() as td:
            run = LexAutonomousStrategyEngine(td).run(base_packet())
            self.assertFalse(run.ask_owner_allowed)
            self.assertTrue(run.access_resolution["routes"])
            self.assertEqual(run.action_queue[0].action_type, "RETRIEVE")
            self.assertFalse(run.action_queue[0].owner_approval_required)

    def test_ten_step_forecast_is_mandatory(self):
        with tempfile.TemporaryDirectory() as td:
            run = LexAutonomousStrategyEngine(td).run(base_packet())
            self.assertEqual(len(run.forecast_tree), 10)
            self.assertEqual([n.step for n in run.forecast_tree], list(range(1, 11)))

    def test_selected_strategy_has_no_external_effect(self):
        with tempfile.TemporaryDirectory() as td:
            run = LexAutonomousStrategyEngine(td).run(base_packet())
            self.assertIsNotNone(run.selected_strategy)
            self.assertFalse(run.selected_strategy.external_effect)
            self.assertFalse(run.truth_boundary["external_effect"])
            self.assertTrue(run.truth_boundary["consequential_actions_owner_reserved"])

    def test_owner_only_unknown_can_be_asked(self):
        packet = base_packet()
        packet["unknowns"] = [{
            "unknown_id": "OWNER-1",
            "question": "Which remedy does the owner prefer?",
            "owner_only": True,
            "decision_impact": 0.5,
            "information_gain": 0.2,
            "urgency": 0.2,
        }]
        with tempfile.TemporaryDirectory() as td:
            run = LexAutonomousStrategyEngine(td).run(packet)
            self.assertTrue(run.ask_owner_allowed)

    def test_missing_non_owner_capability_creates_ao_cra_build(self):
        packet = base_packet()
        packet["sources"] = []
        with tempfile.TemporaryDirectory() as td:
            run = LexAutonomousStrategyEngine(td).run(packet)
            self.assertTrue(run.ask_owner_allowed)
            self.assertTrue(run.ao_cra_builds)
            self.assertEqual(run.ao_cra_builds[0]["classification"], "UNRESOLVED_ENGINEERING_BUILD")

    def test_learning_ledger_is_hash_linked(self):
        with tempfile.TemporaryDirectory() as td:
            engine = LexAutonomousStrategyEngine(td)
            engine.run(base_packet())
            engine.run(base_packet())
            import json
            lines = [json.loads(x) for x in (Path(td) / "learning-ledger.jsonl").read_text().splitlines() if x.strip()]
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0]["previous_hash"], "GENESIS")
            self.assertEqual(lines[1]["previous_hash"], lines[0]["entry_hash"])


if __name__ == "__main__":
    unittest.main()
