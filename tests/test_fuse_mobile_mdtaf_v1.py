from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from proofos_omega import ImpactCompiler, ProofPolicy, ProofSelector


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "mobile" / "fuse-mobile" / "lab"
CONTRACT = ROOT / "governance" / "fuse_mobile_mdtaf_v1.json"
WORKFLOW = ROOT / ".github" / "workflows" / "fuse-mobile-android-build.yml"
AIRLOCK_POLICY = ROOT / "governance" / "github_airlock_policy.json"
PROOFOS_POLICY = ROOT / "governance" / "proofos_omega_policy_v1.json"
APK_SHA = "a" * 64


class FuseMobileMdtafContractTests(unittest.TestCase):
    def _valid_smoke(self) -> dict[str, object]:
        return {
            "schema": "FUSE_MOBILE_MDTAF_SMOKE_RECEIPT_V1",
            "state": "ANDROID_SMOKE_PASS",
            "apk_sha256": APK_SHA,
            "install_state": "PASS",
            "first_launch_state": "PASS",
            "relaunch_state": "PASS",
            "network_baseline_state": "PASS",
            "connectivity_loss_state": "PASS",
            "offline_launch_state": "PASS",
            "network_recovery_state": "PASS",
            "recovery_launch_state": "PASS",
            "fatal_or_anr_hits": [],
        }

    def _valid_security(self) -> dict[str, object]:
        return {
            "schema": "FUSE_MOBILE_APK_SECURITY_SCAN_V1",
            "state": "APK_CREDENTIAL_SCAN_CLEAN",
            "apk_sha256": APK_SHA,
            "matches": [],
        }

    def _run_certificate(
        self,
        *,
        smoke: dict[str, object] | None = None,
        security: dict[str, object] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence"
            evidence.mkdir()
            (evidence / "smoke-receipt.json").write_text(
                json.dumps(smoke if smoke is not None else self._valid_smoke()),
                encoding="utf-8",
            )
            (evidence / "apk-security-scan.json").write_text(
                json.dumps(security if security is not None else self._valid_security()),
                encoding="utf-8",
            )
            output = Path(tmp) / "certificate.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(LAB / "certify.py"),
                    "--evidence-dir",
                    str(evidence),
                    "--output",
                    str(output),
                    "--source-sha",
                    "f" * 40,
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertTrue(output.is_file(), proc.stderr or proc.stdout)
            certificate = json.loads(output.read_text(encoding="utf-8"))
            return proc, certificate

    def test_permanent_contract_is_truth_bounded(self) -> None:
        data = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "FUSE-MOBILE-MDTAF-V1")
        self.assertEqual(data["version"], "1.2.0")
        self.assertEqual(data["authority_ceiling"], "A1_INTERNAL")
        self.assertFalse(data["external_effect_default"])
        self.assertTrue(data["truth_boundary"]["source_is_not_runtime"])
        self.assertTrue(data["truth_boundary"]["virtual_device_is_not_physical_device"])
        self.assertTrue(data["truth_boundary"]["owner_device_profile_uses_progressive_fidelity"])
        self.assertTrue(data["truth_boundary"]["consent_bound_real_data_is_allowed_when_material"])
        self.assertTrue(data["truth_boundary"]["live_secret_clone_is_prohibited"])
        self.assertTrue(data["truth_boundary"]["offline_process_survival_alone_is_not_offline_proof"])
        self.assertTrue(data["truth_boundary"]["security_receipt_must_match_exercised_apk_hash"])
        self.assertFalse(data["owner_reference_device"]["public_source_storage_allowed"])
        self.assertEqual(data["owner_reference_device"]["secret_boundary"]["clone_into_twin"], False)
        self.assertIn("L4_CONSENT_BOUND_REAL_DATA_LAB", data["owner_reference_device"]["fidelity_ladder"])
        self.assertIn("installed_application_inventory", data["owner_reference_device"]["l2_behavioral_ecology_twin"])
        self.assertIn("selected_real_messages", data["owner_reference_device"]["l4_consent_bound_real_data_lab"])
        gates = set(data["minimum_release_gates"])
        self.assertIn("APK_SECURITY_SMOKE_HASH_MATCH", gates)
        self.assertIn("OFFLINE_FAULT_INJECTION_VERIFIED", gates)
        self.assertIn("NETWORK_RECOVERY_PASS", gates)
        self.assertIn("RECOVERY_RELAUNCH_PASS", gates)

    def test_owner_capture_supports_progressive_real_world_fidelity(self) -> None:
        source = (LAB / "capture_owner_device.py").read_text(encoding="utf-8")
        self.assertIn("--fidelity-level", source)
        self.assertIn("--include-system-packages", source)
        self.assertIn("--include-literal-identifiers", source)
        self.assertIn("--real-content-sample", source)
        self.assertIn("--acknowledge-sensitive-capture", source)
        self.assertIn('"pm", "list", "packages"', source)
        self.assertIn('"dumpsys", "account"', source)
        self.assertIn('"content", "query"', source)
        self.assertIn('"dumpsys", "iphonesubinfo"', source)
        self.assertIn('"credentials_or_tokens_captured": False', source)
        self.assertIn('"live_secret_clone_allowed": False', source)
        self.assertIn("Sensitive Level-4 capture requires", source)

    def test_proofos_maps_mdtaf_to_bounded_court_without_global_fallback(self) -> None:
        policy = ProofPolicy.from_path(PROOFOS_POLICY)
        paths = [
            "mobile/fuse-mobile/lab/capture_owner_device.py",
            "mobile/fuse-mobile/lab/run_android_smoke.sh",
            "governance/fuse_mobile_mdtaf_v1.json",
            "governance/proofos_omega_policy_extension_fuse_mobile_mdtaf_v1.json",
        ]
        impact = ImpactCompiler(policy).assess(paths)
        manifest = ProofSelector(policy).compile_manifest(base_sha="1" * 40, head_sha="2" * 40, impact=impact)
        selected = {item.test_id for item in manifest.selected_tests}
        self.assertIn("FUSE_MOBILE_MDTAF", impact.direct_subsystems)
        self.assertFalse(impact.unmapped_production_paths)
        self.assertIn("fuse_mobile_mdtaf", selected)
        self.assertNotIn("full_federation_fallback", selected)
        self.assertTrue({"airlock_kernel", "source_provenance", "proofos_self"} <= selected)

    def test_smoke_harness_requires_verified_fault_and_recovery(self) -> None:
        source = (LAB / "run_android_smoke.sh").read_text(encoding="utf-8")
        self.assertIn("cmd connectivity airplane-mode enable", source)
        self.assertIn("cmd connectivity airplane-mode disable", source)
        self.assertIn("ping -c 1 -W 2 8.8.8.8", source)
        self.assertIn('"connectivity_loss_state"', source)
        self.assertIn('"network_recovery_state"', source)
        self.assertIn('"recovery_launch_state"', source)
        self.assertIn("refusing offline PASS", source)

    def test_certificate_accepts_matching_hardened_core(self) -> None:
        proc, certificate = self._run_certificate()
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertEqual(certificate["verdict"], "RELEASE_VERIFIED_WITH_DECLARED_LIMITATIONS")
        self.assertEqual(certificate["artifact_hash_binding_state"], "PASS")
        self.assertTrue(certificate["required_gates"]["connectivity_loss_verified"])
        self.assertTrue(certificate["required_gates"]["network_recovery"])
        self.assertTrue(certificate["required_gates"]["recovery_launch"])

    def test_certificate_refuses_unverified_connectivity_loss(self) -> None:
        smoke = self._valid_smoke()
        smoke["connectivity_loss_state"] = "FAIL"
        proc, certificate = self._run_certificate(smoke=smoke)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(certificate["verdict"], "NOT_RELEASE_READY")
        self.assertIn("connectivity_loss_verified", certificate["failed_required_gates"])

    def test_certificate_refuses_failed_network_recovery(self) -> None:
        smoke = self._valid_smoke()
        smoke["network_recovery_state"] = "FAIL"
        proc, certificate = self._run_certificate(smoke=smoke)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("network_recovery", certificate["failed_required_gates"])

    def test_certificate_refuses_failed_recovery_relaunch(self) -> None:
        smoke = self._valid_smoke()
        smoke["recovery_launch_state"] = "FAIL"
        proc, certificate = self._run_certificate(smoke=smoke)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("recovery_launch", certificate["failed_required_gates"])

    def test_certificate_refuses_hash_mismatch(self) -> None:
        security = self._valid_security()
        security["apk_sha256"] = "b" * 64
        proc, certificate = self._run_certificate(security=security)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(certificate["artifact_hash_binding_state"], "FAIL")
        self.assertIn("artifact_hash_binding", certificate["failed_required_gates"])

    def test_certificate_refuses_missing_security_hash(self) -> None:
        security = self._valid_security()
        security.pop("apk_sha256")
        proc, certificate = self._run_certificate(security=security)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("artifact_hash_binding", certificate["failed_required_gates"])

    def test_certificate_refuses_dirty_scan_even_when_hash_matches(self) -> None:
        security = self._valid_security()
        security["state"] = "APK_CREDENTIAL_SCAN_FAILED"
        proc, certificate = self._run_certificate(security=security)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(certificate["required_gates"]["artifact_hash_binding"])
        self.assertFalse(certificate["required_gates"]["apk_credential_scan"])

    def test_certificate_refuses_missing_core_evidence(self) -> None:
        source = (LAB / "certify.py").read_text(encoding="utf-8")
        self.assertIn('verdict = "NOT_RELEASE_READY"', source)
        self.assertIn('"RELEASE_VERIFIED_WITH_DECLARED_LIMITATIONS"', source)
        self.assertIn('"physical_device_validation"', source)
        self.assertIn('"owasp_masvs_review"', source)
        self.assertIn('"artifact_hash_binding"', source)
        self.assertIn('"connectivity_loss_verified"', source)
        self.assertIn('"network_recovery"', source)

    def test_mdtaf_reuses_existing_admitted_owner_dispatched_workflow(self) -> None:
        if not WORKFLOW.exists():
            self.skipTest("workflow-free export excludes repository workflow controls")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        policy = json.loads(AIRLOCK_POLICY.read_text(encoding="utf-8"))
        path = ".github/workflows/fuse-mobile-android-build.yml"
        self.assertIn(path, policy["active_workflow_allowlist"])
        self.assertEqual(policy["allowed_events"][path], ["issues"])
        self.assertIn("[FO-DISPATCH] FUSE_MOBILE_ANDROID_BUILD_V1", workflow)
        self.assertIn("[FO-DISPATCH] FUSE_MOBILE_MDTAF_V1", workflow)
        self.assertIn("permissions:\n  contents: read\n  issues: read", workflow)
        self.assertIn("github.event.issue.author_association == 'OWNER'", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn(path, policy["oidc_workflow_allowlist"])
        self.assertNotIn(path, policy["provider_mutation_workflow_allowlist"])
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("id-token: write", workflow)


if __name__ == "__main__":
    unittest.main()
