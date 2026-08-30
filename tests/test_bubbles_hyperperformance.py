import unittest

from federation.bubbles_hyperperformance import (
    ContextPressureBudget,
    ContextPressureGovernor,
    ContextPressureObservation,
    MissionCapsuleCompiler,
)


class ContextPressureGovernorTests(unittest.TestCase):
    def test_normal_workload_is_admitted(self):
        governor = ContextPressureGovernor()
        decision = governor.evaluate(
            ContextPressureObservation(
                active_sources=4,
                heavy_sources=1,
                tool_results=8,
                tool_payload_chars=20_000,
                estimated_capsule_chars=8_000,
            )
        )
        self.assertTrue(decision.admitted)
        self.assertEqual(decision.action, "CONTINUE")

    def test_heavy_hydration_fails_small(self):
        governor = ContextPressureGovernor(
            ContextPressureBudget(max_heavy_sources=2, max_tool_payload_chars=50_000)
        )
        decision = governor.evaluate(
            ContextPressureObservation(
                active_sources=5,
                heavy_sources=4,
                tool_results=10,
                tool_payload_chars=75_000,
                estimated_capsule_chars=9_000,
            )
        )
        self.assertFalse(decision.admitted)
        self.assertEqual(decision.action, "CHECKPOINT_COMPACT_REROUTE")
        self.assertIn("HEAVY_SOURCE_BUDGET", decision.reasons)
        self.assertIn("TOOL_PAYLOAD_BUDGET", decision.reasons)


class MissionCapsuleCompilerTests(unittest.TestCase):
    def _state(self):
        return {
            "mission_id": "MISSION-1",
            "objective": "Complete the mission without loading the entire estate.",
            "verified_state": "SHADOW_ACTIVE",
            "source_frontier": "main@abc123",
            "authorities": ["SLOS", "SOVARA"],
            "active_capabilities": [f"CAP-{i}" for i in range(20)],
            "artifacts": ["A", "B"],
            "blockers": ["BLOCK-1"],
            "next_action": "Run the smallest outcome-complete lane.",
            "proof_refs": ["P1", "P2"],
            "freshness": "LEASED",
            "metadata": {"truth_rule": "projection_not_event_truth"},
        }

    def test_capsule_is_bounded(self):
        capsule = MissionCapsuleCompiler(max_items_per_list=5).compile(self._state())
        self.assertEqual(len(capsule.active_capabilities), 5)
        self.assertEqual(capsule.mission_id, "MISSION-1")
        self.assertEqual(capsule.metadata["truth_rule"], "projection_not_event_truth")

    def test_missing_required_field_fails_closed(self):
        state = self._state()
        state.pop("proof_refs")
        with self.assertRaisesRegex(ValueError, "MISSION_CAPSULE_MISSING_FIELDS:proof_refs"):
            MissionCapsuleCompiler().compile(state)


if __name__ == "__main__":
    unittest.main()
