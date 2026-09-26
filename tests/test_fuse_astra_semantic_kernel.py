import unittest

from fuse_astra_semantic_kernel.kernel import (
    AmbiguousAliasError,
    CapabilityCompiler,
    CapabilityProfile,
    Implementation,
    Maturity,
    PROFILES,
    build_default_registry,
)


def impl(
    cap,
    name,
    provider="fuse-local",
    quality=0.9,
    cost=0.2,
    latency=100,
    sovereignty=1.0,
    maturity=Maturity.LOCAL_COMPONENT,
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
        maturity=maturity,
        proof_ok=proof,
        local=local,
    )


class SemanticKernelTests(unittest.TestCase):
    def test_numeric_alias_collision_is_preserved_not_overwritten(self):
        r = build_default_registry()
        self.assertEqual(
            r.alias_matches("IH-109"),
            ("LANG.EQUIVALENCE_COURT", "SERVE.DISAGGREGATED_PREFILL_DECODE"),
        )
        with self.assertRaises(AmbiguousAliasError):
            r.resolve_alias("IH-109")

    def test_semantic_identity_is_unambiguous(self):
        r = build_default_registry()
        self.assertEqual(r.get("CK.STATE").semantic_id, "CK.STATE")

    def test_hard_gates_precede_economic_scoring(self):
        r = build_default_registry()
        p = CapabilityProfile("P", ("CK.STATE",), min_quality=0.8)
        candidates = [
            impl("CK.STATE", "cheap-but-unproved", quality=0.99, cost=0.01, proof=False),
            impl("CK.STATE", "proved", quality=0.9, cost=0.5, proof=True),
        ]
        route = CapabilityCompiler(r, candidates).compile(p)
        self.assertEqual(route.selected["CK.STATE"].impl_id, "proved")

    def test_astra_independent_profile_rejects_openai_only_route(self):
        r = build_default_registry()
        p = CapabilityProfile(
            "P",
            ("CK.STATE",),
            min_quality=0.8,
            require_astra_independent=True,
        )
        with self.assertRaises(RuntimeError):
            CapabilityCompiler(
                r,
                [impl("CK.STATE", "astra", provider="openai", local=False)],
            ).compile(p)

    def test_local_preference_breaks_close_route_in_favor_of_sovereignty(self):
        r = build_default_registry()
        p = CapabilityProfile("P", ("CK.STATE",), min_quality=0.8, prefer_local=True)
        candidates = [
            impl("CK.STATE", "external", provider="vendor", local=False, cost=0.20, sovereignty=0.2),
            impl("CK.STATE", "local", local=True, cost=0.24, sovereignty=1.0),
        ]
        route = CapabilityCompiler(r, candidates).compile(p)
        self.assertEqual(route.selected["CK.STATE"].impl_id, "local")

    def test_local_offline_profile_compiles_when_all_primitives_proved(self):
        r = build_default_registry()
        p = PROFILES["PROFILE.LOCAL_OFFLINE"]
        candidates = [impl(cap, f"local-{cap}") for cap in p.required_capabilities]
        route = CapabilityCompiler(r, candidates).compile(p)
        self.assertTrue(route.astra_independent)
        self.assertEqual(set(route.selected), set(p.required_capabilities))


if __name__ == "__main__":
    unittest.main()
