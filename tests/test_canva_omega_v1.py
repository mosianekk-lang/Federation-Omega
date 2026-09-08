import unittest

from federation.canva_omega_v1 import (
    AuthorityClass,
    CanvaOmegaVisualIntelligence,
    PrivacyClass,
    ProofState,
    VisualMission,
    VisualProjectionPacket,
    VisualSurface,
)


class CanvaOmegaV1Tests(unittest.TestCase):
    def packet(self, **overrides):
        data = {
            "system_id": "FUSE",
            "source_refs": ("github:sha:example",),
            "claims": ("Mission state is source-implemented.",),
            "proof_state": ProofState.I1,
            "authority": AuthorityClass.A1_INTERNAL,
            "privacy": PrivacyClass.P1_INTERNAL,
            "freshness": "CURRENT",
            "registered_system": True,
        }
        data.update(overrides)
        return VisualProjectionPacket(**data)

    def test_bible_routes_to_visual_family(self):
        plan = CanvaOmegaVisualIntelligence.compile(
            VisualMission(
                objective="Create a complete illustrated Bible knowledge atlas and architecture system",
                audience="owner and expert readers",
                packets=(self.packet(system_id="OMEGA-SCIENTIA"),),
            )
        )
        self.assertIn(VisualSurface.VISUAL_ATLAS, plan.surfaces)
        self.assertIn(VisualSurface.PRESENTATION, plan.surfaces)
        self.assertIn(VisualSurface.DESIGN_SYSTEM, plan.surfaces)
        self.assertIn("knowledge_atlas", plan.visual_primitives)
        self.assertFalse(plan.release_blocked)

    def test_future_registered_system_is_supported(self):
        plan = CanvaOmegaVisualIntelligence.compile(
            VisualMission(
                objective="Visualise a future Federation service architecture",
                audience="engineering",
                packets=(
                    self.packet(
                        system_id="FUTURE-FEDERATION-SERVICE-9000",
                        source_refs=("registry:future-service-9000",),
                    ),
                ),
            )
        )
        self.assertIn("FUTURE-FEDERATION-SERVICE-9000", plan.source_systems)

    def test_unregistered_system_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "UNREGISTERED_SYSTEM_PACKET"):
            CanvaOmegaVisualIntelligence.compile(
                VisualMission(
                    objective="Visualise unregistered state",
                    audience="internal",
                    packets=(self.packet(registered_system=False),),
                )
            )

    def test_missing_provenance_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "MISSING_SOURCE_PROVENANCE"):
            CanvaOmegaVisualIntelligence.compile(
                VisualMission(
                    objective="Visualise evidence",
                    audience="internal",
                    packets=(self.packet(source_refs=()),),
                )
            )

    def test_canva_cannot_be_canonical_truth_store(self):
        with self.assertRaisesRegex(ValueError, "CANVA_CANNOT_BE_CANONICAL_TRUTH_STORE"):
            CanvaOmegaVisualIntelligence.compile(
                VisualMission(
                    objective="Visualise Canva design state",
                    audience="internal",
                    packets=(
                        self.packet(
                            system_id="CANVA",
                            canonical_source=True,
                            source_refs=("canva:design:test",),
                        ),
                    ),
                )
            )

    def test_confidential_external_release_is_blocked(self):
        plan = CanvaOmegaVisualIntelligence.compile(
            VisualMission(
                objective="Create a public evidence presentation",
                audience="external",
                packets=(self.packet(privacy=PrivacyClass.P3_PRIVILEGED),),
                allow_external_release=True,
            )
        )
        self.assertTrue(plan.release_blocked)
        self.assertTrue(any(reason.startswith("PRIVACY_BLOCK") for reason in plan.release_reasons))

    def test_owner_gated_external_release_is_blocked(self):
        plan = CanvaOmegaVisualIntelligence.compile(
            VisualMission(
                objective="Create a publication-ready strategic presentation",
                audience="external",
                packets=(
                    self.packet(
                        authority=AuthorityClass.A2_CONSEQUENTIAL,
                        owner_gate=True,
                    ),
                ),
                allow_external_release=True,
            )
        )
        self.assertTrue(plan.release_blocked)
        self.assertTrue(
            any(reason.startswith("OWNER_APPROVAL_REQUIRED") for reason in plan.release_reasons)
        )

    def test_freshness_qualifier_is_preserved(self):
        plan = CanvaOmegaVisualIntelligence.compile(
            VisualMission(
                objective="Create a current platform status infographic",
                audience="internal",
                packets=(self.packet(freshness="STALE_READBACK"),),
            )
        )
        self.assertIn("FRESHNESS_QUALIFIER:FUSE:STALE_READBACK", plan.warnings)

    def test_visual_polish_warning_is_always_present(self):
        plan = CanvaOmegaVisualIntelligence.compile(
            VisualMission(
                objective="Create a capability maturity diagram",
                audience="internal",
                packets=(self.packet(proof_state=ProofState.D0),),
            )
        )
        self.assertIn("VISUAL_POLISH_MUST_NOT_STRENGTHEN_EPISTEMIC_STATE", plan.warnings)
        self.assertIn("maturity_ladder", plan.visual_primitives)


if __name__ == "__main__":
    unittest.main()
