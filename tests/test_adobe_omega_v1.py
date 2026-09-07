import unittest

from federation.adobe_omega_v1 import (
    ADOBE_OMEGA_CAPABILITIES,
    BACKENDS,
    AdobeOmegaRouter,
    BackendSnapshot,
    BackendState,
    CapabilityFamily,
    CapabilityMode,
    ProofLevel,
    ProofReceipt,
    RouteRequest,
    capability_family_counts,
    parity_report,
    probe_local_backends,
    validate_registry,
)


def snap(
    backend_id,
    state,
    *,
    installed=True,
    license_accepted=True,
    semantic=False,
    proof=ProofLevel.DISCOVERED,
):
    return BackendSnapshot(
        backend_id=backend_id,
        state=state,
        installed=installed,
        license_accepted=license_accepted,
        semantic_readback_verified=semantic,
        proof_level=proof,
    )


class AdobeOmegaV1Tests(unittest.TestCase):
    def test_registry_is_valid_and_broad(self):
        validate_registry()
        self.assertGreaterEqual(len(ADOBE_OMEGA_CAPABILITIES), 65)
        counts = capability_family_counts()
        self.assertEqual(set(counts), {family.value for family in CapabilityFamily})
        self.assertTrue(all(value > 0 for value in counts.values()))

    def test_each_capability_has_proof_contract_and_benchmark(self):
        for capability in ADOBE_OMEGA_CAPABILITIES.values():
            self.assertTrue(capability.proof_contract)
            self.assertTrue(capability.public_benchmark)

    def test_local_first_route_beats_healthy_provider(self):
        router = AdobeOmegaRouter()
        snapshots = {
            "LOCAL_PDF": snap(
                "LOCAL_PDF",
                BackendState.VERIFIED_OPERATIONAL,
                semantic=True,
                proof=ProofLevel.SEMANTIC_READBACK,
            ),
            "ADOBE_ACROBAT_NATIVE": snap(
                "ADOBE_ACROBAT_NATIVE",
                BackendState.VERIFIED_OPERATIONAL,
                semantic=True,
                proof=ProofLevel.SEMANTIC_READBACK,
            ),
            "ADOBE_UNIFIED_NATIVE": snap(
                "ADOBE_UNIFIED_NATIVE",
                BackendState.VERIFIED_OPERATIONAL,
                semantic=True,
                proof=ProofLevel.SEMANTIC_READBACK,
            ),
        }
        decision = router.route(RouteRequest("pdf.properties"), snapshots)
        self.assertEqual(decision.selected_backend, "LOCAL_PDF")
        self.assertEqual(decision.mode, "SOVEREIGN_LOCAL")

    def test_provider_circuit_hold_is_never_selected(self):
        router = AdobeOmegaRouter()
        decision = router.route(
            RouteRequest("layer.document_manifest"),
            {
                "ADOBE_UNIFIED_NATIVE": snap(
                    "ADOBE_UNIFIED_NATIVE", BackendState.CIRCUIT_HELD
                )
            },
        )
        self.assertIsNone(decision.selected_backend)
        self.assertEqual(decision.mode, "BUILD_REQUIRED")
        self.assertTrue(any(reason == "STATE_CIRCUIT_HELD" for _, reason in decision.rejected))

    def test_read_only_backend_can_read_but_cannot_write(self):
        router = AdobeOmegaRouter()
        snapshots = {
            "ADOBE_EXPRESS_NATIVE": snap(
                "ADOBE_EXPRESS_NATIVE", BackendState.READ_ONLY
            )
        }
        read_decision = router.route(RouteRequest("design.template_search"), snapshots)
        write_decision = router.route(RouteRequest("design.fill_text"), snapshots)
        self.assertEqual(read_decision.selected_backend, "ADOBE_EXPRESS_NATIVE")
        self.assertIsNone(write_decision.selected_backend)
        self.assertTrue(
            any(reason == "STATE_READ_ONLY" for _, reason in write_decision.rejected)
        )

    def test_license_gate_blocks_generative_backend(self):
        router = AdobeOmegaRouter()
        decision = router.route(
            RouteRequest("gen.image", allow_provider=False),
            {
                "LOCAL_GENERATIVE": snap(
                    "LOCAL_GENERATIVE",
                    BackendState.AVAILABLE_UNVERIFIED,
                    license_accepted=False,
                ),
                "FEDERATION_IMAGE_PROVIDER": snap(
                    "FEDERATION_IMAGE_PROVIDER",
                    BackendState.AVAILABLE_UNVERIFIED,
                    license_accepted=False,
                ),
            },
        )
        self.assertIsNone(decision.selected_backend)
        self.assertTrue(any(reason == "LICENSE_NOT_ADMITTED" for _, reason in decision.rejected))

    def test_unknown_or_unavailable_route_creates_typed_build_gap(self):
        router = AdobeOmegaRouter()
        decision = router.route(RouteRequest("video.render_export"), {})
        self.assertIsNone(decision.selected_backend)
        self.assertEqual(decision.open_builds, ("BUILD-AO-011:video.render_export",))

    def test_semantic_readback_gate_rejects_discovery_only_backend(self):
        router = AdobeOmegaRouter()
        decision = router.route(
            RouteRequest("image.resize_crop", require_semantic_readback=True),
            {
                "LOCAL_RASTER": snap(
                    "LOCAL_RASTER", BackendState.AVAILABLE_UNVERIFIED, semantic=False
                )
            },
        )
        self.assertIsNone(decision.selected_backend)
        self.assertTrue(
            any(reason == "SEMANTIC_READBACK_REQUIRED" for _, reason in decision.rejected)
        )

    def test_probe_never_promotes_dependency_presence_to_verified(self):
        def fake_which(name):
            return f"/usr/bin/{name}" if name == "qpdf" else None

        def fake_find_spec(name):
            return None

        snapshots = probe_local_backends(which=fake_which, find_spec=fake_find_spec)
        self.assertEqual(snapshots["LOCAL_PDF"].state, BackendState.AVAILABLE_UNVERIFIED)
        self.assertFalse(snapshots["LOCAL_PDF"].semantic_readback_verified)
        self.assertEqual(snapshots["LOCAL_PDF"].proof_level, ProofLevel.DISCOVERED)

    def test_probe_holds_generative_backend_until_license_admitted(self):
        def fake_which(name):
            return None

        class Module:
            pass

        def fake_find_spec(name):
            return Module() if name == "diffusers" else None

        snapshots = probe_local_backends(which=fake_which, find_spec=fake_find_spec)
        self.assertEqual(snapshots["LOCAL_GENERATIVE"].state, BackendState.LICENSE_HELD)

        admitted = probe_local_backends(
            which=fake_which,
            find_spec=fake_find_spec,
            license_acceptance={"LOCAL_GENERATIVE"},
        )
        self.assertEqual(
            admitted["LOCAL_GENERATIVE"].state, BackendState.AVAILABLE_UNVERIFIED
        )

    def test_proof_receipt_semantic_level_requires_semantic_readback(self):
        with self.assertRaises(ValueError):
            ProofReceipt.issue(
                capability_id="pdf.properties",
                backend_id="LOCAL_PDF",
                proof_level=ProofLevel.SEMANTIC_READBACK,
                semantic_readback_verified=False,
                evidence_refs=("test",),
                outcome={"page_count": 1},
            )

    def test_proof_receipt_is_deterministic(self):
        kwargs = dict(
            capability_id="pdf.properties",
            backend_id="LOCAL_PDF",
            proof_level=ProofLevel.SEMANTIC_READBACK,
            semantic_readback_verified=True,
            evidence_refs=("fixture:1",),
            outcome={"page_count": 1, "encrypted": False},
        )
        a = ProofReceipt.issue(**kwargs)
        b = ProofReceipt.issue(**kwargs)
        self.assertEqual(a.outcome_fingerprint, b.outcome_fingerprint)

    def test_parity_never_claims_full_from_installed_or_read_only_states(self):
        snapshots = {
            backend_id: snap(
                backend_id,
                BackendState.AVAILABLE_UNVERIFIED,
                semantic=False,
                license_accepted=True,
            )
            for backend_id in BACKENDS
        }
        report = parity_report(snapshots)
        self.assertFalse(report["full_parity"])
        self.assertEqual(report["semantic_verified_capabilities"], 0)
        self.assertEqual(
            len(report["gap_capabilities"]), report["total_capabilities"]
        )

    def test_provider_can_be_disabled_per_request(self):
        router = AdobeOmegaRouter()
        snapshots = {
            "ADOBE_ACROBAT_NATIVE": snap(
                "ADOBE_ACROBAT_NATIVE",
                BackendState.VERIFIED_OPERATIONAL,
                semantic=True,
                proof=ProofLevel.SEMANTIC_READBACK,
            )
        }
        decision = router.route(
            RouteRequest("pdf.properties", allow_provider=False), snapshots
        )
        self.assertIsNone(decision.selected_backend)
        self.assertTrue(
            any(reason == "PROVIDER_DISABLED_BY_REQUEST" for _, reason in decision.rejected)
        )

    def test_design_write_mode_is_not_read(self):
        self.assertIs(
            ADOBE_OMEGA_CAPABILITIES["design.fill_text"].mode, CapabilityMode.MANAGE
        )


if __name__ == "__main__":
    unittest.main()
