import unittest

from ops.sovara_provider_execution_fabric import (
    CellState,
    ProviderCell,
    ProofReceipt,
    Substrate,
    authority_inheritance_allowed,
    can_promote_to_litellm,
    classify_provider_failure,
    independent_ready_cells,
    next_openrouter_gate,
    provider_cell_matrix,
    select_provider_route,
)
from sovara.creative import (
    AdmissionState,
    BuildStrategy,
    ContentClass,
    CreativeMissionGenome,
    Eligibility,
    ExecutionPlane,
    MatureContext,
    PrivacyClass,
    RightsState,
    RoutePolicy,
    RouteType,
    SkillDomain,
    StudioMode,
    StudioRequest,
    can_deploy,
    compile_studio_plan,
    evaluate_route,
    plan_capability,
    select_route,
)


class ProviderExecutionFabricTests(unittest.TestCase):
    def legacy_cell(self, provider, state=CellState.SOURCE_READY, **kwargs):
        return ProviderCell(provider, state, f"{provider}-only", **kwargs)

    def execution_cell(self, provider, substrate=Substrate.APPS_SCRIPT, **overrides):
        base = dict(
            provider=provider,
            state=CellState.READY,
            authority_scope=f"{provider}-only",
            substrate=substrate,
            credential_reference_ready=True,
            runtime_authorised=True,
            health_ok=True,
            funding_or_quota_ready=True,
            circuit_open=False,
        )
        base.update(overrides)
        return ProviderCell(**base)

    # Original v1 regressions remain intact.
    def test_held_provider_does_not_block_verified_cell(self):
        good = ProviderCell(
            "openrouter",
            CellState.SEMANTIC_VERIFIED,
            "openrouter-only",
            provider_call_proven=True,
            semantic_readback_proven=True,
        )
        held = ProviderCell("gemini", CellState.HELD, "google-only")
        self.assertEqual((good,), independent_ready_cells([held, good]))

    def test_litellm_requires_provider_and_semantic_proof(self):
        source_only = self.legacy_cell("openrouter")
        provider_only = ProviderCell(
            "openrouter", CellState.SEMANTIC_VERIFIED, "openrouter-only",
            provider_call_proven=True, semantic_readback_proven=False,
        )
        proven = ProviderCell(
            "openrouter", CellState.SEMANTIC_VERIFIED, "openrouter-only",
            provider_call_proven=True, semantic_readback_proven=True,
        )
        self.assertFalse(can_promote_to_litellm(source_only))
        self.assertFalse(can_promote_to_litellm(provider_only))
        self.assertTrue(can_promote_to_litellm(proven))

    def test_authority_never_inherits_across_cells(self):
        a = ProviderCell("openrouter", CellState.PROVEN, "openrouter-only", True, True, True)
        b = ProviderCell("gemini", CellState.HELD, "google-only")
        self.assertFalse(authority_inheritance_allowed(a, b))

    def test_openrouter_gate_progression(self):
        self.assertEqual("SOURCE_INSTALL_AND_EXACT_READBACK", next_openrouter_gate(source_installed=False, metadata_verified=False, semantic_verified=False))
        self.assertEqual("PROVIDER_METADATA_READBACK", next_openrouter_gate(source_installed=True, metadata_verified=False, semantic_verified=False))
        self.assertEqual("EXACT_NONCE_SEMANTIC_READBACK", next_openrouter_gate(source_installed=True, metadata_verified=True, semantic_verified=False))
        self.assertEqual("LITELLM_ADMISSION_AND_FORCED_FALLBACK_PROOF", next_openrouter_gate(source_installed=True, metadata_verified=True, semantic_verified=True))

    # v1.1 additive orchestration regressions.
    def test_openrouter_can_proceed_while_google_gemini_is_held(self):
        decision = select_provider_route(
            [
                self.execution_cell("gemini", state=CellState.HELD, circuit_open=True),
                self.execution_cell("openrouter"),
            ],
            preferred_order=["openrouter", "gemini"],
        )
        self.assertEqual("openrouter", decision.selected_provider)
        self.assertIn("gemini", decision.held_providers)

    def test_one_provider_failure_never_sets_global_stall(self):
        failure = classify_provider_failure(provider="gemini", fingerprint="STS_INVALID_TARGET", materially_changed_dependency=False)
        self.assertTrue(failure["circuit_open"])
        self.assertFalse(failure["global_stall"])

    def test_material_dependency_change_reopens_circuit(self):
        failure = classify_provider_failure(provider="gemini", fingerprint="STS_INVALID_TARGET", materially_changed_dependency=True)
        self.assertFalse(failure["circuit_open"])

    def test_receipt_requires_generation_readback_for_new_proof_contract(self):
        receipt = ProofReceipt("openrouter", True, True, True, True, True, True, False)
        self.assertFalse(receipt.promotion_ready)

    def test_litellm_receipt_admission_is_provider_specific(self):
        receipts = {
            "openrouter": ProofReceipt("openrouter", True, True, True, True, True, True, True),
            "gemini": ProofReceipt("gemini", True, True, False, False, False, False, False),
        }
        decision = select_provider_route([self.execution_cell("openrouter")], receipts=receipts)
        self.assertEqual(("openrouter",), decision.litellm_admission)

    def test_health_failure_holds_only_that_provider_when_no_other_substrate_is_ready(self):
        decision = select_provider_route(
            [self.execution_cell("openrouter", health_ok=False), self.execution_cell("deepseek")],
            preferred_order=["openrouter", "deepseek"],
        )
        self.assertEqual("deepseek", decision.selected_provider)
        self.assertIn("openrouter", decision.held_providers)

    def test_replaceable_substrate_keeps_provider_eligible(self):
        decision = select_provider_route(
            [
                self.execution_cell("openrouter", substrate=Substrate.CLOUD_RUN, health_ok=False),
                self.execution_cell("openrouter", substrate=Substrate.APPS_SCRIPT),
            ],
            preferred_order=["openrouter"],
        )
        self.assertEqual("apps_script", decision.selected_substrate)
        self.assertNotIn("openrouter", decision.held_providers)

    def test_no_credential_reference_means_no_execution(self):
        decision = select_provider_route([self.execution_cell("openrouter", credential_reference_ready=False)])
        self.assertIsNone(decision.selected_provider)

    def test_no_quota_or_funding_holds_only_that_provider(self):
        decision = select_provider_route(
            [self.execution_cell("openai", funding_or_quota_ready=False), self.execution_cell("openrouter")],
            preferred_order=["openai", "openrouter"],
        )
        self.assertEqual("openrouter", decision.selected_provider)

    def test_matrix_exposes_no_credential_value(self):
        matrix = provider_cell_matrix([self.execution_cell("openrouter")])
        self.assertTrue(matrix[0]["operational_eligible"])
        self.assertNotIn("credential_value", matrix[0])

    def test_fingerprint_is_deterministic(self):
        cells = [self.execution_cell("openrouter"), self.execution_cell("deepseek")]
        self.assertEqual(
            select_provider_route(cells, preferred_order=["openrouter"]).fingerprint,
            select_provider_route(cells, preferred_order=["openrouter"]).fingerprint,
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
