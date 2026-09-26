import unittest

from fuse_astra_semantic_kernel.kernel import (
    CapabilityProfile,
    Implementation,
    Maturity,
    build_default_registry,
)
from fuse_astra_semantic_kernel.planner import (
    GlobalCapabilityCompiler,
    ImplementationMeta,
    RoutePlanningError,
    RoutePolicy,
    RoutePreferences,
)


def impl(
    cap,
    name,
    provider="fuse-local",
    quality=0.9,
    cost=0.2,
    latency=100,
    sovereignty=1.0,
    proof=True,
    local=True,
):
    return Implementation(
        impl_id=name,
        capability_id=cap,
        provider=provider,
        quality=quality,
        latency_ms=latency,
        cost_units=cost,
        sovereignty=sovereignty,
        maturity=Maturity.LOCAL_COMPONENT,
        proof_ok=proof,
        local=local,
    )


class GlobalRoutePlannerTests(unittest.TestCase):
    def test_cross_capability_tag_requirement_eliminates_incompatible_combo(self):
        r = build_default_registry()
        p = CapabilityProfile("P", ("CK.MODEL", "CK.EXEC"), min_quality=0.8)
        items = [
            ImplementationMeta(impl("CK.MODEL", "gpu-model"), requires_tags=("cuda",)),
            ImplementationMeta(impl("CK.EXEC", "cpu-exec", cost=0.01), provides_tags=("cpu",)),
            ImplementationMeta(impl("CK.EXEC", "gpu-exec", cost=0.30), provides_tags=("cuda",)),
        ]
        route = GlobalCapabilityCompiler(r, items).select(p)
        self.assertEqual(route.selected["CK.EXEC"].implementation.impl_id, "gpu-exec")

    def test_low_confidence_route_is_hard_rejected_before_economics(self):
        r = build_default_registry()
        p = CapabilityProfile("P", ("CK.STATE",), min_quality=0.8)
        items = [
            ImplementationMeta(impl("CK.STATE", "cheap-estimate", cost=0.01), confidence=0.2),
            ImplementationMeta(impl("CK.STATE", "proved", cost=0.50), confidence=0.95),
        ]
        route = GlobalCapabilityCompiler(r, items).select(
            p, RoutePolicy(min_evidence_confidence=0.8)
        )
        self.assertEqual(route.selected["CK.STATE"].implementation.impl_id, "proved")

    def test_provider_concentration_can_be_bounded_across_whole_route(self):
        r = build_default_registry()
        p = CapabilityProfile("P", ("CK.STATE", "CK.CONTEXT"), min_quality=0.8)
        items = [
            ImplementationMeta(impl("CK.STATE", "a-state", provider="a", local=False)),
            ImplementationMeta(impl("CK.STATE", "b-state", provider="b", local=False)),
            ImplementationMeta(impl("CK.CONTEXT", "a-context", provider="a", local=False)),
            ImplementationMeta(impl("CK.CONTEXT", "b-context", provider="b", local=False)),
        ]
        route = GlobalCapabilityCompiler(r, items).select(
            p, RoutePolicy(max_provider_concentration=0.5)
        )
        self.assertEqual(route.provider_concentration, 0.5)
        self.assertEqual(len(route.providers), 2)

    def test_openai_independence_is_enforced_on_entire_route(self):
        r = build_default_registry()
        p = CapabilityProfile(
            "P",
            ("CK.STATE", "CK.MODEL"),
            min_quality=0.8,
            require_astra_independent=True,
        )
        items = [
            ImplementationMeta(impl("CK.STATE", "local-state")),
            ImplementationMeta(impl("CK.MODEL", "astra", provider="openai", local=False)),
        ]
        with self.assertRaises(RoutePlanningError):
            GlobalCapabilityCompiler(r, items).select(p)

    def test_pareto_frontier_preserves_real_tradeoff(self):
        r = build_default_registry()
        p = CapabilityProfile("P", ("CK.STATE",), min_quality=0.8)
        items = [
            ImplementationMeta(impl("CK.STATE", "fast", quality=0.85, cost=0.4, latency=50)),
            ImplementationMeta(impl("CK.STATE", "cheap", quality=0.85, cost=0.1, latency=500)),
            ImplementationMeta(impl("CK.STATE", "dominated", quality=0.80, cost=0.6, latency=700)),
        ]
        frontier = GlobalCapabilityCompiler(r, items).pareto_frontier(p)
        ids = {x.selected["CK.STATE"].implementation.impl_id for x in frontier}
        self.assertEqual(ids, {"fast", "cheap"})

    def test_failure_risk_can_outweigh_small_cost_advantage(self):
        r = build_default_registry()
        p = CapabilityProfile("P", ("CK.STATE",), min_quality=0.8)
        items = [
            ImplementationMeta(
                impl("CK.STATE", "fragile", cost=0.05),
                failure_probability=0.4,
            ),
            ImplementationMeta(
                impl("CK.STATE", "reliable", cost=0.10),
                failure_probability=0.01,
            ),
        ]
        route = GlobalCapabilityCompiler(r, items).select(
            p,
            preferences=RoutePreferences(failure_weight=10.0, cost_weight=1.0),
        )
        self.assertEqual(route.selected["CK.STATE"].implementation.impl_id, "reliable")

    def test_required_local_fraction_enforces_sovereign_compute_mix(self):
        r = build_default_registry()
        p = CapabilityProfile("P", ("CK.STATE", "CK.CONTEXT"), min_quality=0.8)
        items = [
            ImplementationMeta(impl("CK.STATE", "local-state", local=True)),
            ImplementationMeta(impl("CK.STATE", "cloud-state", provider="cloud", local=False, cost=0.01)),
            ImplementationMeta(impl("CK.CONTEXT", "local-context", local=True)),
            ImplementationMeta(impl("CK.CONTEXT", "cloud-context", provider="cloud", local=False, cost=0.01)),
        ]
        route = GlobalCapabilityCompiler(r, items).select(
            p,
            RoutePolicy(min_local_fraction=1.0),
        )
        self.assertEqual(route.local_fraction, 1.0)
        self.assertEqual(route.providers, {"fuse-local"})


if __name__ == "__main__":
    unittest.main()
