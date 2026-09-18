from __future__ import annotations

import json
from pathlib import Path
import unittest

from superior_logic.digital_twin import CapabilityEdge, FederationDigitalTwin
from superior_logic.hypercube_bottleneck_resolver import (
    BottleneckBenchmark,
    BottleneckKind,
    BottleneckSignal,
    HypercubeBottleneckResolver,
    MARKET_PATTERNS,
    RouteFamily,
)
from superior_logic.hyperperformance import HyperperformanceController
from superior_logic.mission_ir import LaneClass, MissionCompiler, MissionNode


def signal(**overrides) -> BottleneckSignal:
    base = dict(
        bottleneck_id="BOT-001",
        kind=BottleneckKind.CI_FEEDBACK,
        summary="CI feedback is dominated by repeated serial validation and cold work.",
        evidence_refs=("ci:run:1", "trace:critical-path"),
        throughput_drag=0.82,
        latency_share=0.88,
        queue_wait_share=0.64,
        failure_recurrence=0.58,
        dependency_centrality=0.76,
        owner_burden=0.60,
        cost_pressure=0.55,
        proof_gap=0.42,
        risk=0.24,
        commercial_leverage=0.80,
        differentiation_potential=0.74,
        internal_coverage=0.45,
        external_boundary=False,
        affected_missions=4,
        internal_capabilities=("ProofOS", "Bubbles", "CFBE"),
    )
    base.update(overrides)
    return BottleneckSignal(**base)


ROOT = Path(__file__).resolve().parents[1]


class HypercubeGovernanceContractTests(unittest.TestCase):
    def test_market_harvest_is_mechanism_only_and_clean_room(self):
        self.assertGreaterEqual(len(MARKET_PATTERNS), 8)
        self.assertTrue(all(item.clean_room_only for item in MARKET_PATTERNS))
        families = {item.source_family for item in MARKET_PATTERNS}
        self.assertIn("GitHub + Graphite", families)
        self.assertIn("Bazel + BuildBuddy", families)
        self.assertIn("Temporal", families)
        self.assertIn("OpenTelemetry", families)

    def test_governance_requires_commercial_uplift_and_no_external_authority(self):
        data = json.loads(
            (ROOT / "governance" / "fuse_hypercube_bottleneck_resolver_v1.json").read_text()
        )
        self.assertEqual("FUSE-HYPERCUBE-HBR-001", data["capability_id"])
        self.assertFalse(data["external_effect"])
        self.assertTrue(data["promotion_contract"]["proof_before_claim"])
        self.assertFalse(data["promotion_contract"]["automatic_stable_self_promotion"])
        self.assertIn("commercial_leverage", data["commercial_outcome_dimensions"])
        self.assertIn(
            "SYSTEM_MUST_REMEASURE_AFTER_EACH_FIX_AND_CONTINUE_IF_THE_CONSTRAINT_STILL_DOMINATES",
            data["algorithmic_laws"],
        )

    def test_master_directive_and_acme_inherit_bottleneck_to_advantage_law(self):
        directive = (
            ROOT / "docs" / "architecture" / "FUSE_ONE_ASTRA_OMNISURFACE_MASTER_DIRECTIVE_V3.md"
        ).read_text(encoding="utf-8")
        acme = (ROOT / "doctrine" / "ACME-001-v3.0.md").read_text(encoding="utf-8")
        self.assertIn("HYPERCUBE BOTTLENECK-TO-COMMERCIAL-ADVANTAGE LOOP", directive)
        self.assertIn("Hypercube Bottleneck-to-Advantage Gate", acme)
        self.assertIn("F27 bottleneck reported without resolution harvest", acme)


class HypercubeBottleneckResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = HypercubeBottleneckResolver()

    def test_ci_bottleneck_harvests_cache_dynamic_pipeline_and_test_intelligence(self):
        result = self.resolver.resolve(signal())
        self.assertEqual(result.action_state, "RESOLUTION_READY")
        self.assertGreater(result.bottleneck_score, 0.0)
        self.assertGreater(result.commercial_product_score, 0.0)
        self.assertIn("REMOTE_CACHE_EXECUTION_DEDUP", result.market_harvest)
        self.assertIn("DYNAMIC_PIPELINE_COMPILATION", result.market_harvest)
        self.assertIn("TEST_IMPACT_SELECTION", result.market_harvest)
        self.assertTrue(result.portfolio)
        self.assertFalse(result.external_effect_authorized)
        self.assertFalse(result.stable_self_promotion_allowed)
        self.assertIn("ProofOS", result.internal_harvest)

    def test_serial_dependency_harvests_stack_aware_and_speculative_routes(self):
        item = signal(
            kind=BottleneckKind.SERIAL_DEPENDENCY,
            summary="Stacked PR admission creates repeated bottom-up rebase and CI waits.",
        )
        result = self.resolver.resolve(item)
        self.assertIn("STACK_AWARE_MERGE_QUEUE", result.market_harvest)
        self.assertIn("SPECULATIVE_PARALLEL_VALIDATION", result.market_harvest)
        self.assertTrue(
            any(
                candidate.family in {RouteFamily.MARKET_COMPOSITE, RouteFamily.INVENT_ALGORITHM}
                for candidate in result.portfolio
            )
        )
        self.assertIn("Stack-aware convergence queue", result.product_features)

    def test_external_boundary_is_preserved_while_alternatives_are_still_generated(self):
        item = signal(
            kind=BottleneckKind.EXTERNAL_BOUNDARY,
            external_boundary=True,
            summary="External provider boundary prevents direct automatic continuation.",
            risk=0.45,
        )
        result = self.resolver.resolve(item)
        self.assertTrue(result.portfolio)
        self.assertFalse(result.external_effect_authorized)
        self.assertIn("External-boundary-aware graceful degradation", result.product_features)
        self.assertTrue(
            all("EXTERNAL_BOUNDARY_PRESERVED" in candidate.reason_codes for candidate in result.portfolio)
        )

    def test_recurring_shared_bottleneck_becomes_system_upgrade_candidate(self):
        result = self.resolver.resolve(
            signal(
                failure_recurrence=0.9,
                affected_missions=6,
                commercial_leverage=0.9,
                differentiation_potential=0.9,
            )
        )
        self.assertTrue(result.system_upgrade_candidate)
        self.assertIn(
            "REGISTER_RECURRING_BOTTLENECK_AS_REUSABLE_CAPABILITY_OR_PRODUCT_FEATURE",
            result.next_actions,
        )

    def test_low_internal_coverage_keeps_invention_route_available(self):
        result = self.resolver.resolve(
            signal(
                kind=BottleneckKind.UNKNOWN,
                internal_coverage=0.02,
                internal_capabilities=(),
                throughput_drag=0.95,
                failure_recurrence=0.85,
                differentiation_potential=0.95,
            )
        )
        self.assertTrue(
            any(candidate.family is RouteFamily.INVENT_ALGORITHM for candidate in result.portfolio)
        )

    def test_missing_evidence_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "HYPERCUBE_BOTTLENECK_EVIDENCE_REQUIRED"):
            self.resolver.resolve(signal(evidence_refs=()))

    def test_measured_positive_nonregressive_route_promotes(self):
        verdict = self.resolver.judge_benchmark(
            BottleneckBenchmark(
                candidate_id="HBR-CANDIDATE-1",
                baseline_throughput=10,
                candidate_throughput=15,
                baseline_latency=100,
                candidate_latency=60,
                baseline_failure_rate=0.10,
                candidate_failure_rate=0.05,
                baseline_owner_burden=10,
                candidate_owner_burden=4,
                baseline_cost=100,
                candidate_cost=80,
                baseline_commercial_value=100,
                candidate_commercial_value=125,
                acceptance_passed=True,
                proof_refs=("proof:benchmark:1",),
            )
        )
        self.assertEqual("PROMOTE_CANDIDATE", verdict.decision)
        self.assertGreater(verdict.value_score, 0.03)
        self.assertIn("COMMERCIAL_VALUE_IMPROVED", verdict.reason_codes)
        self.assertIn("MEASURED_NONREGRESSIVE_POSITIVE_VALUE", verdict.reason_codes)

    def test_quality_regression_rejects_even_if_throughput_improves(self):
        verdict = self.resolver.judge_benchmark(
            BottleneckBenchmark(
                candidate_id="HBR-CANDIDATE-2",
                baseline_throughput=10,
                candidate_throughput=20,
                baseline_latency=100,
                candidate_latency=50,
                baseline_failure_rate=0.02,
                candidate_failure_rate=0.10,
                baseline_owner_burden=5,
                candidate_owner_burden=3,
                baseline_cost=100,
                candidate_cost=70,
                baseline_commercial_value=100,
                candidate_commercial_value=120,
                acceptance_passed=True,
                proof_refs=("proof:benchmark:2",),
            )
        )
        self.assertEqual("REJECT", verdict.decision)
        self.assertIn("FAILURE_RATE_REGRESSION", verdict.reason_codes)

    def test_benchmark_without_proof_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "HYPERCUBE_BENCHMARK_PROOF_REQUIRED"):
            self.resolver.judge_benchmark(
                BottleneckBenchmark(
                    candidate_id="HBR-CANDIDATE-3",
                    baseline_throughput=10,
                    candidate_throughput=11,
                    baseline_latency=100,
                    candidate_latency=90,
                    baseline_failure_rate=0.1,
                    candidate_failure_rate=0.1,
                    baseline_owner_burden=5,
                    candidate_owner_burden=5,
                    baseline_cost=100,
                    candidate_cost=100,
                    baseline_commercial_value=100,
                    candidate_commercial_value=101,
                    acceptance_passed=True,
                    proof_refs=(),
                )
            )

    def test_resolve_many_prioritizes_system_constraints(self):
        high = signal(
            bottleneck_id="BOT-HIGH",
            throughput_drag=0.95,
            latency_share=0.95,
            dependency_centrality=0.95,
        )
        low = signal(
            bottleneck_id="BOT-LOW",
            throughput_drag=0.1,
            latency_share=0.1,
            queue_wait_share=0.1,
            failure_recurrence=0.1,
            dependency_centrality=0.1,
            owner_burden=0.1,
            proof_gap=0.1,
        )
        results = self.resolver.resolve_many((low, high))
        self.assertEqual(results[0].bottleneck_id, "BOT-HIGH")


