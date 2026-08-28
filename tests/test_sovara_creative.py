import unittest

from sovara_creative import (
    ContentClass,
    CreativeMissionGenome,
    Eligibility,
    MatureContext,
    PrivacyClass,
    RightsState,
    RoutePolicy,
    RouteType,
    evaluate_route,
    select_route,
)


class SovaraCreativeGenesisTests(unittest.TestCase):
    def test_standard_mission_genome_normalizes_modalities(self):
        genome = CreativeMissionGenome.build(
            mission_id=" SC-001 ",
            content_class=ContentClass.BRAND_COMMERCIAL,
            objective="Create campaign package",
            privacy_class=PrivacyClass.INTERNAL,
            required_modalities=["Image", "TEXT", "image"],
            rights_state=RightsState.VERIFIED,
        )
        self.assertEqual(genome.mission_id, "SC-001")
        self.assertEqual(genome.required_modalities, ("image", "text"))

    def test_mature_mission_requires_verified_rights_state(self):
        with self.assertRaises(ValueError):
            CreativeMissionGenome.build(
                mission_id="SC-MATURE-001",
                content_class=ContentClass.MATURE_ADULT_ORIENTED,
                objective="Lawful adult creator production",
                privacy_class=PrivacyClass.SENSITIVE_PERFORMER,
                rights_state=RightsState.PENDING,
            )

    def test_mature_route_fails_closed_without_adult_and_consent_gate(self):
        route = RoutePolicy(
            route_id="self-hosted",
            route_type=RouteType.SELF_HOSTED_GCP,
            privacy_ceiling=PrivacyClass.SENSITIVE_PERFORMER,
            policy_verified=True,
            mature_class_allowed=True,
        )
        result = evaluate_route(
            content_class=ContentClass.MATURE_ADULT_ORIENTED,
            privacy_class=PrivacyClass.SENSITIVE_PERFORMER,
            route=route,
            mature_context=MatureContext(
                all_participants_adults=True,
                consent_verified=False,
            ),
        )
        self.assertEqual(result, Eligibility.INELIGIBLE)

    def test_external_mature_route_requires_current_policy_verification(self):
        route = RoutePolicy(
            route_id="external-frontier",
            route_type=RouteType.OPENROUTER_FCX,
            privacy_ceiling=PrivacyClass.SENSITIVE_PERFORMER,
            policy_verified=False,
            mature_class_allowed=True,
        )
        result = evaluate_route(
            content_class=ContentClass.MATURE_ADULT_ORIENTED,
            privacy_class=PrivacyClass.INTERNAL,
            route=route,
            mature_context=MatureContext(
                all_participants_adults=True,
                consent_verified=True,
            ),
        )
        self.assertEqual(result, Eligibility.POLICY_RECHECK_REQUIRED)

    def test_router_prefers_sovereign_route_before_external_gateway(self):
        candidates = [
            RoutePolicy(
                route_id="openrouter",
                route_type=RouteType.OPENROUTER_FCX,
                privacy_ceiling=PrivacyClass.INTERNAL,
                policy_verified=True,
            ),
            RoutePolicy(
                route_id="sovereign",
                route_type=RouteType.SELF_HOSTED_GCP,
                privacy_ceiling=PrivacyClass.PRIVATE_ASSET,
                policy_verified=True,
            ),
        ]
        decision = select_route(
            content_class=ContentClass.IMAGE,
            privacy_class=PrivacyClass.INTERNAL,
            candidates=candidates,
        )
        self.assertEqual(decision.selected_route_id, "sovereign")
        self.assertTrue(decision.no_paper_continuity_preserved)

    def test_non_generative_digital_route_is_valid_terminal_fallback(self):
        candidates = [
            RoutePolicy(
                route_id="external-unverified",
                route_type=RouteType.OPENROUTER_FCX,
                privacy_ceiling=PrivacyClass.INTERNAL,
                policy_verified=False,
            ),
            RoutePolicy(
                route_id="digital-editor",
                route_type=RouteType.NON_GENERATIVE_DIGITAL,
                privacy_ceiling=PrivacyClass.SENSITIVE_PERFORMER,
                policy_verified=True,
                generation_capable=False,
            ),
        ]
        decision = select_route(
            content_class=ContentClass.IMAGE,
            privacy_class=PrivacyClass.INTERNAL,
            candidates=candidates,
        )
        self.assertEqual(decision.selected_route_id, "digital-editor")
        self.assertEqual(decision.selected_route_type, RouteType.NON_GENERATIVE_DIGITAL.value)

    def test_secret_payloads_are_not_sent_to_generative_routes(self):
        route = RoutePolicy(
            route_id="external",
            route_type=RouteType.OPENROUTER_FCX,
            privacy_ceiling=PrivacyClass.SECRET,
            policy_verified=True,
        )
        result = evaluate_route(
            content_class=ContentClass.EDITORIAL,
            privacy_class=PrivacyClass.SECRET,
            route=route,
        )
        self.assertEqual(result, Eligibility.NON_GENERATIVE_ONLY)


if __name__ == "__main__":
    unittest.main()
