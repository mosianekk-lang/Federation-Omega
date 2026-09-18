from __future__ import annotations

from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
COURT = ROOT / "governance" / "self_hosting_rd_court_v1.json"
PROOFOS = ROOT / "governance" / "proofos_omega_policy_extension_self_hosting_rd_v1.json"
DOC = ROOT / "docs" / "architecture" / "SELF_HOSTING_RD_COURT_V1.md"

REQUIRED_TERMINALS = {
    "EXACT_SOURCE_CURRENTNESS",
    "REPRODUCIBLE_BUILD",
    "CHALLENGER_READY",
    "MATCHED_EVAL",
    "QUALITY_NONNEGATIVE",
    "DEPENDENCY_EXIT",
    "DISCONNECTED_REBUILD",
    "ROLLBACK_READY",
    "OWNER_VALUE_GAIN",
    "INDEPENDENT_JUDGE_ACK",
}

class SelfHostingRDCourtV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.court = json.loads(COURT.read_text(encoding="utf-8"))
        cls.proofos = json.loads(PROOFOS.read_text(encoding="utf-8"))
        cls.doc = DOC.read_text(encoding="utf-8")

    def test_terminal_court_is_complete_and_exact(self):
        self.assertEqual(set(self.court["terminal_predicates"]), REQUIRED_TERMINALS)

    def test_does_not_create_duplicate_sovereign_roots(self):
        forbidden = set(self.court["forbidden_duplicate_roots"])
        for item in ("controller", "scheduler", "mission_bus", "memory_root", "proof_root", "source_authority", "judge"):
            self.assertIn(item, forbidden)
        self.assertIn("FUSE_FORGE_SOVEREIGN_SOURCE_PROTECTION_V1", self.court["reuse_required"])
        self.assertIn("REALITY_JUDGE", self.court["reuse_required"])

    def test_authority_and_effects_fail_closed(self):
        effects = self.court["effects"]
        self.assertFalse(effects["provider_effect_authorized_by_source"])
        self.assertFalse(effects["provider_mutation_authorized_by_source"])
        self.assertFalse(effects["production_activation_authorized_by_source"])
        self.assertFalse(effects["public_invocation_authorized_by_source"])
        self.assertFalse(effects["iam_mutation_authorized_by_source"])
        self.assertTrue(self.court["hard_floors"]["no_authority_expansion"])

    def test_clean_room_boundary_is_explicit(self):
        b = self.court["clean_room_boundary"]
        self.assertTrue(b["owned_source"])
        self.assertTrue(b["public_mechanisms"])
        self.assertTrue(b["authorized_interfaces"])
        self.assertFalse(b["private_or_restricted_bypass"])
        self.assertFalse(b["credential_or_access_control_bypass"])

    def test_promotion_separates_source_runtime_and_value(self):
        p = self.court["promotion"]
        self.assertTrue(p["fdof_required_for_source"])
        self.assertFalse(p["source_admission_proves_runtime"])
        self.assertFalse(p["runtime_proof_proves_value"])
        self.assertFalse(p["builder_may_self_promote"])
        self.assertTrue(p["independent_judge_required"])
        boundary = self.court["proof_boundary"]
        self.assertFalse(boundary["source_admitted"])
        self.assertFalse(boundary["runtime_executed"])
        self.assertFalse(boundary["production_active"])
        self.assertFalse(boundary["value_verified"])

    def test_challenger_requires_exit_rebuild_and_rollback(self):
        c = self.court["challenger_contract"]
        self.assertTrue(c["reuse_before_build"])
        self.assertTrue(c["compose_before_residual"])
        self.assertTrue(c["source_independent_tests_required"])
        self.assertTrue(c["matched_incumbent_comparison_required"])
        self.assertTrue(c["negative_courts_required"])
        self.assertTrue(c["rollback_package_required"])
        self.assertTrue(c["dependency_exit_test_required"])
        self.assertTrue(c["disconnected_rebuild_test_required"])

    def test_proofos_binds_global_r4_core_test(self):
        rr = self.proofos["risk_rules"][0]
        self.assertEqual(rr["risk"], "R4_CORE")
        sr = self.proofos["subsystem_rules"][0]
        self.assertEqual(sr["subsystem"], "SELF_HOSTING_RD_COURT_V1")
        self.assertIn("FUSE_FORGE_SOVEREIGN_SOURCE_PROTECTION_V1", sr["depends_on"])
        t = self.proofos["tests"][0]
        self.assertEqual(t["target"], "test_self_hosting_rd_court_v1.py")
        self.assertEqual(t["block_scope"], "GLOBAL")

    def test_architecture_doc_preserves_owner_and_maturity_boundaries(self):
        for marker in (
            "Optimize means; never redefine the owner's end.",
            "Control deployment is not source admission.",
            "Source admission is not runtime proof.",
            "Runtime proof is not value proof.",
            "Disconnected rebuild",
            "Independent Judge",
        ):
            self.assertIn(marker, self.doc)

if __name__ == "__main__":
    unittest.main()
