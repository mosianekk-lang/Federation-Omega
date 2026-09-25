import unittest

from benchmarking.cfbe_omega.production_genesis_v1 import (
    MaturityStage,
    ProofKey,
    compile_production_genome,
    evaluate_readiness,
)
from federation.fuse_one_commercial_closure_v1 import (
    CommercialClosureInput,
    OWNER_INTENT_HASH,
    PRODUCT_ID,
    canonical_product_contract,
    compile_commercial_closure,
)
from federation.product_release_factory_v1 import (
    ProductReleaseInput,
    compile_product_release_bundle,
    release_gate,
)


class FuseOneCommercialClosureTests(unittest.TestCase):
    @staticmethod
    def _release_bundle():
        contract = canonical_product_contract()
        return compile_product_release_bundle(
            ProductReleaseInput(
                product_id=PRODUCT_ID,
                product_contract_fingerprint=contract.fingerprint,
                version="0.1.0-candidate",
                executable_entrypoints=(
                    "fuse-one-desktop.exe",
                    "fuse-one-cli.exe",
                ),
                website_routes=("/", "/download", "/docs", "/trust", "/status"),
                installer_targets=("MSIX_USER", "ZIP_PORTABLE"),
            )
        )

    def test_canonical_product_contract_is_commercially_bounded_and_stable(self):
        contract = canonical_product_contract()
        self.assertEqual(PRODUCT_ID, contract.product_id)
        self.assertEqual(64, len(OWNER_INTENT_HASH))
        self.assertIn("INSTALL_WITHOUT_ADMIN_ON_WINDOWS", contract.user_journeys)
        self.assertIn("LOCAL_OFFLINE_CORE", contract.required_outcomes)
        self.assertIn("PROVIDER_NEUTRAL_ROUTING", contract.required_outcomes)
        self.assertIn("OWNER_CUSTOMER_VALUE_MEASURED", contract.required_outcomes)

    def test_existing_production_genesis_contract_is_exercised(self):
        contract = canonical_product_contract()
        genome = compile_production_genome(contract)
        self.assertEqual(20, len(genome.systems))
        self.assertEqual(
            MaturityStage.PRODUCT_CONTRACTED,
            evaluate_readiness((ProofKey.PRODUCT_CONTRACT,)).stage,
        )

    def test_existing_product_release_contract_is_exercised(self):
        bundle = self._release_bundle()
        self.assertEqual(12, len(bundle.components))
        self.assertEqual(
            "HOLD",
            release_gate(bundle, ("WEBSITE_DEPLOYED_READBACK",))["status"],
        )
        self.assertEqual(
            "RELEASE_READY",
            release_gate(bundle, bundle.required_terminal_proofs)["status"],
        )

    def test_source_only_state_cannot_false_promote_to_commercial_release(self):
        report = compile_commercial_closure(
            CommercialClosureInput(
                observed_proofs=(
                    ProofKey.PRODUCT_CONTRACT.value,
                    ProofKey.SYSTEM_GENOME.value,
                    ProofKey.ARCHITECTURE.value,
                    ProofKey.SOURCE.value,
                ),
            )
        )
        self.assertEqual("COMMERCIAL_CLOSURE_IN_PROGRESS", report.commercial_state)
        self.assertEqual("HOLD", report.release_status)
        self.assertFalse(report.provider_effect_authorized)

    def test_deterministic_test_state_is_not_runtime_or_value_proof(self):
        proofs = tuple(
            key.value
            for key in (
                ProofKey.PRODUCT_CONTRACT,
                ProofKey.SYSTEM_GENOME,
                ProofKey.ARCHITECTURE,
                ProofKey.SOURCE,
                ProofKey.UNIT_TESTS,
                ProofKey.INTEGRATION_TESTS,
                ProofKey.CONTRACT_TESTS,
                ProofKey.SECURITY_TESTS,
                ProofKey.PERFORMANCE_TESTS,
            )
        )
        report = compile_commercial_closure(
            CommercialClosureInput(observed_proofs=proofs)
        )
        self.assertEqual(MaturityStage.DETERMINISTIC_TESTED.name, report.maturity_stage)
        self.assertEqual("COMMERCIAL_BUILD_VALIDATED", report.commercial_state)
        self.assertNotEqual("READY_FOR_PROGRESSIVE_GO_LIVE", report.go_live_status)

    def test_hypercube_compiles_every_canonical_project_bottleneck(self):
        report = compile_commercial_closure(CommercialClosureInput())
        self.assertEqual(5, len(report.hypercube_resolution_receipts))
        self.assertTrue(all(len(item) == 64 for item in report.hypercube_resolution_receipts))
        self.assertIn("Windows non-admin install", report.commercial_features)
        self.assertIn("durable resumable missions", report.commercial_features)
        self.assertTrue(
            any(action.startswith("HYPERCUBE_RESOLVE:") for action in report.next_actions)
        )

    def test_unknown_proof_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "FUSE_COMMERCIAL_UNKNOWN_PROOF"):
            compile_commercial_closure(
                CommercialClosureInput(observed_proofs=("MADE_UP_PROOF",))
            )

    def test_report_is_deterministic_for_identical_inputs(self):
        request = CommercialClosureInput()
        self.assertEqual(
            compile_commercial_closure(request).receipt_sha256,
            compile_commercial_closure(request).receipt_sha256,
        )

    def test_release_factory_targets_user_installable_windows_distribution(self):
        bundle = self._release_bundle()
        installer = next(c for c in bundle.components if c.kind == "INSTALLER")
        self.assertIn("MSIX_USER", installer.contract["targets"])
        self.assertIn("ZIP_PORTABLE", installer.contract["targets"])
        self.assertEqual("REQUIRED_BEFORE_RELEASE", installer.contract["signing"])

    def test_even_all_product_release_proofs_do_not_replace_value_maturity(self):
        report = compile_commercial_closure(
            CommercialClosureInput(
                release_terminal_proofs=(
                    "WEBSITE_DEPLOYED_READBACK",
                    "INSTALLER_SIGNED",
                    "CLEAN_INSTALL_VERIFIED",
                    "UPGRADE_VERIFIED",
                    "UNINSTALL_VERIFIED",
                    "SECURE_UPDATE_VERIFIED",
                    "TENANT_ISOLATION_VERIFIED",
                    "AUTH_VERIFIED",
                    "RECOVERY_VERIFIED",
                    "SUPPLY_CHAIN_VERIFIED",
                    "TRUST_CENTER_CLAIMS_CURRENT",
                    "OWNER_VALUE_VERIFIED",
                ),
            )
        )
        self.assertEqual("RELEASE_READY", report.release_status)
        self.assertNotEqual("COMMERCIAL_RELEASE_READY", report.commercial_state)

    def test_full_synthetic_proof_vector_reaches_release_ready_only_with_all_gates(self):
        report = compile_commercial_closure(
            CommercialClosureInput(
                observed_proofs=tuple(item.value for item in ProofKey),
                release_terminal_proofs=(
                    "WEBSITE_DEPLOYED_READBACK",
                    "INSTALLER_SIGNED",
                    "CLEAN_INSTALL_VERIFIED",
                    "UPGRADE_VERIFIED",
                    "UNINSTALL_VERIFIED",
                    "SECURE_UPDATE_VERIFIED",
                    "TENANT_ISOLATION_VERIFIED",
                    "AUTH_VERIFIED",
                    "RECOVERY_VERIFIED",
                    "SUPPLY_CHAIN_VERIFIED",
                    "TRUST_CENTER_CLAIMS_CURRENT",
                    "OWNER_VALUE_VERIFIED",
                ),
                exact_effect_authority=True,
                rollback_verified=True,
                semantic_canary_defined=True,
            )
        )
        self.assertEqual(MaturityStage.VALUE_VERIFIED.name, report.maturity_stage)
        self.assertEqual("READY_FOR_PROGRESSIVE_GO_LIVE", report.go_live_status)
        self.assertEqual("RELEASE_READY", report.release_status)
        self.assertEqual("COMMERCIAL_RELEASE_READY", report.commercial_state)


if __name__ == "__main__":
    unittest.main()
