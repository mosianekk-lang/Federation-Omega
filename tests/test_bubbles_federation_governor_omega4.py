from __future__ import annotations
import os, tempfile, time, unittest
from bubbles.federation_governor_omega4 import FederationGovernor, FederationWatchdog
from bubbles.federation_governor_omega4.registry import EvidenceRecord


class Omega4Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.gov = FederationGovernor(os.path.join(self.tmp.name, "omega4.sqlite3"))
        self.gov.register_project("TUT", "TUT Legal", "MATTER:TUT")
        self.gov.register_project("BIZ", "Business", "MATTER:BUSINESS")
        self.gov.register_mission(project_id="TUT", mission_id="M1",
            objective="Review Joel and Pule emails", origin_chat="legal-team",
            next_gate="legal synthesis", executable_next=True)

    def tearDown(self):
        self.gov.registry.close()
        self.tmp.cleanup()

    def test_thin_shim_and_capability_selection(self):
        shim = self.gov.bootstrap_chat(chat_key="C1", project_id="TUT", mission_id="M1",
            needed_tags=["legal", "labour", "evidence"],
            connectors=["Gmail", "Google Drive"], source_pointers=["gmail:joel", "gmail:pule"])
        self.assertLessEqual(len(str(shim).encode()), 4096)
        self.assertIn("Lex", shim["active_specialists"])
        self.assertIn("Ledger", shim["active_specialists"])

    def test_reuse_is_project_scoped(self):
        args = dict(project_id="TUT", objective="Review Joel and Pule emails",
            proof_gap="email content", action="read", target="gmail:joel", source_version="v1")
        self.assertEqual("EXECUTE_NEW", self.gov.preflight_work(**args)["decision"])
        self.gov.record_work(mission_id="M1", state="COMPLETE", result_pointer="receipt:1",
            semantic_ok=True, **args)
        self.assertEqual("REUSE_VERIFIED_RESULT", self.gov.preflight_work(**args)["decision"])
        other = dict(args); other["project_id"] = "BIZ"
        self.assertEqual("EXECUTE_NEW", self.gov.preflight_work(**other)["decision"])

    def test_project_scoped_stale_evidence(self):
        self.gov.put_evidence(EvidenceRecord(project_id="TUT", source_id="policy:1",
            source_type="drive", version="v1", verified=True))
        self.assertFalse(self.gov.registry.evidence_needs_refresh("TUT", "policy:1", version="v1"))
        self.assertTrue(self.gov.registry.evidence_needs_refresh("TUT", "policy:1", version="v2"))
        self.assertTrue(self.gov.registry.evidence_needs_refresh("BIZ", "policy:1", version="v1"))

    def test_inheritance_capsule(self):
        cap = self.gov.inheritance_capsule("TUT")
        self.assertIn("M1", cap["active_missions"])
        self.assertEqual("MATTER:TUT", cap["matter_wall"])

    def test_federation_health_correlation(self):
        self.gov.register_mission(project_id="TUT", mission_id="M2",
            objective="Review Joel and Pule emails", origin_chat="other", executable_next=True)
        with self.gov.registry._conn() as conn:
            conn.execute("UPDATE missions SET updated_at=? WHERE mission_id=?", (time.time()-2000, "M1"))
        report = FederationWatchdog(self.gov.registry).inspect(idle_seconds=1000)
        kinds = {item["type"] for item in report["findings"]}
        self.assertIn("POSSIBLE_DUPLICATE_MISSIONS", kinds)
        self.assertIn("IDLE_EXECUTABLE_MISSION", kinds)


if __name__ == "__main__":
    unittest.main()
