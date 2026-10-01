from __future__ import annotations

import json
from pathlib import Path
import unittest

from federation.formation_omega_acceleration_binding_v1 import (
    DeadlineState,
    FiveMinuteScientiaGovernor,
    FormationAlphaOmegaCompiler,
    FormationUltimateProgramming,
    TimedWorkUnit,
)

ROOT = Path(__file__).resolve().parents[1]


class FormationOmegaAccelerationBindingV1Tests(unittest.TestCase):
    def test_global_contract_binds_all_three_requested_organs(self) -> None:
        cfg = json.loads(
            (ROOT / "config" / "fuse-formation-omega-acceleration-v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(cfg["applies_to"], "ALL_FUSE_WORKFLOWS")
        self.assertEqual(cfg["five_minute_completion"]["target_total_seconds"], 300)
        self.assertTrue(cfg["five_minute_completion"]["omega_scientia_falsification_required"])
        self.assertEqual(
            cfg["formation_ultimate_programming"]["profile"],
            "FORMATION_ULTIMATE_PROGRAMMING_V1",
        )
        self.assertEqual(
            cfg["formation_alpha_omega_compiler"]["underlying_engine"],
            "AlphaOmegaEngine",
        )
        self.assertFalse(cfg["creates_new_controller"])
        self.assertFalse(cfg["external_effect_authority"])

    def test_scientia_parallelizes_to_five_minute_feasible_plan(self) -> None:
        assessment = FiveMinuteScientiaGovernor(max_parallel_lanes=4).assess(
            mission_id="M-5M-FAST",
            units=(
                TimedWorkUnit(
                    "research",
                    "Gather evidence",
                    180.0,
                    parallelizable=True,
                    max_parallelism=2,
                ),
                TimedWorkUnit(
                    "synthesis",
                    "Synthesize result",
                    60.0,
                    depends_on=("research",),
                ),
            ),
        )
        self.assertEqual(assessment.state, DeadlineState.DEADLINE_FEASIBLE.value)
        self.assertTrue(assessment.eligible_for_five_minute_slo)
        self.assertLessEqual(assessment.forecast_total_seconds, 300.0)
        self.assertGreaterEqual(assessment.required_parallel_lanes, 2)
        self.assertIn("What evidence would falsify", " ".join(assessment.scientia_challenge["questions"]))

    def test_scientia_rejects_unchanged_over_budget_sequential_plan(self) -> None:
        assessment = FiveMinuteScientiaGovernor(max_parallel_lanes=8).assess(
            mission_id="M-5M-SLOW",
            units=(
                TimedWorkUnit(
                    "serial",
                    "Irreducible serial compute",
                    300.0,
                    parallelizable=False,
                ),
            ),
        )
        self.assertEqual(assessment.state, DeadlineState.RECOMPILE_REQUIRED.value)
        self.assertFalse(assessment.eligible_for_five_minute_slo)
        self.assertGreater(assessment.forecast_total_seconds, 300.0)
        self.assertIn("serial", assessment.blocker_units)
        self.assertIn("REESTIMATE_P95_AND_RECOMPILE_BEFORE_EXECUTION", assessment.recompile_actions)

    def test_scientia_does_not_fake_external_wait_guarantee(self) -> None:
        assessment = FiveMinuteScientiaGovernor().assess(
            mission_id="M-WAIT",
            units=(
                TimedWorkUnit(
                    "submit",
                    "Submit request",
                    20.0,
                ),
                TimedWorkUnit(
                    "provider-wait",
                    "Wait for provider event",
                    0.0,
                    depends_on=("submit",),
                    external_wait=True,
                ),
            ),
        )
        self.assertEqual(assessment.state, DeadlineState.EXTERNAL_WAIT.value)
        self.assertFalse(assessment.eligible_for_five_minute_slo)
        self.assertIn("provider-wait", assessment.blocker_units)
        self.assertIn("PERSIST_CHECKPOINT_AND_RESUME_ON_EVENT", assessment.recompile_actions)

    def test_scientia_requires_observed_time_acceptance_and_proof_for_success(self) -> None:
        ok = FiveMinuteScientiaGovernor.verify_observed(
            mission_id="M-OBS",
            observed_wall_seconds=287.0,
            acceptance_complete=True,
            proof_complete=True,
        )
        self.assertEqual(ok.state, DeadlineState.VERIFIED.value)
        late = FiveMinuteScientiaGovernor.verify_observed(
            mission_id="M-OBS-LATE",
            observed_wall_seconds=301.0,
            acceptance_complete=True,
            proof_complete=True,
        )
        self.assertEqual(late.state, DeadlineState.VIOLATED.value)
        unproven = FiveMinuteScientiaGovernor.verify_observed(
            mission_id="M-OBS-PROOF",
            observed_wall_seconds=120.0,
            acceptance_complete=True,
            proof_complete=False,
        )
        self.assertEqual(unproven.state, DeadlineState.VIOLATED.value)

    def test_formation_ultimate_programming_uses_slos_finalization_kernel(self) -> None:
        result = FormationUltimateProgramming().compile(
            mission_id="M-CODE",
            base_revision="abc123",
            objective="Build and verify a repository-aware coding improvement",
            required_capabilities=(
                "repository_intelligence",
                "prepared_workspace",
                "coding_fleet",
                "verification_supercourt",
            ),
            repository_files={
                "app/main.py": "def answer():\n    return 42\n",
                "tests/test_main.py": "from app.main import answer\n",
            },
            toolchain={"python": "3.13"},
            dependencies={"stdlib": "pinned"},
            risk="HIGH",
        )
        self.assertEqual(result.profile, "FORMATION_ULTIMATE_PROGRAMMING_V1")
        self.assertIn("REPOGRAPH_IMPACT_ANALYSIS", result.sophisticated_mechanisms)
        self.assertIn("VERIFICATION_SUPERCOURT", result.sophisticated_mechanisms)
        self.assertFalse(result.external_effect_authorized)
        self.assertFalse(result.blueprint["effect_authority_granted"])

    def test_formation_alpha_omega_uses_canonical_engine_and_full_stage_plan(self) -> None:
        receipt = FormationAlphaOmegaCompiler().compile(
            mission_id="M-AO",
            objective="Build a complete workflow service with API, data, reporting and proof",
            outcomes=("working service", "verification receipt"),
            constraints=("proof before claim",),
            preferred_surfaces=("github", "cloud_run"),
            repo_root=ROOT,
        )
        self.assertEqual(receipt.profile, "FORMATION_ALPHA_OMEGA_COMPILER_V1")
        self.assertEqual(
            receipt.compiler_stages,
            (
                "DISCOVERY",
                "DECOMPOSITION",
                "ARCHITECTURE",
                "BUILD",
                "TEST",
                "DEPLOY",
                "VERIFY",
                "OPERATE",
                "MAINTAIN",
            ),
        )
        self.assertEqual(len(receipt.plan["packets"]), 9)
        self.assertFalse(receipt.local_build_executed)
        self.assertFalse(receipt.provider_deployed)
        self.assertFalse(receipt.operational_verified)


if __name__ == "__main__":
    unittest.main()
