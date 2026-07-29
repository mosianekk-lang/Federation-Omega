import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from superior_logic.runtime import SuperiorLogicRuntime
from superior_logic.service import create_app


class ServiceAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = SuperiorLogicRuntime(Path(self.tmp.name) / "service.db")
        self.client = TestClient(create_app(self.runtime))

    def tearDown(self):
        self.client.close()
        self.runtime.close()
        self.tmp.cleanup()

    def test_health_exposes_slrk_controls(self):
        response = self.client.get("/health")
        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("3.2.0", payload["version"])
        self.assertTrue(payload["event_chain_valid"])
        self.assertIn("CLAIM_GOVERNOR", payload["slrk_controls"])

    def test_capability_register_and_assess(self):
        registered = self.client.post(
            "/capabilities/register",
            json={
                "capability_id": "CAP-DRIVE-WRITE",
                "name": "Drive write",
                "state": "EXECUTABLE_NOW",
                "can_write": True,
                "can_execute": True,
                "can_verify": True,
                "proof_required": "created object readback",
                "fallback_route": "drive-connector",
            },
        )
        self.assertEqual(200, registered.status_code)
        assessed = self.client.post(
            "/capabilities/assess",
            json={"required_capabilities": ["CAP-DRIVE-WRITE"]},
        )
        self.assertEqual("EXECUTABLE", assessed.json()["state"])

    def test_claim_governor_blocks_false_live_completion(self):
        response = self.client.post(
            "/claims/govern",
            json={
                "claim": "The federation is live, complete and fully automated.",
                "proof_level": 55,
            },
        )
        payload = response.json()
        self.assertFalse(payload["allowed"])
        self.assertIn("execution_verified", payload["missing_conditions"])
        self.assertIn("gap_scan_complete", payload["missing_conditions"])

    def test_fault_bans_route_and_requires_material_change_to_clear(self):
        created = self.client.post(
            "/faults",
            json={
                "fault_id": "ROUTE_REPEATED_FAILED_DEPLOY_FAULT",
                "layer_type": "ROUTE_LAYER",
                "detected_problem": "Known route failed twice",
                "banned_pattern": "Blind retry",
                "bypass_rule": "Use image deployment",
                "severity": "BLOCK",
                "proof_required": "New service-state proof",
                "route_id": "gcloud-source-deploy",
            },
        )
        self.assertEqual(
            "BANNED_UNLESS_CLEARED",
            created.json()["route"]["state"],
        )
        blocked = self.client.post(
            "/routes/gcloud-source-deploy/clear",
            json={"reason": "No material change", "conditions_changed": False},
        )
        self.assertEqual(409, blocked.status_code)
        cleared = self.client.post(
            "/routes/gcloud-source-deploy/clear",
            json={
                "reason": "Builder route repaired and reverified",
                "conditions_changed": True,
            },
        )
        self.assertEqual("AVAILABLE", cleared.json()["state"])

    def test_engine_production_promotion_fails_closed(self):
        response = self.client.post(
            "/engines/evaluate-promotion",
            json={
                "engine_id": "ENG-API-1",
                "target_environment": "PRODUCTION",
                "objective": "Protect completion claims",
                "risk_class": "HIGH",
                "profile_complete": True,
                "governor_attached": True,
                "fault_rules_attached": True,
                "proof_rules_attached": True,
                "tests_passed": True,
                "proof_ledger_written": True,
                "risk_accepted": True,
                "rollback_ready": False,
                "status_path_ready": True,
                "last_known_good_registered": True,
                "approval_granted": False,
                "live_readback_plan_ready": True,
            },
        )
        payload = response.json()
        self.assertEqual("BLOCKED", payload["decision"])
        self.assertIn("rollback_ready", payload["missing_gates"])
        self.assertIn("approval_granted", payload["missing_gates"])


if __name__ == "__main__":
    unittest.main()
