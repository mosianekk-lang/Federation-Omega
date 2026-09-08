import unittest

from federation.mobile_gateway.fuse_mobile_v1 import (
    Capability,
    EffectClass,
    FederationCapabilityManifest,
    MobileRequest,
    Mode,
    route_request,
    validate_manifest,
)


class FuseMobileGatewayTests(unittest.TestCase):
    def manifest(self, *caps):
        return FederationCapabilityManifest(
            subject="owner:kim",
            issued_at="2026-09-08T03:52:40+02:00",
            expires_at="2026-09-08T04:52:40+02:00",
            capabilities=tuple(caps),
            source_scopes=("KDV", "DRIVE"),
            model_scopes=("AUTO",),
            policies={"external_effects": "OWNER_GATED"},
        )

    def test_manifest_has_no_secret_material(self):
        self.assertEqual(validate_manifest(self.manifest()), [])

    def test_research_route_is_internal_and_proof_aware(self):
        decision = route_request(MobileRequest("research this", mode=Mode.RESEARCH), self.manifest())
        self.assertTrue(decision.effect_allowed)
        self.assertFalse(decision.owner_gate_required)
        self.assertIn("KDV", decision.components)
        self.assertIn("CFBE", decision.components)

    def test_openrouter_uses_existing_mesh_when_capability_is_live(self):
        manifest = self.manifest(Capability("OPENROUTER-PROCESSOR-MESH", "MODEL_ROUTER", "existing", health="HEALTHY"))
        decision = route_request(
            MobileRequest("compare models", requested_models=("openrouter:auto",)), manifest
        )
        self.assertIn("sovara.creative.openrouter_processor_mesh", decision.components)

    def test_openrouter_falls_back_when_not_live(self):
        decision = route_request(
            MobileRequest("compare models", requested_models=("openrouter:auto",)), self.manifest()
        )
        self.assertIn("PROVIDER_FALLBACK", decision.components)

    def test_consequential_effect_is_owner_gated(self):
        decision = route_request(
            MobileRequest("send this", mode=Mode.EXECUTE, effect_class=EffectClass.EXTERNAL_COMMUNICATION),
            self.manifest(),
        )
        self.assertFalse(decision.effect_allowed)
        self.assertTrue(decision.owner_gate_required)
        self.assertEqual(decision.strategy, "OWNER_GATED")


if __name__ == "__main__":
    unittest.main()
