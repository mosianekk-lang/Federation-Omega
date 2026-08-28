import io
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
    AmbitionClass,
    BenchmarkDimension,
    BuildStrategy,
    ContentClass,
    CreativeMissionGenome,
    Eligibility,
    EvolutionEvidence,
    ExecutionPlane,
    FrontierObservation,
    MatureContext,
    MetaEvolutionState,
    MetricDirection,
    MetricObservation,
    MissionEconomics,
    PrivacyClass,
    RightsState,
    RoutePolicy,
    RouteType,
    ScientistHypothesis,
    SkillDomain,
    SovaraDimensionState,
    StudioMode,
    StudioRequest,
    ValueClass,
    ValueEvidence,
    ValueGateState,
    ValueMetricSpec,
    build_ten_x_target,
    calculate_frontier_gaps,
    can_deploy,
    compare_value_metrics,
    compile_best_of_breed_frontier,
    compile_studio_plan,
    default_production_value_specs,
    economics_snapshot,
    evaluate_meta_evolution,
    evaluate_route,
    evaluate_value_gate,
    plan_capability,
    preregister_omega_scientist_experiment,
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


class SovaraCreativeOpenRouterAdmissionTests(unittest.TestCase):
    def test_openrouter_policy_adapter_regressions_are_admission_bound(self):
        suite = unittest.defaultTestLoader.loadTestsFromName(
            "tests.test_sovara_creative_openrouter_adapter"
        )
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)

        self.assertGreaterEqual(result.testsRun, 26)
        self.assertTrue(result.wasSuccessful(), stream.getvalue())


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


class SovaraCreativeCFBEMetaEvolutionTests(unittest.TestCase):
    def test_composite_frontier_uses_best_fresh_suite_not_average(self):
        frontier = compile_best_of_breed_frontier(
            [
                FrontierObservation(
                    "F-1", "suite-a", BenchmarkDimension.DIRECTOR_EXPERIENCE,
                    3.0, "https://example.invalid/a", "2026-08-28", True,
                ),
                FrontierObservation(
                    "F-2", "suite-b", BenchmarkDimension.DIRECTOR_EXPERIENCE,
                    5.0, "https://example.invalid/b", "2026-08-28", True,
                ),
                FrontierObservation(
                    "F-3", "stale-suite", BenchmarkDimension.DIRECTOR_EXPERIENCE,
                    5.0, "https://example.invalid/stale", "2025-01-01", False,
                ),
            ]
        )
        self.assertEqual(len(frontier), 1)
        self.assertEqual(frontier[0].frontier_score, 5.0)
        self.assertEqual(frontier[0].suite_ids, ("suite-b",))

    def test_ratio_gap_selects_ten_x_but_quality_gap_selects_frontier_plus(self):
        frontier = compile_best_of_breed_frontier(
            [
                FrontierObservation(
                    "F-1", "suite-a", BenchmarkDimension.OWNER_BURDEN,
                    5.0, "https://example.invalid/a", "2026-08-28",
                ),
                FrontierObservation(
                    "F-2", "suite-b", BenchmarkDimension.PROFESSIONAL_FINISHING,
                    5.0, "https://example.invalid/b", "2026-08-28",
                ),
            ]
        )
        gaps = calculate_frontier_gaps(
            frontier=frontier,
            sovara=(
                SovaraDimensionState(BenchmarkDimension.OWNER_BURDEN, 4.0, 1.0, "CI_ADMITTED"),
                SovaraDimensionState(BenchmarkDimension.PROFESSIONAL_FINISHING, 3.0, 1.0, "CI_ADMITTED"),
            ),
            ratio_dimensions=(BenchmarkDimension.OWNER_BURDEN,),
        )
        by_dimension = {gap.dimension: gap for gap in gaps}
        self.assertEqual(by_dimension[BenchmarkDimension.OWNER_BURDEN].ambition, AmbitionClass.TEN_X)
        self.assertEqual(by_dimension[BenchmarkDimension.PROFESSIONAL_FINISHING].ambition, AmbitionClass.FRONTIER_PLUS)

    def test_ten_x_target_requires_measured_positive_baseline(self):
        target = build_ten_x_target(
            metric="owner_interventions_per_mission",
            baseline=20.0,
            higher_is_better=False,
        )
        self.assertEqual(target.target, 2.0)
        self.assertTrue(target.met_by(1.5))
        self.assertFalse(target.met_by(3.0))
        with self.assertRaises(ValueError):
            build_ten_x_target(metric="owner_interventions", baseline=0.0, higher_is_better=False)

    def test_omega_scientist_requires_competing_falsifiable_hypotheses(self):
        target = build_ten_x_target(
            metric="recovery_seconds",
            baseline=100.0,
            higher_is_better=False,
        )
        experiment = preregister_omega_scientist_experiment(
            experiment_id="SC-X-001",
            dimension=BenchmarkDimension.AUTOMATED_RECOVERY,
            primary_metric="recovery_seconds",
            hypotheses=(
                ScientistHypothesis(
                    "H1", "Failure-Win composition reduces recovery time",
                    ("median recovery <= 10 seconds",),
                    ("median recovery > 10 seconds",),
                ),
                ScientistHypothesis(
                    "H2", "Static fallback performs as well or better",
                    ("static recovery <= adaptive recovery",),
                    ("adaptive recovery is materially faster",),
                ),
            ),
            benchmark_ids=("CFBE-CREATIVE-001",),
            rollback_condition="Any reliability or proof regression",
            ambition=AmbitionClass.TEN_X,
            ten_x_target=target,
        )
        self.assertEqual(experiment.authority_ceiling, "A1_INTERNAL")
        self.assertFalse(experiment.external_effect)
        self.assertTrue(experiment.preregistration_sha256)

    def test_meta_evolution_never_promotes_from_ci_without_runtime_and_value_proof(self):
        held = evaluate_meta_evolution(
            EvolutionEvidence(
                benchmark_refs=("CFBE-CREATIVE-001",),
                scientist_preregistered=True,
                deterministic_tests_passed=True,
                ci_admitted=True,
                provider_effect_required=True,
                provider_native_readback=False,
                repeated_success=False,
                value_gain_verified=False,
            )
        )
        self.assertEqual(held, MetaEvolutionState.HOLD_PROVIDER_READBACK_UNPROVEN)
        promoted = evaluate_meta_evolution(
            EvolutionEvidence(
                benchmark_refs=("CFBE-CREATIVE-001",),
                scientist_preregistered=True,
                deterministic_tests_passed=True,
                ci_admitted=True,
                provider_effect_required=True,
                provider_native_readback=True,
                repeated_success=True,
                value_gain_verified=True,
            )
        )
        self.assertEqual(promoted, MetaEvolutionState.PROMOTION_CANDIDATE)


