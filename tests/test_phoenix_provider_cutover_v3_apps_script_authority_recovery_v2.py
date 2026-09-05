from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from ops.apps_script_authorization_gate import audit_apps_script_source

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "apps_script" / "authority_recovery_v2"
PUBLIC = CANDIDATE / "public_gateway"
PRIVATE = CANDIDATE / "private_admin"
GOVERNANCE = ROOT / "governance" / "apps_script_authority_recovery_v2.json"
EXPECTED_SOURCE_SHA = "2e80636313ba1942ac80d0de687bf465d1472f998a0bc071d5e2d93adfe33248"


class AppsScriptAuthorityRecoveryV2Tests(unittest.TestCase):
    def project_bundle(self, directory: Path) -> str:
        files = []
        for path in sorted(directory.iterdir()):
            if path.name == "README.md" or path.is_dir():
                continue
            file_type = "JSON" if path.name == "appsscript.json" else "SERVER_JS"
            name = "appsscript" if path.name == "appsscript.json" else path.stem
            files.append(
                {
                    "name": name,
                    "type": file_type,
                    "source": path.read_text(),
                }
            )
        return json.dumps({"files": files})

    def public_report(self) -> dict:
        return audit_apps_script_source(self.project_bundle(PUBLIC))

    def private_report(self) -> dict:
        return audit_apps_script_source(self.project_bundle(PRIVATE))

    def test_public_gateway_is_minimum_scope_and_read_only(self):
        manifest = json.loads((PUBLIC / "appsscript.json").read_text())
        self.assertEqual(manifest.get("oauthScopes"), None)
        router = (PUBLIC / "Gateway_Router.gs").read_text()
        security = (PUBLIC / "Gateway_Security.gs").read_text()
        combined = router + security
        self.assertEqual(combined.count("function doGet("), 1)
        self.assertEqual(combined.count("function doPost("), 1)
        self.assertIn("computeHmacSha256Signature", security)
        self.assertIn("SOVARA_GATEWAY_claimNonce_", security)
        self.assertIn("CANONICAL_TARGET_MISMATCH", security)
        self.assertIn("SECRET_BEARING_PAYLOAD_FIELD_REJECTED", security)
        self.assertNotIn("APPROVAL_KEY", combined)
        self.assertNotIn("RUNTIME_EXECUTE", combined)
        self.assertNotIn("ARCHON_codeApply", combined)
        self.assertNotIn("script.projects", json.dumps(manifest))
        self.assertNotIn("cloud-platform", json.dumps(manifest))
        self.assertEqual(self.public_report()["status"], "SOURCE_REVIEW_PASS")

    def test_private_admin_has_no_public_web_entry(self):
        manifest = json.loads((PRIVATE / "appsscript.json").read_text())
        self.assertNotIn("webapp", manifest)
        self.assertNotIn(
            "https://www.googleapis.com/auth/cloud-platform",
            manifest["oauthScopes"],
        )
        source = self.project_bundle(PRIVATE)
        self.assertNotIn("function doGet(", source)
        self.assertNotIn("function doPost(", source)
        router = (PRIVATE / "Admin_Router.gs").read_text()
        self.assertIn("function SOVARA_ADMIN_dispatch", router)
        self.assertEqual(self.private_report()["status"], "SOURCE_REVIEW_PASS")

    def test_provider_and_permit_bindings_are_exact_and_externally_verified(self):
        source = (PRIVATE / "Project_Lineage.gs").read_text()
        security = (PRIVATE / "Admin_Security.gs").read_text()
        for marker in (
            "APPS_SCRIPT_ADMIN_COMPOSITE",
            "transactionId",
            "requestSha256",
            "expectedBeforeHash",
            "expectedAfterHash",
            "providerReceiptSha256",
            "effectPermitSha256",
            "standardCloudProjectShared",
            "scriptsRunDeploymentVerified",
            "projectContentInventoryVerified",
            "deploymentInventoryVerified",
            "EXTERNAL_ADMISSION_VERIFICATION_FAILED",
            "verifierIdentity",
            "followRedirects: false",
        ):
            self.assertIn(marker, source)
        self.assertIn("SOVARA_ADMIN_claimEffectPermit_", security)
        self.assertIn("EFFECT_PERMIT_REPLAY_REJECTED", security)
        self.assertIn("PERMIT_LEDGER_PROPERTY", security)
        self.assertNotIn("PROVIDER_RECEIPT_ANCHOR_PROPERTY", source)
        self.assertNotIn("EFFECT_PERMIT_ANCHOR_PROPERTY", source)

    def test_backup_first_mutation_and_rollback_are_hash_read_back(self):
        manager = (PRIVATE / "ARCHON_Core.gs").read_text()
        backup = (PRIVATE / "ARCHON_Version_Backup_API.gs").read_text()
        integrity = (PRIVATE / "ARCHON_Integrity_Audit.gs").read_text()
        self.assertIn("SOVARA_ADMIN_claimEffectPermitUnderLock_", manager)
        claim = manager.index("SOVARA_ADMIN_claimEffectPermitUnderLock_")
        backup_call = manager.index("ARCHON_CODE_createBackup_", claim)
        update = manager.index("ARCHON_CODE_updateProjectContent_", backup_call)
        readback = manager.index("ARCHON_CODE_getProjectContent_", update)
        version = manager.index("ARCHON_CODE_createVersion_", readback)
        self.assertLess(claim, backup_call)
        self.assertLess(backup_call, update)
        self.assertLess(update, readback)
        self.assertLess(readback, version)
        self.assertIn("ARCHON_CODE_BACKUP_V2", backup)
        self.assertIn("backupSha256", backup)
        self.assertIn("Backup exact readback verification failed", backup)
        self.assertIn("Rollback readback hash mismatch", backup)
        self.assertIn("ARCHON_CODE_verifyDeploymentReadback_", integrity)
        self.assertIn("ARCHON_CODE_auditSpreadsheet_", integrity)
        self.assertNotIn("getActiveSpreadsheet", integrity)
        self.assertNotIn("getActiveSpreadsheet", manager)
        self.assertIn("ARCHON_AUDIT_SPREADSHEET_ID", (PRIVATE / "README.md").read_text())
        self.assertNotIn("function ARCHON_codeApply", manager)
        self.assertNotIn("function ARCHON_codeRollback", manager)

    def test_no_change_returns_before_permit_consumption_or_provider_writes(self):
        manager = (PRIVATE / "ARCHON_Core.gs").read_text()
        no_change = manager.index("status: 'NO_CHANGE'")
        consume = manager.index("SOVARA_ADMIN_claimEffectPermitUnderLock_")
        backup = manager.index("ARCHON_CODE_createBackup_", consume)
        update = manager.index("ARCHON_CODE_updateProjectContent_", backup)
        self.assertLess(no_change, consume)
        self.assertLess(no_change, backup)
        self.assertLess(no_change, update)
        self.assertIn("permitConsumed: false", manager)

    def test_permit_consumption_does_not_reacquire_non_reentrant_lock(self):
        security = (PRIVATE / "Admin_Security.gs").read_text()
        manager = (PRIVATE / "ARCHON_Core.gs").read_text()
        start = security.index("function SOVARA_ADMIN_claimEffectPermitUnderLock_")
        end = security.index("function SOVARA_ADMIN_readLedger_", start)
        under_lock = security[start:end]
        self.assertNotIn("getScriptLock", under_lock)
        self.assertNotIn("waitLock", under_lock)
        self.assertIn("SOVARA_ADMIN_claimEffectPermitUnderLock_", manager)
        self.assertNotIn(
            "SOVARA_ADMIN_claimEffectPermit_(\n        request.effectPermit",
            manager,
        )

    def test_post_effect_verifier_is_action_aware_for_apply_and_rollback(self):
        source = (PRIVATE / "Project_Lineage.gs").read_text()
        manager = (PRIVATE / "ARCHON_Core.gs").read_text()
        self.assertIn("const effectAction", source)
        self.assertIn("action: effectAction", source)
        self.assertIn(
            "String(verified.action || '') === effectAction",
            source,
        )
        self.assertGreaterEqual(
            manager.count("SOVARA_ADMIN_verifyExternalPostEffect_"),
            2,
        )

    def test_apps_script_api_client_rejects_redirects(self):
        source = (PRIVATE / "ARCHON_Version_Backup_API.gs").read_text()
        start = source.index("function ARCHON_CODE_apiRequest_")
        client = source[start:]
        self.assertIn("followRedirects: false", client)
        self.assertIn("status < 200 || status >= 300", client)

    def test_node_security_contract_executes(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        completed = subprocess.run(
            [node, str(CANDIDATE / "tests" / "security_contracts.mjs")],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(
            "APPS_SCRIPT_AUTHORITY_RECOVERY_V2_SECURITY_CONTRACTS_PASS",
            completed.stdout,
        )

    def test_python_signer_emits_no_secret(self):
        signer = CANDIDATE / "tools" / "sign_envelope.py"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "request.json"
            env = {
                "PATH": str(Path(shutil.which("python") or "/usr/bin/python").parent),
                "SOVARA_HMAC_SECRET": "s" * 48,
            }
            completed = subprocess.run(
                [
                    shutil.which("python") or "python",
                    str(signer),
                    "gateway",
                    "--action",
                    "STATUS",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            rendered = output.read_text()
            self.assertNotIn("s" * 32, rendered)
            payload = json.loads(rendered)
            self.assertEqual(payload["targetProjectNumber"], "257649435135")
            self.assertRegex(payload["signature"], r"^[a-f0-9]{64}$")

    def test_candidate_manifest_and_receipt_are_hash_bound(self):
        manifest_path = CANDIDATE / "candidate_manifest.json"
        receipt_path = CANDIDATE / "source_audit_receipt.json"
        manifest = json.loads(manifest_path.read_text())
        claimed_manifest = manifest.pop("manifest_sha256")
        actual_manifest = hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.assertEqual(claimed_manifest, actual_manifest)
        for item in manifest["files"]:
            file_path = ROOT / item["path"]
            data = file_path.read_bytes()
            self.assertEqual(len(data), item["bytes"], item["path"])
            self.assertEqual(
                hashlib.sha256(data).hexdigest(),
                item["sha256"],
                item["path"],
            )

        receipt = json.loads(receipt_path.read_text())
        claimed_receipt = receipt.pop("receipt_sha256")
        actual_receipt = hashlib.sha256(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.assertEqual(claimed_receipt, actual_receipt)
        self.assertEqual(
            receipt["candidate"]["manifest_sha256"],
            claimed_manifest,
        )

    def test_source_anchor_and_truth_boundary_are_preserved(self):
        governance = json.loads(GOVERNANCE.read_text())
        self.assertEqual(
            governance["source"]["declared_source_sha256"],
            EXPECTED_SOURCE_SHA,
        )
        self.assertFalse(governance["source"]["original_mutated"])
        self.assertFalse(governance["provider_authority_proven"])
        self.assertFalse(governance["provider_mutation_authorized"])
        self.assertFalse(governance["provider_deployment_performed"])
        self.assertFalse(governance["live_apps_script_mutated"])
        self.assertEqual(
            governance["local_verification"]["protected_backup_audit"][
                "status"
            ],
            "SECURITY_HOLD",
        )
        self.assertGreaterEqual(
            governance["local_verification"]["protected_backup_audit"][
                "static_coverage_ratio_vs_prior_best_case"
            ],
            2.0,
        )


if __name__ == "__main__":
    unittest.main()
