from __future__ import annotations

import unittest

from evidenceops.caseforge.capability_decision import (
    BlockerKind,
    CapabilityDecisionRequest,
    CapabilityScope,
    CapabilityState,
    GateDecision,
    RouteAttempt,
    TerminalClaim,
)
from evidenceops.caseforge.federation_capability_twin import (
    CapabilityTwin,
    ReadbackState,
    RuntimeState,
    SemanticState,
    TwinState,
)
from evidenceops.caseforge.federation_evolution_program import SYSTEM_PROFILES
from evidenceops.caseforge.federation_evolution_runtime import (
    CounterfactualEngine,
    DEFAULT_DEPENDENCY_EDGES,
    DependencyEdge,
    DependencyGraph,
    DependencyKind,
    ExecutableWorkZeroGate,
    FailureMemoryEntry,
    MissionContinuationKernel,
    MissionExecutionState,
    NegativeProofReceipt,
    OperationalMemory,
    PredictiveCapabilityPreloader,
    RouteClass,
    RoutePortfolioOptimizer,
    RouteSynthesizer,
    SelfHealingRouteEngine,
    SemanticFailureClassifier,
    SuccessRouteRecipe,
    TerminalStateFirewall,
)


def source_twin(system_id: str, *, runtime_state: RuntimeState = RuntimeState.SOURCE_ONLY, age: int = 0) -> CapabilityTwin:
    semantic = SemanticState.DECLARED_CONTRACT
    readback = ReadbackState.SOURCE_READBACK
    if runtime_state == RuntimeState.RUNTIME_PARTIAL:
        semantic = SemanticState.RUNTIME_SEMANTIC_VERIFIED
        readback = ReadbackState.RUNTIME_READBACK
    return CapabilityTwin(
        system_id=system_id,
        source_ref=f"REGISTRY:{system_id}",
        observed_at="2026-08-11T23:50:00+02:00",
        source_exists=True,
        canonical_readback=True,
        authority_ceiling="A1_INTERNAL",
        semantic_state=semantic,
        readback_state=readback,
        runtime_state=runtime_state,
        proof_ref=f"RCP:{system_id}",
        ttl_seconds=3600,
        age_seconds=age,
    )


def all_twins() -> dict[str, CapabilityTwin]:
    return {system_id: source_twin(system_id) for system_id in SYSTEM_PROFILES}


class DependencyGraphTests(unittest.TestCase):
    def test_default_graph_has_no_required_hard_cycle(self) -> None:
        graph = DependencyGraph(DEFAULT_DEPENDENCY_EDGES).validate().assert_no_required_cycle()
        self.assertIn("FEDERATION_OMEGA", graph.dependencies_of("DIRECT_RUNTIME"))
        self.assertIn("DIRECT_RUNTIME", graph.dependencies_of("ARCHITRON"))
        self.assertIn("TRUTHGRID", graph.dependencies_of("EVIDENCEOPS"))

    def test_failure_isolation_does_not_freeze_unrelated_systems(self) -> None:
        graph = DependencyGraph(DEFAULT_DEPENDENCY_EDGES).validate()
        affected = set(graph.affected_by_failure(["DIRECT_RUNTIME"]))
        unaffected = set(graph.unaffected_by_failure(["DIRECT_RUNTIME"]))
        self.assertIn("ARCHITRON", affected)
        self.assertIn("EVI", affected)
        self.assertIn("TRUTHGRID", unaffected)
        self.assertIn("LEX_OMEGA", unaffected)
        self.assertTrue(affected.isdisjoint(unaffected))

    def test_required_hard_cycle_is_rejected(self) -> None:
        graph = DependencyGraph(
            (
                DependencyEdge("FEDERATION_OMEGA", "DIRECT_RUNTIME", DependencyKind.HARD, True, "R1"),
                DependencyEdge("DIRECT_RUNTIME", "FEDERATION_OMEGA", DependencyKind.HARD, True, "R2"),
            )
        )
        with self.assertRaisesRegex(ValueError, "cycle"):
            graph.validate().assert_no_required_cycle()