class SovaraCreativeCommercialValueEngineTests(unittest.TestCase):
    def test_mission_economics_exposes_contribution_margin_and_unit_economics(self):
        economics = MissionEconomics(
            currency="ZAR",
            attributed_revenue=10000.0,
            direct_provider_cost=500.0,
            external_tool_cost=300.0,
            owner_labor_cost=700.0,
            other_direct_cost=500.0,
            approved_assets=10,
            published_assets=5,
        )
        snapshot = economics_snapshot(economics)
        self.assertEqual(snapshot["total_cost"], 2000.0)
        self.assertEqual(snapshot["contribution_margin"], 8000.0)
        self.assertAlmostEqual(snapshot["margin_rate"], 0.8)
        self.assertEqual(snapshot["cost_per_approved_asset"], 200.0)
        self.assertEqual(snapshot["revenue_per_published_asset"], 2000.0)

    def test_zero_baseline_never_fabricates_relative_gain(self):
        comparisons = compare_value_metrics(
            specs=(
                ValueMetricSpec(
                    "attributed_revenue",
                    ValueClass.COMMERCIAL,
                    MetricDirection.HIGHER_IS_BETTER,
                ),
            ),
            observations=(
                MetricObservation("attributed_revenue", 0.0, 100.0, "KDV:VALUE-001"),
            ),
        )
        self.assertIsNone(comparisons[0].relative_gain)
        self.assertTrue(comparisons[0].target_met)

    def test_value_gate_never_promotes_from_metrics_without_provider_readback(self):
        observations = (
            MetricObservation("contribution_margin", 100.0, 120.0, "KDV:MARGIN"),
            MetricObservation("attributed_revenue", 200.0, 250.0, "KDV:REVENUE"),
            MetricObservation("time_to_deliverable_seconds", 100.0, 80.0, "KDV:TIME"),
            MetricObservation("publication_success_rate", 0.9, 0.95, "KDV:PUBLISH"),
            MetricObservation("owner_interventions", 10.0, 5.0, "KDV:INTERVENTIONS"),
            MetricObservation("owner_minutes", 100.0, 60.0, "KDV:OWNER_MINUTES"),
        )
        decision = evaluate_value_gate(
            specs=default_production_value_specs(),
            observations=observations,
            evidence=ValueEvidence(provider_native_readback=False, repeated_success=True),
        )
        self.assertEqual(decision.state, ValueGateState.HOLD_RUNTIME_PROOF)
        self.assertFalse(decision.promotion_ready)

    def test_commercial_value_is_coequal_with_operational_and_usability_value(self):
        specs = (
            ValueMetricSpec("revenue", ValueClass.COMMERCIAL, MetricDirection.HIGHER_IS_BETTER),
            ValueMetricSpec("time", ValueClass.OPERATIONAL, MetricDirection.LOWER_IS_BETTER),
            ValueMetricSpec("owner", ValueClass.USABILITY, MetricDirection.LOWER_IS_BETTER),
        )
        decision = evaluate_value_gate(
            specs=specs,
            observations=(
                MetricObservation("revenue", 100.0, 90.0, "KDV:REV"),
                MetricObservation("time", 100.0, 50.0, "KDV:TIME"),
                MetricObservation("owner", 10.0, 2.0, "KDV:OWNER"),
            ),
            evidence=ValueEvidence(provider_native_readback=True, repeated_success=True),
        )
        self.assertEqual(decision.state, ValueGateState.HOLD_COMMERCIAL_VALUE)
        self.assertFalse(decision.promotion_ready)

    def test_full_value_evidence_can_reach_production_value_candidate(self):
        specs = (
            ValueMetricSpec("margin", ValueClass.COMMERCIAL, MetricDirection.HIGHER_IS_BETTER),
            ValueMetricSpec("time", ValueClass.OPERATIONAL, MetricDirection.LOWER_IS_BETTER),
            ValueMetricSpec("owner", ValueClass.USABILITY, MetricDirection.LOWER_IS_BETTER),
        )
        decision = evaluate_value_gate(
            specs=specs,
            observations=(
                MetricObservation("margin", 100.0, 140.0, "KDV:MARGIN"),
                MetricObservation("time", 100.0, 70.0, "KDV:TIME"),
                MetricObservation("owner", 10.0, 3.0, "KDV:OWNER"),
            ),
            evidence=ValueEvidence(provider_native_readback=True, repeated_success=True),
        )
        self.assertEqual(decision.state, ValueGateState.PRODUCTION_VALUE_CANDIDATE)
        self.assertTrue(decision.promotion_ready)
        self.assertEqual(decision.commercial_target_rate, 1.0)
        self.assertEqual(decision.operational_target_rate, 1.0)
        self.assertEqual(decision.usability_target_rate, 1.0)

    def test_foundry_reuses_k10_finops_and_evolution_governor_for_commercial_builds(self):
        candidate = plan_capability(
            capability_id="SC-COMMERCIAL-001",
            outcome="Build an adaptive campaign performance and creative value skill",
            skill_domains=(SkillDomain.COMMERCIAL_GROWTH, SkillDomain.PERFORMANCE_MARKETING),
            available_capabilities=(
                "K10_CANVA_CINEMA_OS",
                "FINOPS_ROUTE_OPTIMIZER",
                "FEDERATION_EVOLUTION_GOVERNOR",
                "CFBE_OMEGA",
                "FORMATION_OMEGA",
            ),
        )
        self.assertEqual(candidate.strategy, BuildStrategy.COMPOSE)
        self.assertIn("K10_CANVA_CINEMA_OS", candidate.reused_capabilities)
        self.assertIn("FINOPS_ROUTE_OPTIMIZER", candidate.reused_capabilities)
        self.assertIn("FEDERATION_EVOLUTION_GOVERNOR", candidate.reused_capabilities)

    def test_commercial_frontier_dimensions_are_first_class(self):
        self.assertEqual(BenchmarkDimension.COMMERCIAL_VALUE.value, "COMMERCIAL_VALUE")
        self.assertEqual(BenchmarkDimension.REVENUE_ATTRIBUTION.value, "REVENUE_ATTRIBUTION")
        self.assertEqual(BenchmarkDimension.PERFORMANCE_INTELLIGENCE.value, "PERFORMANCE_INTELLIGENCE")


if __name__ == "__main__":
    unittest.main()
