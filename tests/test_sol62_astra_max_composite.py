from __future__ import annotations

import unittest
from pathlib import Path

from services.sol62_client_runtime.astra_max_composite import (
    HARD_BOUNDARIES,
    compile_astra_max_profile,
    runtime_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class Sol62AstraMaxCompositeTests(unittest.TestCase):
    def test_complex_work_uses_max_or_xhigh_reasoning(self):
        profile = compile_astra_max_profile(
            objective=(
                "Execute a complex multi-step research, browser, coding and professional "
                "artifact mission across several systems with proof and recovery."
            ),
            constraints=("CURRENT_EVIDENCE", "PROOF_REQUIRED", "MULTI_PROVIDER"),
            risk_class="HIGH",
            consequential=False,
            astra_provider_available=True,
            code_execution_available=True,
            browser_control_available=True,
        )
        self.assertIn(profile.reasoning_effort, {"xhigh", "max"})
        self.assertGreaterEqual(profile.max_parallel_lanes, 6)
        self.assertEqual(profile.capability_mode, "MAXIMUM_AUTHORIZED_CAPABILITY")
        self.assertTrue(profile.no_artificial_local_throttles)
        self.assertTrue(profile.no_artificial_goal_dilution)

    def test_consequential_work_forces_max_reasoning_but_reduces_parallelism(self):
        profile = compile_astra_max_profile(
            objective="Make a consequential browser-mediated decision with exact authority.",
            risk_class="CRITICAL",
            consequential=True,
            astra_provider_available=True,
            code_execution_available=True,
            browser_control_available=True,
        )
        self.assertEqual(profile.reasoning_effort, "max")
        self.assertLessEqual(profile.max_parallel_lanes, 3)
        self.assertIn("AUTHORIZATION", profile.hard_boundaries)
        self.assertFalse(profile.authority_expansion)
        self.assertFalse(profile.safety_bypass)

    def test_code_first_computer_use_when_available(self):
        profile = compile_astra_max_profile(
            objective="Operate browser and desktop applications and verify the final state.",
            code_execution_available=True,
            browser_control_available=True,
        )
        self.assertEqual(profile.computer_use_strategy[0], "CODE_EXECUTION_FIRST")
        self.assertIn("FUSE_BROWSER_CONTROL_PLANE", profile.computer_use_strategy)
        self.assertIn("SEMANTIC_READBACK_REQUIRED", profile.computer_use_strategy)

    def test_provider_unavailable_keeps_astra_mechanisms_via_fallback(self):
        profile = compile_astra_max_profile(
            objective="Perform deep research and produce a polished report.",
            astra_provider_available=False,
        )
        self.assertFalse(profile.astra_provider_preferred_when_qualified)
        self.assertTrue(profile.provider_neutral_fallback)
        self.assertNotIn("OPENAI_GPT_6_ASTRA", profile.preferred_surfaces)

    def test_actual_astra_route_is_preferred_only_when_marked_available(self):
        profile = compile_astra_max_profile(
            objective="Use the strongest available model for end-to-end work.",
            preferred_surfaces=("FUSE_LOCAL",),
            astra_provider_available=True,
        )
        self.assertTrue(profile.astra_provider_preferred_when_qualified)
        self.assertEqual(profile.preferred_surfaces[0], "OPENAI_GPT_6_ASTRA")

    def test_runtime_contract_preserves_hard_boundaries(self):
        contract = runtime_contract()
        self.assertEqual(contract["reasoning_effort_ceiling"], "max")
        self.assertEqual(contract["computer_use_default_for_astra"], "CODE_EXECUTION_FIRST")
        self.assertFalse(contract["authority_expansion"])
        self.assertFalse(contract["safety_bypass"])
        self.assertEqual(set(contract["hard_boundaries"]), set(HARD_BOUNDARIES))
        self.assertEqual(contract["model_identity_claim"], "NONE")

    def test_formation_binding_embeds_astra_profile_without_model_identity_claim(self):
        text = (
            ROOT
            / "services"
            / "sol62_client_runtime"
            / "alpha_omega_formation_binding.py"
        ).read_text(encoding="utf-8")
        self.assertIn("compile_astra_max_profile", text)
        self.assertIn('foundry_dict["astra_max_profile"]', text)
        self.assertIn('"astra_model_runtime_verified": False', text)
        self.assertIn('"astra_provider_authority_granted": False', text)


if __name__ == "__main__":
    unittest.main()