class RouteSynthesisTests(unittest.TestCase):
    def test_synthesizer_produces_four_material_route_classes(self) -> None:
        routes = RouteSynthesizer().synthesize("TRUTHGRID", all_twins())
        self.assertEqual(4, len(routes))
        self.assertEqual(
            {RouteClass.DIRECT, RouteClass.SPECIALIZED, RouteClass.COMPOSITE, RouteClass.REVERSIBLE_EXPERIMENT},
            {route.route_class for route in routes},
        )
        composite = next(route for route in routes if route.route_class is RouteClass.COMPOSITE)
        self.assertIn("CORPUS_FACTORY", composite.systems)
        self.assertIn("VERITAS", composite.systems)

    def test_optimizer_prefers_proof_and_reversibility_not_first_route(self) -> None:
        routes = RouteSynthesizer().synthesize("TRUTHGRID", all_twins())
        ranked = RoutePortfolioOptimizer().rank(routes)
        self.assertEqual(RouteClass.SPECIALIZED, ranked[0].route.route_class)
        self.assertGreaterEqual(ranked[0].score, ranked[-1].score)


class FailureAndRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.classifier = SemanticFailureClassifier()
        self.healer = SelfHealingRouteEngine()

    def test_classifier_distinguishes_schema_auth_approval_transient_and_platform(self) -> None:
        cases = {
            "Unable to parse range: CONTROL!A1:H20": BlockerKind.INVALID_ARGUMENT_OR_SCHEMA,
            "Authentication required; connector not connected": BlockerKind.AUTHENTICATION_OR_CONNECTION_REQUIRED,
            "Approval required for external write": BlockerKind.APPROVAL_OR_PERMISSION_REQUIRED,
            "503 temporarily unavailable": BlockerKind.TRANSIENT_TECHNICAL_LIMITATION,
            "not supported by platform; platform hard limit": BlockerKind.PLATFORM_HARD_LIMIT,
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                result = self.classifier.classify(message, evidence="RCP-ERR")
                self.assertEqual(expected, result.blocker)

    def test_approval_hold_does_not_freeze_unaffected_lanes(self) -> None:
        failure = self.classifier.classify("approval required for external write", evidence="RCP-A")
        repair = self.healer.decide(failure)
        self.assertTrue(repair.approval_required)
        self.assertTrue(repair.continue_unaffected_lanes)
        self.assertFalse(repair.retry_same_route)

    def test_schema_error_generates_corrected_route_recovery_not_cannot(self) -> None:
        failure = self.classifier.classify("invalid argument: unable to parse range", evidence="RCP-SCHEMA")
        repair = self.healer.decide(failure)
        self.assertEqual("DISCOVER_SCHEMA_AND_RETRY_CORRECTED_ROUTE", repair.repair_action)
        self.assertFalse(repair.terminal_for_exact_scope)


class OperationalMemoryTests(unittest.TestCase):
    def test_success_routes_are_retrievable_by_objective_class(self) -> None:
        memory = OperationalMemory()
        memory.record_success(
            SuccessRouteRecipe(
                recipe_id="R-SCHEMA",
                objective_class="SHEETS_READ",
                route_id="METADATA_THEN_RANGE",
                prerequisites=("spreadsheet_id",),
                proof_ref="CAN-CRG-001",
                freshness_rule="re-read metadata when schema changes",
            )
        )
        found = memory.known_route("SHEETS_READ")
        self.assertEqual(("R-SCHEMA",), tuple(item.recipe_id for item in found))

    def test_failure_recurrence_increments_without_losing_repair(self) -> None:
        memory = OperationalMemory()
        entry = FailureMemoryEntry("STALE_BASE_HEAD", "RECUT_CURRENT_MAIN", "PR334")
        memory.record_failure(entry)
        memory.record_failure(entry)
        self.assertEqual(2, memory.failures["STALE_BASE_HEAD"].recurrence_count)
        self.assertEqual("RECUT_CURRENT_MAIN", memory.failures["STALE_BASE_HEAD"].repair_action)


class PreloadAndTerminalProofTests(unittest.TestCase):
    def test_preloader_flags_stale_and_adapter_required_dependencies(self) -> None:
        twins = all_twins()
        twins["KIM_DATAVERSE"] = source_twin("KIM_DATAVERSE", age=4000)
        twins["VERITAS"] = CapabilityTwin(
            system_id="VERITAS",
            source_ref="REGISTRY:VERITAS",
            observed_at="2026-08-11T23:50:00+02:00",
            source_exists=True,
            canonical_readback=True,
            authority_ceiling="A1_INTERNAL",
            semantic_state=SemanticState.DECLARED_CONTRACT,
            readback_state=ReadbackState.SOURCE_READBACK,
            runtime_state=RuntimeState.ADAPTER_REQUIRED,
            proof_ref="RCP:VERITAS",
        )
        plan = PredictiveCapabilityPreloader().plan("TRUTHGRID", twins)
        self.assertIn("KIM_DATAVERSE", plan.refresh_required)
        self.assertIn("VERITAS", plan.adapter_required)

    def test_terminal_firewall_rejects_cannot_from_local_route_failure(self) -> None:
        request = CapabilityDecisionRequest(
            objective="read canonical control",
            claim=TerminalClaim.CANNOT,
            scope=CapabilityScope.CURRENT_CHAT,
            state=CapabilityState.ROUTE_CALLABLE,
            blocker=BlockerKind.INVALID_ARGUMENT_OR_SCHEMA,
            current_discovery_ref="RCP-DISCOVERY",
            route_attempts=(
                RouteAttempt("bad-range", blocker=BlockerKind.INVALID_ARGUMENT_OR_SCHEMA),
            ),
        )
        decision = TerminalStateFirewall().evaluate(request)
        self.assertEqual(GateDecision.DENY_TERMINAL_CLAIM, decision.decision)
        self.assertIn("ROUTE_OR_DEPENDENCY_BLOCKER_IS_NOT_OBJECTIVE_INCAPABILITY", decision.reason_codes)


class NegativeProofAndCounterfactualTests(unittest.TestCase):
    def test_negative_proof_requires_receipts_for_checked_routes(self) -> None:
        with self.assertRaisesRegex(ValueError, "receipts"):
            NegativeProofReceipt(
                proposition="native file not located",
                scope="Drive+Gmail",
                routes_checked=("Drive", "Gmail"),
                search_receipts=(),
            ).validate()
        receipt = NegativeProofReceipt(
            proposition="native file not located in bounded connected corpus",
            scope="Drive+Gmail",
            routes_checked=("Drive", "Gmail"),
            search_receipts=("RCP-D", "RCP-G"),
        ).validate()
        self.assertEqual(2, len(receipt.search_receipts))

    def test_platform_limit_counterfactual_keeps_objective_open_for_equivalent_route(self) -> None:
        counterfactual = CounterfactualEngine().derive(BlockerKind.PLATFORM_HARD_LIMIT)
        self.assertTrue(counterfactual.objective_remains_open)
        self.assertEqual("OBJECTIVE_EQUIVALENT_USER_LEVEL_IMPLEMENTATION", counterfactual.minimum_changed_condition)


class MissionCompletionTests(unittest.TestCase):
    def test_internal_work_remaining_forces_continuation(self) -> None:
        state = MissionExecutionState("M-1", executable_internal_dependencies=3)
        decision = MissionContinuationKernel().decide(state)
        self.assertTrue(decision.continue_execution)
        self.assertFalse(decision.mission_complete)

    def test_external_boundary_is_reported_separately_after_internal_work_zero(self) -> None:
        state = MissionExecutionState(
            "M-2",
            executable_internal_dependencies=0,
            external_dependencies=("EMPLOYER_PRODUCTION",),
        )
        work_zero = ExecutableWorkZeroGate().evaluate(state)
        self.assertTrue(work_zero.internal_complete)
        self.assertEqual(("EMPLOYER_PRODUCTION",), work_zero.external_dependencies)
        decision = MissionContinuationKernel().decide(state)
        self.assertFalse(decision.continue_execution)
        self.assertEqual("BOUND_EXTERNAL_HOLDS", decision.next_mode)

    def test_user_stop_is_respected(self) -> None:
        state = MissionExecutionState("M-3", 4, user_stopped=True)
        decision = MissionContinuationKernel().decide(state)
        self.assertFalse(decision.continue_execution)
        self.assertEqual("USER_STOP", decision.reason)


if __name__ == "__main__":
    unittest.main()
