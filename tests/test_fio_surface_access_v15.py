import unittest

from federation.fio_surface_access import (
    SurfaceAction,
    SurfaceAttestation,
    SurfaceManifest,
    SurfaceRegistry,
    SurfaceClass,
    SurfaceMode,
    SovaraDerivedSurfaceRouter,
    default_kdv_surface_manifests,
)


class FIOSurfaceAccessV15Tests(unittest.TestCase):
    def setUp(self):
        self.registry = SurfaceRegistry(default_kdv_surface_manifests())
        self.router = SovaraDerivedSurfaceRouter(self.registry)

    def att(self, surface, *, direct=True, fallback=False, read=True, write=True, readback=True, fresh=True, authority="A1_INTERNAL"):
        return SurfaceAttestation(
            surface_id=surface,
            present=True,
            direct_route_live=direct,
            fallback_route_live=fallback,
            read_capable=read,
            write_capable=write,
            semantic_readback_ready=readback,
            fresh=fresh,
            proof_refs=(f"proof:{surface}",),
            observed_at="2026-09-05T05:55:00+02:00",
            current_authority=authority,
        )

    def test_safe_read_auto_routes_on_current_direct_surface(self):
        action = SurfaceAction("a1", "GOOGLE_DRIVE", "READ")
        decision = self.router.route(action, (self.att("GOOGLE_DRIVE"),))
        self.assertEqual(decision.state, "AUTO_ROUTE_SAFE_INTERNAL")
        self.assertTrue(decision.auto_execute_internal)
        self.assertEqual(decision.selected_adapter, "GOOGLE_DRIVE_CONNECTOR")

    def test_safe_internal_write_auto_routes_when_write_is_proven(self):
        action = SurfaceAction("a2", "KDV", "WRITE", requested_authority="A1_INTERNAL")
        decision = self.router.route(action, (self.att("KDV"),))
        self.assertTrue(decision.auto_execute_internal)
        self.assertEqual(decision.mode, SurfaceMode.SAFE_INTERNAL)

    def test_external_effect_is_never_executed_by_fio(self):
        action = SurfaceAction(
            "a3", "GOOGLE_CLOUD", "DEPLOY",
            requested_authority="PROVIDER_ACTION",
            external_effect=True,
            effect_class="DEPLOYMENT",
            authorization_ref="HMC:DEPLOY:1",
            rollback_required=True,
        )
        decision = self.router.route(action, (self.att("GOOGLE_CLOUD", authority="PROVIDER_ACTION"),))
        self.assertTrue(decision.delegate_to_sovara)
        self.assertFalse(decision.auto_execute_internal)
        self.assertEqual(decision.state, "DELEGATE_TO_SOVARA")

    def test_external_effect_without_exact_authorization_is_held(self):
        action = SurfaceAction(
            "a4", "GOOGLE_CLOUD", "DEPLOY",
            requested_authority="PROVIDER_ACTION",
            external_effect=True,
            effect_class="DEPLOYMENT",
            rollback_required=True,
        )
        decision = self.router.route(action, (self.att("GOOGLE_CLOUD", authority="PROVIDER_ACTION"),))
        self.assertEqual(decision.state, "SOVARA_PREFLIGHT_HELD")
        self.assertIn("EXACT_AUTHORIZATION_REF_REQUIRED", decision.reasons)

    def test_communication_send_requires_explicit_owner_directive(self):
        action = SurfaceAction(
            "a5", "GMAIL", "SEND",
            requested_authority="A2_REVERSIBLE_EXTERNAL",
            external_effect=True,
            effect_class="EMAIL_SEND",
            authorization_ref="HMC:MAIL:1",
            rollback_required=True,
            communication_send=True,
            explicit_owner_directive=False,
        )
        decision = self.router.route(action, (self.att("GMAIL", authority="A2_REVERSIBLE_EXTERNAL"),))
        self.assertEqual(decision.state, "EXPLICIT_OWNER_DIRECTIVE_REQUIRED")
        self.assertTrue(decision.human_required)

    def test_explicit_email_send_still_delegates_to_sovara(self):
        action = SurfaceAction(
            "a6", "GMAIL", "SEND",
            requested_authority="A2_REVERSIBLE_EXTERNAL",
            external_effect=True,
            effect_class="EMAIL_SEND",
            authorization_ref="OWNER:EXPLICIT:MAIL",
            rollback_required=True,
            communication_send=True,
            explicit_owner_directive=True,
        )
        decision = self.router.route(action, (self.att("GMAIL", authority="A2_REVERSIBLE_EXTERNAL"),))
        self.assertTrue(decision.delegate_to_sovara)
        self.assertEqual(decision.state, "DELEGATE_TO_SOVARA")

    def test_unknown_surface_auto_enrolls_read_only_shadow(self):
        action = SurfaceAction("a7", "FUTURE_SURFACE", "DISCOVER")
        decision = self.router.route(action, ())
        self.assertEqual(decision.state, "DISCOVERED_READ_ONLY_SHADOW")
        self.assertEqual(decision.mode, SurfaceMode.READ_ONLY)
        self.assertFalse(decision.auto_execute_internal)

    def test_stale_surface_downgrades_before_effect(self):
        action = SurfaceAction("a8", "GOOGLE_DRIVE", "READ")
        decision = self.router.route(action, (self.att("GOOGLE_DRIVE", fresh=False),))
        self.assertEqual(decision.state, "SURFACE_STALE_DOWNGRADED")
        self.assertEqual(decision.mode, SurfaceMode.READ_ONLY)

    def test_direct_route_preferred_over_fallback(self):
        action = SurfaceAction("a9", "GOOGLE_DRIVE", "READ")
        decision = self.router.route(action, (self.att("GOOGLE_DRIVE", direct=True, fallback=True),))
        self.assertEqual(decision.selected_adapter, "GOOGLE_DRIVE_CONNECTOR")

    def test_fallback_route_used_when_direct_unavailable(self):
        action = SurfaceAction("a10", "GOOGLE_DRIVE", "READ")
        decision = self.router.route(action, (self.att("GOOGLE_DRIVE", direct=False, fallback=True),))
        self.assertEqual(decision.selected_adapter, "APPS_SCRIPT_TRANSPORT")

    def test_write_requires_current_write_proof(self):
        action = SurfaceAction("a11", "KDV", "WRITE", requested_authority="A1_INTERNAL")
        decision = self.router.route(action, (self.att("KDV", write=False),))
        self.assertEqual(decision.state, "SURFACE_WRITE_NOT_PROVEN")
        self.assertFalse(decision.auto_execute_internal)

    def test_semantic_readback_required_for_safe_auto_route(self):
        action = SurfaceAction("a12", "GOOGLE_DRIVE", "READ")
        decision = self.router.route(action, (self.att("GOOGLE_DRIVE", readback=False),))
        self.assertEqual(decision.state, "SEMANTIC_READBACK_NOT_READY")

    def test_authority_above_surface_ceiling_is_held(self):
        action = SurfaceAction("a13", "CANVA", "READ", requested_authority="A3_CONSEQUENTIAL")
        decision = self.router.route(action, (self.att("CANVA"),))
        self.assertEqual(decision.state, "SURFACE_AUTHORITY_CEILING_HELD")

    def test_irreversible_action_requires_human_and_sovara(self):
        action = SurfaceAction(
            "a14", "GOOGLE_DRIVE", "WRITE",
            requested_authority="A2_REVERSIBLE_EXTERNAL",
            external_effect=True,
            effect_class="IRREVERSIBLE_DELETE",
            authorization_ref="HMC:DELETE:1",
            irreversible=True,
        )
        decision = self.router.route(action, (self.att("GOOGLE_DRIVE", authority="A2_REVERSIBLE_EXTERNAL"),))
        self.assertTrue(decision.delegate_to_sovara)
        self.assertTrue(decision.human_required)
        self.assertIn("IRREVERSIBLE_ACTION_HUMAN_REQUIRED", decision.reasons)

    def test_security_or_credential_effect_is_not_internal_auto_execution(self):
        action = SurfaceAction(
            "a15", "OPENAI_PLATFORM", "KEY_SETUP",
            requested_authority="PROVIDER_ACTION",
            external_effect=True,
            effect_class="CREDENTIAL_CREATE",
            authorization_ref="HMC:KEY:1",
            rollback_required=True,
            security_or_credential_effect=True,
        )
        decision = self.router.route(action, (self.att("OPENAI_PLATFORM", authority="PROVIDER_ACTION"),))
        self.assertTrue(decision.delegate_to_sovara)
        self.assertFalse(decision.auto_execute_internal)

    def test_one_failed_surface_does_not_stall_independent_surface(self):
        actions = (
            SurfaceAction("blocked", "GOOGLE_CLOUD", "READ"),
            SurfaceAction("safe", "GOOGLE_DRIVE", "READ"),
        )
        attestations = (
            SurfaceAttestation("GOOGLE_CLOUD", True, False, False, False, False, False, True, ("proof:gcp",), "now"),
            self.att("GOOGLE_DRIVE"),
        )
        decisions = self.router.route_batch(actions, attestations)
        self.assertEqual(decisions[0].state, "NO_LIVE_SURFACE_ROUTE")
        self.assertEqual(decisions[1].state, "AUTO_ROUTE_SAFE_INTERNAL")

    def test_surface_attestation_requires_proof(self):
        item = SurfaceAttestation("GOOGLE_DRIVE", True, True, False, True, True, True, True, (), "now")
        with self.assertRaisesRegex(ValueError, "SURFACE_ATTESTATION_PROOF_REQUIRED"):
            item.validate()

    def test_write_cannot_exist_without_read_capability(self):
        item = SurfaceAttestation("GOOGLE_DRIVE", True, True, False, False, True, True, True, ("proof",), "now")
        with self.assertRaisesRegex(ValueError, "SURFACE_WRITE_REQUIRES_READ_CAPABILITY"):
            item.validate()

    def test_manifest_cannot_default_external_effects_on(self):
        item = SurfaceManifest("x", "X", SurfaceClass.OTHER, ("READ",), external_effect_default=True)
        with self.assertRaisesRegex(ValueError, "SURFACE_EXTERNAL_EFFECT_DEFAULT_PROHIBITED"):
            item.validate()

    def test_route_decision_fingerprint_is_deterministic(self):
        action = SurfaceAction("fp", "GOOGLE_DRIVE", "READ")
        att = (self.att("GOOGLE_DRIVE"),)
        self.assertEqual(self.router.route(action, att).fingerprint, self.router.route(action, att).fingerprint)


if __name__ == "__main__":
    unittest.main()
