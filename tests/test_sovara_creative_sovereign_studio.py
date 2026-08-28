import unittest

from sovara.creative import (
    AdmissionState,
    BuildStrategy,
    ContentClass,
    ExecutionPlane,
    PrivacyClass,
    SkillDomain,
    StudioMode,
    StudioRequest,
    can_deploy,
    compile_studio_plan,
    plan_capability,
)


class SovaraCreativeSovereignStudioTests(unittest.TestCase):
    def test_sensitive_creator_work_routes_private_first(self):
        plan = compile_studio_plan(
            StudioRequest(
                request_id="SC-PRIVATE-001",
                objective="Create a private production package",
                content_class=ContentClass.IMAGE,
                privacy_class=PrivacyClass.PRIVATE_ASSET,
                mode=StudioMode.DIRECTOR,
            )
        )
        self.assertEqual(plan.primary_plane, ExecutionPlane.PRIVATE_MODEL_CELL)
        self.assertTrue(plan.technical_complexity_hidden_from_owner)
        self.assertFalse(plan.provider_execution_proven)

    def test_secret_material_never_routes_to_generative_plane(self):
        plan = compile_studio_plan(
            StudioRequest(
                request_id="SC-SECRET-001",
                objective="Handle protected configuration",
                content_class=ContentClass.EDITORIAL,
                privacy_class=PrivacyClass.SECRET,
            )
        )
        self.assertEqual(plan.primary_plane, ExecutionPlane.NON_GENERATIVE_PRIVATE)
        self.assertNotIn(ExecutionPlane.MAINSTREAM_FRONTIER, plan.fallback_planes)
        self.assertNotIn(ExecutionPlane.PRIVATE_MODEL_CELL, plan.fallback_planes)

    def test_reference_asset_requires_vault_and_rights_gate(self):
        plan = compile_studio_plan(
            StudioRequest(
                request_id="SC-REF-001",
                objective="Adapt an owner-supplied reference",
                content_class=ContentClass.VIDEO_FILM,
                privacy_class=PrivacyClass.INTERNAL,
                reference_asset_present=True,
            )
        )
        self.assertTrue(plan.requires_private_asset_vault)
        self.assertTrue(plan.requires_rights_gate)

    def test_foundry_composes_existing_federation_power_before_inventing(self):
        candidate = plan_capability(
            capability_id="SC-CAP-001",
            outcome="Build an adaptive media transcoding skill",
            skill_domains=(SkillDomain.MEDIA_PIPELINE, SkillDomain.SOFTWARE_ENGINEERING),
            available_capabilities=(
                "SOVARA_PROVIDER_EXECUTION",
                "SOVARA_PROVIDER_RECOVERY",
                "FORMATION_OMEGA",
                "FAILURE_WIN_V2",
            ),
            provider_effect_required=True,
        )
        self.assertEqual(candidate.strategy, BuildStrategy.COMPOSE)
        self.assertEqual(candidate.admission_state, AdmissionState.IDEA)
        self.assertFalse(can_deploy(candidate))

    def test_foundry_invents_only_when_reuse_is_absent(self):
        candidate = plan_capability(
            capability_id="SC-CAP-002",
            outcome="Create a new bounded specialist skill",
            skill_domains=(SkillDomain.AUTOMATION,),
            available_capabilities=(),
        )
        self.assertEqual(candidate.strategy, BuildStrategy.INVENT)
        self.assertFalse(can_deploy(candidate))


if __name__ == "__main__":
    unittest.main()
