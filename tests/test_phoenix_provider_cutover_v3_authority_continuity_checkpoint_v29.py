from __future__ import annotations
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CP = ROOT / "alpha_omega_commercial" / "phoenix_provider_authority_continuity_checkpoint_v29.json"
PJ = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v29.json"
AP = ROOT / "phoenix" / "ops-template" / "governance" / "APPLY_ENTRYPOINT.json"
AC = ROOT / "phoenix" / "ops-template" / "governance" / "PROVIDER_AUTHORITY_PROBE_CONTRACT.json"
OC = ROOT / "phoenix" / "ops-template" / "governance" / "OPS_CONTRACT.json"

def checked_hash(payload: dict, field: str) -> str:
    body = dict(payload)
    claimed = body.pop(field)
    calculated = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if claimed != calculated:
        raise AssertionError(f"{field} mismatch: {claimed} != {calculated}")
    return claimed

class PhoenixProviderAuthorityContinuityCheckpointV29Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cp = json.loads(CP.read_text())
        cls.pj = json.loads(PJ.read_text())
        cls.ap = json.loads(AP.read_text())
        cls.ac = json.loads(AC.read_text())
        cls.oc = json.loads(OC.read_text())

    def test_hashes_dependency_order_and_service_first(self):
        self.assertEqual("d007c6874b05d833c24aa8ac2a1d6f6e021907c732bf060aad7c638b396329f1", checked_hash(self.cp, "checkpoint_sha256"))
        self.assertEqual("38198379525a8c0f1204014faeb495b971928f2f31f4146025c3301a5dd73fed", checked_hash(self.pj, "projection_sha256"))
        self.assertEqual([f"C{i:02d}" for i in range(1, 16)], self.pj["dependency_order"])
        self.assertTrue(self.pj["dependency_order_preserved"])
        self.assertTrue(self.pj["service_enabled_platform_first"])
        self.assertTrue(self.pj["self_service_saas_held"])
        self.assertEqual(["C03","C06","C07","C11","C14","C15"], self.cp["dependency_path"])

    def test_predecessor_and_lineage_are_exact(self):
        p = self.cp["predecessor"]
        self.assertEqual("ca3424575d73d080fb383dd4d2e6c10b2ccf33135c648372307f95a071d16e7e", p["checkpoint_sha256"])
        self.assertEqual("f53b80ad09ed0e6372d441915da4ad83a49e88fb01b1628a81877e36169440c7", p["programme_projection_sha256"])
        line = self.cp["implementation_lineage"]
        self.assertEqual(247, line["capability_pull_request"])
        self.assertEqual("a6cd1b08c475922abbfc5c5d4326421c7535032a", line["capability_pull_request_head"])
        self.assertEqual("f455e46b1d26659a78eb8b8354341806f4b5cbdc", line["capability_merge_commit"])
        self.assertEqual(248, line["current_main_context_pull_request"])
        self.assertEqual("c31d5e99759338f28b3c6b9ad9f8c7141ca79b5b", line["current_main_context_merge_commit"])
        self.assertEqual(0, line["workflow_change_count"])

    def test_provider_native_proof_and_exports_are_exact(self):
        a = self.cp["provider_native_admission"]
        self.assertEqual((30965716910, 92179098845, 8914633816), (a["airlock_run"], a["airlock_job"], a["airlock_artifact_id"]))
        self.assertEqual([], a["airlock_findings"])
        self.assertEqual(0, a["unadmitted_commit_count"])
        self.assertEqual("136/136_PASS", a["provider_control_regressions"]["provider_cutover_v3_family"])
        self.assertEqual("11/11_PASS", a["provider_control_regressions"]["authority_continuity_controls"])
        f = self.cp["provider_native_final_head"]
        self.assertEqual("c31d5e99759338f28b3c6b9ad9f8c7141ca79b5b", f["source_sha"])
        self.assertEqual((30966624315, 92181866024), (f["workflow_run"], f["workflow_job"]))
        self.assertEqual("phoenix-freeze/verified", f["commit_status"])
        self.assertEqual(8914961487, f["cutover_artifact"]["artifact_id"])
        self.assertEqual(8914961270, f["freeze_artifact"]["artifact_id"])
        r = self.cp["export_receipt"]
        self.assertEqual("b2851eae1c4016a8d9f9e6350885d60150c74278e9008f9db07bb44bbb2698b1", r["receipt_sha256"])
        self.assertEqual("8095d0ad45002173d9fad3c439e40379a9e2a1cfcabb1ccb50b8f9bbbacce81a", r["core"]["archive_sha256"])
        self.assertEqual("46a5e981d29d4023d6a38b4edb7306ff3c7ae7ea01d5bd38e19a46ad774ebaec", r["ops"]["archive_sha256"])
        self.assertEqual(0, r["ops"]["active_workflow_count"])

    def test_exported_governance_requires_fresh_jit_continuity(self):
        c = self.cp["export_receipt"]["provider_authority_continuity_contract"]
        self.assertEqual("provider_cutover_authority_bound.py", c["canonical_apply_entrypoint"])
        self.assertEqual(300, c["authority_receipt_max_age_seconds"])
        self.assertEqual(30, c["authority_receipt_max_future_skew_seconds"])
        self.assertTrue(c["authority_receipt_semantic_checks_required"])
        self.assertTrue(c["just_in_time_reprobe_required"])
        self.assertTrue(c["just_in_time_reprobe_get_only"])
        fields = ["authority_mode","repository_creation_endpoint","legacy_main_sha","core_target_exists","ops_target_exists"]
        self.assertEqual(fields, c["continuity_fields"])
        self.assertEqual(300, self.ap["provider_authority_receipt_max_age_seconds"])
        self.assertEqual(30, self.ap["provider_authority_receipt_max_future_skew_seconds"])
        self.assertTrue(self.ap["provider_authority_just_in_time_reprobe_required"])
        self.assertTrue(self.ap["provider_authority_continuity_drift_invalidates"])
        self.assertEqual(fields, self.ac["continuity_fields"])
        self.assertEqual("AUTHORITY_CONTINUITY_INVALIDATED", self.ac["continuity_drift_status"])
        self.assertTrue(self.oc["authority_rules"]["provider_authority_continuity_required"])
        self.assertFalse(self.oc["authority_rules"]["source_repository_mutation"])

    def test_live_authority_and_operational_gate_fail_closed(self):
        r = self.cp["provider_authority_readback"]
        self.assertTrue(r["fresh_readback_performed"])
        self.assertEqual(["mosianekk-lang/Federation-Omega"], r["installed_repositories"])
        self.assertEqual("NOT_FOUND_NOT_CLAIMED_CREATED", r["target_core_repository"])
        self.assertEqual("NOT_FOUND_NOT_CLAIMED_CREATED", r["target_ops_repository"])
        blocked = "PROVIDER_BLOCKED_SELECTED_REPOSITORY_INSTALLATION_OR_USER_SCOPED_ADMIN_AUTHORITY_REQUIRED"
        self.assertEqual(blocked, r["provider_apply_authority"])
        self.assertFalse(r["provider_mutation_performed"])
        g = self.cp["operational_proof_gate"]
        for key in ("authority_receipt_freshness_checks","authority_receipt_future_skew_checks","authority_receipt_semantic_checks","just_in_time_authority_reprobe_get_only","authority_continuity_binding","target_topology_drift_fail_closed","source_drift_fail_closed","probe_failure_fail_closed"):
            self.assertEqual("VERIFIED_MOCK_PROVIDER_CONFORMANCE", g[key])
        self.assertFalse(g["blocked_authority_authorization_state_created"])
        self.assertFalse(g["blocked_authority_provider_call_allowed"])
        self.assertFalse(g["provider_apply_performed"])
        self.assertFalse(g["external_repository_created"])

    def test_drive_freeze_commercial_and_institution_boundaries(self):
        d = self.cp["google_drive_release"]
        self.assertEqual("1YhAURM-Wlna8S2UsRABTHTd2RWbVM-MElUPJn3Yu6_I", d["file_id"])
        self.assertEqual("VERIFIED", d["readback"])
        self.assertFalse(d["shared"])
        self.assertEqual(7612, d["text_export_size_bytes"])
        self.assertEqual("26deacadebc8786053b05497b06ebe5c3429ea6c67d1cdac778d6a7e2b2afc49", d["text_export_sha256"])
        z = self.cp["execution_freeze_receipt"]
        self.assertEqual("VERIFIED", z["status"])
        self.assertEqual([], z["unexpected_active"])
        self.assertFalse(z["source_mutation_attempted"])
        t = self.cp["commercial_truth"]
        self.assertEqual("VERIFIED_AND_PRIORITISED", t["service_enabled_platform"])
        self.assertEqual("HELD", t["self_service_saas"])
        self.assertEqual("MARKET_PROOF_REQUIRED", t["customer_demand"])
        self.assertEqual("NOT_PROVEN", t["cloud_run_operation"])
        self.assertEqual(0, t["verified_live_revenue_events"])
        self.assertFalse(t["full_commercial_maturity"])
        self.assertEqual("UNVERIFIED_SCOPE_HELD", self.cp["institution_scope"]["institution_v3_google_drive_publication"])

    def test_projection_keeps_provider_and_owner_boundaries(self):
        blocked = "PROVIDER_BLOCKED_SELECTED_REPOSITORY_INSTALLATION_OR_USER_SCOPED_ADMIN_AUTHORITY_REQUIRED"
        self.assertEqual(blocked, self.pj["provider_execution_plane_cutover"])
        release = self.pj["release_reconciliation"]
        self.assertEqual("NOT_CREATED", release["target_core_repository"])
        self.assertEqual("NOT_CREATED", release["target_ops_repository"])
        self.assertFalse(release["provider_apply_performed"])
        self.assertFalse(release["consequential_release_performed"])
        self.assertIn("PROVIDER_AUTHORITY_CONTINUITY_RELEASE_RECONCILED", self.pj["stage_projection"]["C15"])
        self.assertEqual("OWNER_RESERVED", self.pj["owner_authority"]["financial_commitments"])
        self.assertEqual(0, self.pj["verified_live_revenue_events"])
        self.assertFalse(self.pj["full_commercial_maturity"])

if __name__ == "__main__":
    unittest.main()
