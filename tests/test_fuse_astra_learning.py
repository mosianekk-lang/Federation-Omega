import unittest

from fuse_astra_semantic_kernel.kernel import CapabilityProfile, Implementation, Maturity, build_default_registry
from fuse_astra_semantic_kernel.learning import AdaptiveRouteAdvisor, OutcomeLedger, RouteOutcome, route_signature
from fuse_astra_semantic_kernel.planner import GlobalCapabilityCompiler, ImplementationMeta, RoutePolicy


def impl(cap, name, provider, cost, quality=0.9, local=False, proof=True):
    return Implementation(
        impl_id=name,
        capability_id=cap,
        provider=provider,
        quality=quality,
        latency_ms=100.0,
        cost_units=cost,
        sovereignty=1.0 if local else 0.5,
        maturity=Maturity.LOCAL_COMPONENT,
        proof_ok=proof,
        local=local,
    )


class LearningAdvisorTests(unittest.TestCase):
    def setUp(self):
        self.registry = build_default_registry()
        self.profile = CapabilityProfile("P", ("CK.STATE",), min_quality=0.8)

    def test_unproved_candidate_never_enters_learning_frontier(self):
        compiler = GlobalCapabilityCompiler(
            self.registry,
            [
                ImplementationMeta(impl("CK.STATE", "proved", "vendor-a", 0.2, proof=True)),
                ImplementationMeta(impl("CK.STATE", "unproved", "vendor-b", 0.01, proof=False)),
            ],
        )
        advice = AdaptiveRouteAdvisor(compiler, OutcomeLedger()).advise("coding", self.profile)
        self.assertEqual(advice.incumbent.selected["CK.STATE"].implementation.impl_id, "proved")
        self.assertIsNone(advice.shadow_challenger)

    def test_learning_never_replaces_incumbent_automatically(self):
        compiler = GlobalCapabilityCompiler(
            self.registry,
            [
                ImplementationMeta(impl("CK.STATE", "cheap", "vendor-a", 0.1, quality=0.88)),
                ImplementationMeta(impl("CK.STATE", "strong", "vendor-b", 0.5, quality=0.99)),
            ],
        )
        ledger = OutcomeLedger()
        static_incumbent = compiler.select(self.profile)
        # Record strong outcomes for the other route; advisor may nominate it but
        # must leave the deterministic incumbent unchanged pending external court.
        for route in compiler.pareto_frontier(self.profile):
            sig = route_signature(route)
            if route.selected["CK.STATE"].implementation.impl_id == "strong":
                for _ in range(5):
                    ledger.record(RouteOutcome("coding", sig, True, 1.0, 0.5, 100))
        advice = AdaptiveRouteAdvisor(compiler, ledger).advise("coding", self.profile)
        self.assertEqual(route_signature(advice.incumbent), route_signature(static_incumbent))

    def test_untried_pareto_route_is_suggested_for_shadow(self):
        compiler = GlobalCapabilityCompiler(
            self.registry,
            [
                ImplementationMeta(impl("CK.STATE", "fast", "vendor-a", 0.4, quality=0.9)),
                ImplementationMeta(impl("CK.STATE", "cheap", "vendor-b", 0.1, quality=0.9)),
            ],
        )
        advice = AdaptiveRouteAdvisor(compiler, OutcomeLedger()).advise("coding", self.profile)
        self.assertIsNotNone(advice.shadow_challenger)
        self.assertIn("shadow", advice.reason.lower())

    def test_policy_constraints_apply_before_advice(self):
        compiler = GlobalCapabilityCompiler(
            self.registry,
            [
                ImplementationMeta(impl("CK.STATE", "local", "fuse-local", 0.2, local=True)),
                ImplementationMeta(impl("CK.STATE", "cloud", "cloud", 0.01, local=False)),
            ],
        )
        advice = AdaptiveRouteAdvisor(compiler, OutcomeLedger()).advise(
            "private",
            self.profile,
            RoutePolicy(min_local_fraction=1.0),
        )
        self.assertEqual(advice.incumbent.providers, {"fuse-local"})
        self.assertIsNone(advice.shadow_challenger)

    def test_outcome_ledger_aggregates_external_scores(self):
        ledger = OutcomeLedger()
        sig = (("CK.STATE", "x"),)
        ledger.record(RouteOutcome("coding", sig, True, 0.9, 0.2, 100))
        ledger.record(RouteOutcome("coding", sig, False, 0.2, 0.2, 100))
        stats = ledger.stats("coding", sig)
        self.assertEqual(stats.count, 2)
        self.assertEqual(stats.success_count, 1)
        self.assertAlmostEqual(stats.success_rate, 0.5)


if __name__ == "__main__":
    unittest.main()
