from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "phoenix-emergency-freeze.yml"
POLICY = ROOT / "governance" / "github_airlock_policy.json"
SCRIPT = ROOT / "ops" / "evidenceops_local_bible_event13_rebuild.py"
BOUNDARY = ROOT / "phoenix" / "LOCAL_BIBLE_RECOVERY_EXTERNALIZATION.md"
EXPECTED_PREVIOUS_HASH = "e58ba00136022251976051a041b3664fd51418aaabf2c840c8bf2c5d7903cf21"
EVENT_ID = "EVT-20260804-PST-REMOTE-CLOSURE-FEDERATION-LEARNING-AND-PACKAGE-REBUILD"


class LocalBibleRebuildBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.boundary = BOUNDARY.read_text(encoding="utf-8")

    def test_legacy_source_workflow_has_zero_oidc(self) -> None:
        forbidden = (
            "[BIBLE-REBUILD]",
            "id-token: write",
            "google-github-actions/auth@",
            "GOOGLE_ACCESS_TOKEN",
            "phoenix-export-output/local-bible-rebuild",
            "Authenticate private Local Bible recovery",
            "Rebuild private Local Bible Event 13",
        )
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, self.workflow)
        self.assertIn("PST not requested", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)

    def test_airlock_oidc_allowlist_is_exactly_scoped(self) -> None:
        credential_policy = self.policy["provider_credential_reference_policy"]
        deployment_gateways = {
            credential_policy["provider_deployment_workflow"],
            credential_policy["luno_observer_deployment_workflow"],
            credential_policy["gemini_provider_deployment_workflow"],
            credential_policy["seb_deployment_workflow"],
            ".github/workflows/cios-production-lane.yml",
        }
        g0_identity_probe = credential_policy["g0_identity_probe_workflow"]
        provider_authority_recovery_probe = credential_policy["provider_authority_recovery_probe_workflow"]
        artifact_attestation = credential_policy["artifact_attestation_workflow"]
        fhu047_workflows = {
            value
            for key, value in credential_policy.items()
            if key.startswith("fhu047_") and key.endswith("_workflow")
        }
        provider_mutators = set(self.policy["provider_mutation_workflow_allowlist"])
        nexus_read_only_preflights = {
            ".github/workflows/nexus-direct-preflight.yml",
            ".github/workflows/nexus-direct-runtime-target.yml",
        }
        expected = deployment_gateways | {
            g0_identity_probe,
            provider_authority_recovery_probe,
            artifact_attestation,
        } | fhu047_workflows | provider_mutators | nexus_read_only_preflights
        self.assertEqual(expected, set(self.policy["oidc_workflow_allowlist"]))

        scoped_non_deployment = {
            g0_identity_probe,
            provider_authority_recovery_probe,
            artifact_attestation,
        } | fhu047_workflows | provider_mutators | nexus_read_only_preflights
        for workflow in scoped_non_deployment:
            self.assertIn(workflow, self.policy["active_workflow_allowlist"])
            self.assertIn(workflow, self.policy["execution_quarantine"]["keep_active"])

        self.assertEqual(
            [artifact_attestation],
            self.policy["attestations_write_workflow_allowlist"],
        )
        self.assertNotIn(provider_authority_recovery_probe, provider_mutators)
        self.assertNotIn(provider_authority_recovery_probe, self.policy["attestations_write_workflow_allowlist"])

        sol62_wif = credential_policy.get("sol62_wif_hardening_workflow")
        self.assertEqual({sol62_wif}, provider_mutators)
        self.assertEqual(
            {sol62_wif: "SOL62-WIF-HARDEN-20260901"},
            self.policy["provider_mutation_exact_issue_titles"],
        )

        fhu047_repair = credential_policy.get("fhu047_one_use_repair_workflow")
        if fhu047_repair is not None:
            self.assertIn(fhu047_repair, fhu047_workflows)

        fhu047_census = credential_policy.get("fhu047_authority_graph_census_workflow")
        if fhu047_census is not None:
            self.assertIn(fhu047_census, fhu047_workflows)
            self.assertNotIn(fhu047_census, provider_mutators)
            self.assertNotIn(fhu047_census, self.policy["attestations_write_workflow_allowlist"])

        if not fhu047_workflows:
            self.assertFalse(any("fhu-047" in workflow.lower() for workflow in self.policy["oidc_workflow_allowlist"]))
            self.assertFalse(any("fhu-047" in workflow.lower() for workflow in provider_mutators))

        self.assertNotIn(
            g0_identity_probe,
            deployment_gateways | {provider_authority_recovery_probe, artifact_attestation} | fhu047_workflows | provider_mutators,
        )
        self.assertNotIn(provider_authority_recovery_probe, deployment_gateways)
        self.assertNotIn("oidc_boundary", self.policy)
        self.assertEqual(
            "QUARANTINED_SOURCE_WITH_EXACT_AIRLOCKED_PROVIDER_GATEWAYS",
            self.policy["source_repository_role"],
        )

    def test_rebuild_is_packaged_capability_not_active_source_runtime(self) -> None:
        self.assertTrue(SCRIPT.exists())
        self.assertTrue(BOUNDARY.exists())
        self.assertIn("PRIVATE_OPS_PLANE_REQUIRED", self.boundary)
        self.assertIn("not executable from the legacy public source repository", self.boundary)
        self.assertIn("contains exactly five provider-deployment gateways", self.boundary)
        self.assertIn("deploy-gemini-gateway.yml", self.boundary)
        self.assertIn("seb-omega.yml", self.boundary)
        self.assertIn("no provider rebuild or Library writeback is claimed", self.boundary)

    def test_rebuild_anchors_to_exact_predecessor_and_original_writer(self) -> None:
        self.assertIn(EXPECTED_PREVIOUS_HASH, self.script)
        self.assertIn(EVENT_ID, self.script)
        self.assertIn("capture_event.py", self.script)
        self.assertIn("subprocess.run([sys.executable, str(capture), \"append\"", self.script)
        self.assertIn("subprocess.run([sys.executable, str(capture), \"verify\"", self.script)
        self.assertIn("predecessor event hash drift", self.script)
        self.assertIn("Event 13 previous hash", self.script)
        self.assertIn("ZIP CRC failed", self.script)

    def test_rebuild_is_private_and_source_write_free(self) -> None:
        forbidden = (
            "drive.google.com/uc",
            "export=download",
            "permissions.create",
            "anyoneWithLink",
            "git commit",
            "git push",
            "contents: write",
        )
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, self.script)
        self.assertIn("https://www.googleapis.com/drive/v3/files/", self.script)
        self.assertIn('headers={"Authorization": f"Bearer {token}"}', self.script)
        self.assertIn("P2_PRIVATE_DRIVE_READ_ONLY_NO_PUBLIC_SOURCE_CONTENT", self.script)
        self.assertIn(
            "PROVIDER_PACKAGE_REBUILD_VERIFIED_PENDING_LIBRARY_WRITEBACK",
            self.script,
        )

    def test_failure_success_constraint_learning_ids_are_bound(self) -> None:
        required = (
            "INC-FO-LBRF-20260804-001",
            "REM-FO-LBRF-20260804-001",
            "FORM-FO-LBRF-20260804-001",
            "ALG-LBRF-001",
            "LS-LBRF-001",
            "AR-LBRF-001",
            "CT-LBRF-001",
            "RP-LBRF-001",
            "LOCAL_BINARY_FAILURE_X2",
        )
        for value in required:
            self.assertIn(value, self.script)

    def test_typed_set_preserves_template_field_shapes(self) -> None:
        spec = importlib.util.spec_from_file_location("lbrf", SCRIPT)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        payload = {"sources_inspected": "legacy", "verified_proof": []}
        module.typed_set(payload, "sources_inspected", ["one", "two"])
        module.typed_set(payload, "verified_proof", "proof")
        self.assertEqual("one; two", payload["sources_inspected"])
        self.assertEqual(["proof"], payload["verified_proof"])


if __name__ == "__main__":
    unittest.main()