class HyperperformanceHypercubeIntegrationTests(unittest.TestCase):
    def test_discovered_latency_bottleneck_is_auto_compiled_into_resolution(self):
        twin = FederationDigitalTwin()
        controller = HyperperformanceController(twin=twin)
        mission = MissionCompiler().compile(
            mission_id="M-HYPERCUBE-1",
            objective="reduce bottleneck latency while preserving proof",
            success_condition="latency reduced with proof intact",
            nodes=(
                MissionNode(
                    "slow",
                    "slow stage",
                    "compute",
                    LaneClass.COMPUTE,
                    estimated_latency_ms=90_000,
                    risk=0.2,
                ),
            ),
        )
        results = controller.discover_and_resolve_bottlenecks(missions=(mission,))
        self.assertTrue(results)
        result = next(item for item in results if item.bottleneck_id.startswith("LATENCY:"))
        self.assertEqual(result.action_state, "RESOLUTION_READY")
        self.assertTrue(result.market_harvest)
        self.assertIn("RUN_TOP_DIVERSE_ROUTES_IN_SHADOW_OR_DETERMINISTIC_COURT", result.next_actions)

    def test_deep_seek_discovers_serial_proof_cost_and_authority_constraints(self):
        controller = HyperperformanceController(twin=FederationDigitalTwin())
        mission = MissionCompiler().compile(
            mission_id="M-HYPERCUBE-DEEP",
            objective="close a deep serial proof-heavy costly mission",
            success_condition="constraint no longer dominates",
            nodes=(
                MissionNode(
                    "n1", "compile", "build", LaneClass.COMPUTE,
                    estimated_latency_ms=20_000,
                    estimated_cost=0.2,
                    proof_obligations=("source",),
                ),
                MissionNode(
                    "n2", "test", "proof", LaneClass.EVIDENCE,
                    depends_on=("n1",),
                    estimated_latency_ms=25_000,
                    estimated_cost=0.3,
                    proof_obligations=("tests",),
                ),
                MissionNode(
                    "n3", "deploy", "provider", LaneClass.PROVIDER,
                    depends_on=("n2",),
                    estimated_latency_ms=30_000,
                    estimated_cost=2.0,
                    reversible=False,
                    authority="PROVIDER_MUTATION",
                    proof_obligations=("provider",),
                ),
                MissionNode(
                    "n4", "readback", "provider", LaneClass.CRITICAL,
                    depends_on=("n3",),
                    estimated_latency_ms=35_000,
                    estimated_cost=0.5,
                    reversible=False,
                    authority="PROVIDER_MUTATION",
                    proof_obligations=("semantic",),
                ),
            ),
        )
        results = controller.discover_and_resolve_bottlenecks(missions=(mission,))
        ids = {item.bottleneck_id for item in results}
        self.assertIn("SERIAL:M-HYPERCUBE-DEEP", ids)
        self.assertIn("PROOF:M-HYPERCUBE-DEEP", ids)
        self.assertIn("AUTHORITY:M-HYPERCUBE-DEEP", ids)
        self.assertTrue(any(item.bottleneck_id.startswith("COST:M-HYPERCUBE-DEEP") for item in results))

    def test_capability_gap_is_harvested_without_dispatch_authority(self):
        twin = FederationDigitalTwin()
        twin.upsert(
            CapabilityEdge(
                "read",
                "GITHUB",
                "READ",
                "REPO",
                "READ_ONLY",
                1.0,
                5,
                0.0,
                0.0,
                True,
            )
        )
        controller = HyperperformanceController(twin=twin)
        results = controller.discover_and_resolve_bottlenecks(
            required_capabilities=(("WRITE", "REPO"),)
        )
        self.assertEqual(1, len(results))
        self.assertFalse(results[0].external_effect_authorized)
        self.assertTrue(results[0].portfolio)


if __name__ == "__main__":
    unittest.main()
