import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from superior_logic.runtime import SuperiorLogicRuntime
from superior_logic.service import create_app


class APIOperationIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = SuperiorLogicRuntime(Path(self.tmp.name) / "api-operation.db")
        self.client = TestClient(create_app(self.runtime))

    def tearDown(self):
        self.client.close()
        self.runtime.close()
        self.tmp.cleanup()

    def test_mission_operation_id_replays_and_exposes_receipt(self):
        payload = {
            "owner": "Kim Kagiso Mosiane",
            "instruction": "Replay through the API",
            "operation_id": "api:mission:replay:0001",
        }
        first = self.client.post("/missions", json=payload)
        second = self.client.post("/missions", json=payload)

        self.assertEqual(200, first.status_code)
        self.assertEqual(200, second.status_code)
        self.assertEqual(first.json()["mission_id"], second.json()["mission_id"])
        self.assertEqual(payload["operation_id"], first.json()["operation_id"])
        self.assertEqual("MISSION_CREATED_OR_REPLAYED", first.json()["status"])

        receipt = self.client.get(f"/operations/{payload['operation_id']}")
        self.assertEqual(200, receipt.status_code)
        self.assertEqual("MISSION_CREATE", receipt.json()["operation_type"])
        self.assertEqual("API_CALLER_UNAUTHENTICATED", receipt.json()["principal"])
        self.assertEqual(first.json()["mission_id"], receipt.json()["result"]["mission_id"])

        state = self.client.get("/state").json()
        self.assertEqual(1, state["mission_count"])
        self.assertEqual(1, state["operation_count"])
        self.assertEqual(1, state["event_count"])

    def test_changed_payload_under_same_operation_id_returns_conflict(self):
        operation_id = "api:mission:conflict:0001"
        first = self.client.post(
            "/missions",
            json={
                "instruction": "Original API instruction",
                "operation_id": operation_id,
            },
        )
        conflict = self.client.post(
            "/missions",
            json={
                "instruction": "Changed API instruction",
                "operation_id": operation_id,
            },
        )

        self.assertEqual(200, first.status_code)
        self.assertEqual(409, conflict.status_code)
        self.assertIn("different", conflict.json()["detail"].lower())
        self.assertEqual(1, self.client.get("/state").json()["mission_count"])

    def test_capability_registration_is_replay_safe_through_api(self):
        payload = {
            "capability_id": "CAP-API-IDEMPOTENT",
            "name": "API idempotent capability",
            "state": "EXECUTABLE_NOW",
            "operation_id": "api:capability:replay:0001",
        }
        first = self.client.post("/capabilities/register", json=payload)
        second = self.client.post("/capabilities/register", json=payload)

        self.assertEqual(200, first.status_code)
        self.assertEqual(200, second.status_code)
        self.assertEqual("CAPABILITY_REGISTERED_OR_REPLAYED", first.json()["status"])
        state = self.client.get("/state").json()
        self.assertEqual(1, state["capability_count"])
        self.assertEqual(1, state["operation_count"])
        self.assertEqual(1, state["event_count"])

    def test_missing_operation_id_is_generated_and_returned(self):
        response = self.client.post(
            "/missions", json={"instruction": "Generate a safe operation identifier"}
        )
        self.assertEqual(200, response.status_code)
        operation_id = response.json()["operation_id"]
        self.assertEqual(32, len(operation_id))
        self.assertEqual(200, self.client.get(f"/operations/{operation_id}").status_code)

    def test_invalid_operation_id_is_rejected(self):
        response = self.client.post(
            "/missions",
            json={"instruction": "Invalid operation", "operation_id": "bad id!!"},
        )
        self.assertEqual(422, response.status_code)

    def test_health_is_truthful_about_authentication_boundary(self):
        payload = self.client.get("/health").json()
        self.assertIn("OPERATION_IDEMPOTENCY", payload["slrk_controls"])
        self.assertEqual("UNIMPLEMENTED", payload["application_authentication"])
        self.assertEqual(0, payload["operation_count"])


if __name__ == "__main__":
    unittest.main()
