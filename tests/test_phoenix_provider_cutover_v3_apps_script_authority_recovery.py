from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest

from ops.apps_script_authorization_gate import audit_apps_script_source


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "systems" / "apps-script-authority-recovery-v1.1"
NODE_TEST = ROOT / "tests" / "js" / "test_apps_script_two_plane_candidate.js"
GOVERNANCE = ROOT / "governance" / "apps_script_authority_recovery_v1_1.json"


def bundle(directory: Path) -> str:
    files: list[dict[str, str]] = []
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix in {".gs", ".json"}:
            files.append(
                {
                    "name": "appsscript" if path.name == "appsscript.json" else path.stem,
                    "type": "JSON" if path.suffix == ".json" else "SERVER_JS",
                    "source": path.read_text(encoding="utf-8"),
                }
            )
    return json.dumps({"files": files}, sort_keys=True)


class AppsScriptAuthorityRecoveryV11AdmissionTests(unittest.TestCase):
    def test_candidate_layout_is_complete_and_text_only(self) -> None:
        expected = {
            "public_gateway/Gateway_Router.gs",
            "public_gateway/Gateway_Security.gs",
            "public_gateway/appsscript.json",
            "private_admin/Admin_Router.gs",
            "private_admin/Admin_Security.gs",
            "private_admin/Project_Lineage.gs",
            "private_admin/Retained_ARCHON_Code_Manager.gs",
            "private_admin/appsscript.json",
        }
        present = {
            path.relative_to(CANDIDATE).as_posix()
            for path in CANDIDATE.rglob("*")
            if path.is_file()
        }
        self.assertTrue(expected.issubset(present))
        self.assertFalse(any(path.suffix in {".pyc", ".pyo"} for path in ROOT.rglob("*")))
        self.assertFalse(any(path.name == "__pycache__" for path in ROOT.rglob("*")))

    def test_public_and_private_candidates_pass_gate_v21(self) -> None:
        for name in ("public_gateway", "private_admin"):
            report = audit_apps_script_source(bundle(CANDIDATE / name))
            self.assertEqual("SOURCE_REVIEW_PASS", report["status"], report)
            self.assertEqual([], report["findings"], report)
            self.assertEqual("2.1.0", report["version"])

    def test_executable_node_hostile_suite_passes(self) -> None:
        completed = subprocess.run(
            ["node", str(NODE_TEST), str(CANDIDATE)],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        receipt = json.loads(completed.stdout)
        self.assertEqual("PASS", receipt["result"])
        self.assertEqual(30, receipt["passed"])
        self.assertEqual(0, receipt["failed"])
        self.assertFalse(receipt["providerMutationPerformed"])
        self.assertFalse(receipt["liveAppsScriptChanged"])

    def test_governance_preserves_provider_and_lineage_boundaries(self) -> None:
        value = json.loads(GOVERNANCE.read_text(encoding="utf-8"))
        self.assertEqual("1.1.0", value["version"])
        self.assertEqual("257649435135", value["lineage"]["canonical_target_project_number"])
        self.assertEqual("516699068552", value["lineage"]["legacy_transport_project_number"])
        self.assertFalse(value["lineage"]["authority_inheritance"])
        self.assertFalse(value["verification"]["provider_runtime_executed"])
        self.assertFalse(value["verification"]["live_apps_script_changed"])

    def test_source_contains_no_private_backup_or_credential_material(self) -> None:
        prohibited_paths = {
            "FO_GAS_FLEET_RESTORABLE_BACKUP",
            "FLEETWEEKLY-20260718-181318-5BXX66.json",
        }
        source_paths = {path.name for path in ROOT.rglob("*") if path.is_file()}
        self.assertTrue(prohibited_paths.isdisjoint(source_paths))
        combined = "\n".join(
            path.read_text(encoding="utf-8", errors="strict")
            for path in CANDIDATE.rglob("*")
            if path.is_file()
        )
        self.assertNotIn("APPROVAL_KEY: 'APPROVED'", combined)
        self.assertNotIn('APPROVAL_KEY: "APPROVED"', combined)
        self.assertNotIn("-----BEGIN PRIVATE KEY-----", combined)
        self.assertNotRegex(combined, r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b")

    def test_manager_orders_backup_permit_and_mutation_correctly(self) -> None:
        source = (CANDIDATE / "private_admin" / "Retained_ARCHON_Code_Manager.gs").read_text(encoding="utf-8")
        apply_start = source.index("\nfunction SOVARA_ARCHON_codeApply")
        rollback_start = source.index("\nfunction SOVARA_ARCHON_codeRollback")
        apply = source[apply_start:rollback_start]
        backup = apply.index("ARCHON_CODE_createBackup_")
        consume = apply.index("SOVARA_ADMIN_consumeEffectPermit_")
        mutate = apply.index("ARCHON_CODE_updateProjectContent_")
        self.assertLess(consume, backup)
        self.assertLess(backup, mutate)
        self.assertNotIn("function SOVARA_ARCHON_signRequest", source)
        self.assertIn("Backup exact semantic readback mismatch.", source)


if __name__ == "__main__":
    unittest.main()
