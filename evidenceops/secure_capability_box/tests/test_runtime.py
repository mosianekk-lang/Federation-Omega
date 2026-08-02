import base64
import tempfile
import unittest
from pathlib import Path

from secure_capability_box.errors import InvalidRequest
from secure_capability_box.runtime import RuntimeConfig, build_runtime


class FakeProvider:
    name = "google-secret-manager"

    def access(self, _reference):
        return bytearray(b"fixture-token")

    def readiness(self):
        return {"state": "CONFIGURED", "production_ready": True}


class FakeConnector:
    name = "federation-omega"

    def execute(self, **_kwargs):
        return {"ok": True, "action": "STATUS"}

    def readiness(self):
        return {"state": "CONFIGURED", "production_ready": True}


def environment(path):
    return {
        "SCB_API_TOKEN": "api-token-fixture",
        "SCB_SIGNING_KEY": base64.urlsafe_b64encode(b"k" * 32).decode().rstrip("="),
        "SCB_KEY_ID": "scb-test-v1",
        "SCB_SUBJECT": "evidenceops-runtime",
        "SCB_AUDIENCE": "federation-omega",
        "SCB_AUTHORITY": "A1",
        "SCB_SECRET_PROJECT": "test-project",
        "SCB_SECRET_NAME": "fo-operator-admin-token",
        "SCB_SECRET_VERSION": "7",
        "SCB_ALLOWED_ACTIONS": "STATUS,READ_BUILD",
        "SCB_DB_PATH": str(path),
        "FO_OPERATOR_URL": "https://operator.example",
    }


class RuntimeTests(unittest.TestCase):
    def test_builds_fixed_identity_exact_version_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = build_runtime(
                environment(Path(folder) / "box.sqlite"),
                provider=FakeProvider(), connector=FakeConnector(),
            )
            request = runtime.request(
                mission_id="mission-001", mission_version=1,
                operation_id="operation-001", action="STATUS", ttl_seconds=60,
            )
            self.assertEqual("7", request.secret.version)
            self.assertEqual("evidenceops-runtime", request.identity.subject)
            self.assertTrue(runtime.broker.readiness()["production_ready"])
            runtime.broker.store.close()

    def test_latest_secret_version_fails_closed(self):
        values = environment("/tmp/not-created.sqlite")
        values["SCB_SECRET_VERSION"] = "latest"
        with self.assertRaises(RuntimeError):
            RuntimeConfig.from_env(values)

    def test_request_cannot_choose_an_unconfigured_action(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = build_runtime(
                environment(Path(folder) / "box.sqlite"),
                provider=FakeProvider(), connector=FakeConnector(),
            )
            with self.assertRaises(InvalidRequest):
                runtime.request(
                    mission_id="mission-001", mission_version=1,
                    operation_id="operation-001", action="DELETE", ttl_seconds=60,
                )
            runtime.broker.store.close()


if __name__ == "__main__":
    unittest.main()
