from __future__ import annotations

import json
from pathlib import Path
import unittest

from federation.bubbles_autopilot_policy import (
    CFBECapabilityCandidate,
    HIGH_CONSEQUENCE,
    NO_EFFECT,
    REVERSIBLE_EXTERNAL,
    REVERSIBLE_INTERNAL,
    AutopilotStep,
    cfbe_rank,
    decide_autopilot,
)


class BubblesAutopilotPolicyTests(unittest.TestCase):
    def test_cfbe_rank_uses_canonical_formula(self) -> None:
        candidate = CFBECapabilityCandidate("C1", 5, 5, 5, 5, 1)
        self.assertEqual(625.0, cfbe_rank(candidate))

    def test_cfbe_rank_rejects_zero_effort(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "CFBE_EXPECTED_EFFORT_POSITIVE_REQUIRED"
        ):
            cfbe_rank(CFBECapabilityCandidate("C1", 5, 5, 5, 5, 0))

    def test_safe_work_continues_without_owner(self) -> None:
        for effect_class in (NO_EFFECT, REVERSIBLE_INTERNAL):
            with self.subTest(effect_class=effect_class):
                decision = decide_autopilot(AutopilotStep("safe", effect_class))
                self.assertEqual("CONTINUE_AUTONOMOUSLY", decision.state)
                self.assertTrue(decision.continue_without_owner)
                self.assertFalse(decision.owner_interrupt_required)

    def test_blocked_lane_with_alternate_reroutes_without_owner(self) -> None:
        decision = decide_autopilot(
            AutopilotStep(
                "blocked",
                REVERSIBLE_INTERNAL,
                blocked=True,
                alternate_route_available=True,
            )
        )
        self.assertEqual("ISOLATE_BLOCKED_LANE_AND_REROUTE", decision.state)
        self.assertTrue(decision.continue_without_owner)
        self.assertFalse(decision.owner_interrupt_required)

    def test_blocked_lane_without_route_escalates(self) -> None:
        decision = decide_autopilot(
            AutopilotStep("blocked", REVERSIBLE_INTERNAL, blocked=True)
        )
        self.assertEqual("ESCALATE_OWNER_NO_EXECUTABLE_ROUTE", decision.state)
        self.assertTrue(decision.owner_interrupt_required)

    def test_reversible_external_requires_authority_and_readback(self) -> None:
        decision = decide_autopilot(
            AutopilotStep(
                "external",
                REVERSIBLE_EXTERNAL,
                authority_proven=True,
                provider_readback_available=True,
                proof_refs=("provider:receipt",),
            )
        )
        self.assertEqual("CONTINUE_EXTERNAL_WITH_READBACK", decision.state)
        self.assertTrue(decision.continue_without_owner)
        self.assertEqual(("provider:receipt",), decision.proof_refs)

    def test_reversible_external_missing_gate_escalates(self) -> None:
        for authority, readback in (
            (False, False),
            (False, True),
            (True, False),
        ):
            with self.subTest(authority=authority, readback=readback):
                decision = decide_autopilot(
                    AutopilotStep(
                        "external",
                        REVERSIBLE_EXTERNAL,
                        authority_proven=authority,
                        provider_readback_available=readback,
                    )
                )
                self.assertEqual("ESCALATE_OWNER_EXTERNAL_GATE", decision.state)
                self.assertTrue(decision.owner_interrupt_required)

    def test_high_consequence_always_escalates(self) -> None:
        decision = decide_autopilot(
            AutopilotStep(
                "danger",
                HIGH_CONSEQUENCE,
                authority_proven=True,
                provider_readback_available=True,
            )
        )
        self.assertEqual("ESCALATE_OWNER_HIGH_CONSEQUENCE", decision.state)
        self.assertFalse(decision.continue_without_owner)

    def test_irreducible_owner_choice_escalates(self) -> None:
        decision = decide_autopilot(
            AutopilotStep(
                "creative-choice",
                NO_EFFECT,
                owner_choice_required=True,
            )
        )
        self.assertEqual("ESCALATE_OWNER_IRREDUCIBLE_CHOICE", decision.state)

    def test_alternate_route_requires_blocked_step(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "AUTOPILOT_ALTERNATE_ROUTE_REQUIRES_BLOCKED_STEP"
        ):
            decide_autopilot(
                AutopilotStep(
                    "bad",
                    REVERSIBLE_INTERNAL,
                    alternate_route_available=True,
                )
            )

    def test_benchmark_files_have_exactly_150_unique_capabilities(self) -> None:
        root = Path(__file__).resolve().parents[1]
        paths = [
            root / "benchmarking/cfbe_omega/bubbles_digital_twin_high_performance_50_v1.json",
            root / "benchmarking/cfbe_omega/bubbles_digital_twin_ai_autopilot_50_v1.json",
            root / "benchmarking/cfbe_omega/bubbles_digital_twin_agi_oriented_50_v1.json",
        ]
        all_rows = []
        for path in paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(50, payload["count"])
            self.assertEqual(50, len(payload["capabilities"]))
            all_rows.extend(payload["capabilities"])
        ids = [row["id"] for row in all_rows]
        names = [row["capability"] for row in all_rows]
        self.assertEqual(150, len(all_rows))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
