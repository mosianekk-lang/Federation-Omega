import unittest

from ops.architron_semantic_contract import SemanticContractError, validate_action_response


def _generic_health():
    return {
        "body": {
            "runtime": "architron-unified-core",
            "version": "v11.0-UNIFIED-SOVEREIGNTY",
            "cloudRunService": "architron9",
            "project": "sov-hybrid-suite",
            "healthOk": True,
        }
    }


class ArchitronSemanticContractTests(unittest.TestCase):
    def assert_generic_health_rejected(self, action: str) -> None:
        with self.assertRaises(SemanticContractError) as ctx:
            validate_action_response(action, _generic_health())
        self.assertIn("collapsed to generic runtime health", str(ctx.exception))

    def test_identity_rejects_generic_health(self):
        self.assert_generic_health_rejected("GET_RUNTIME_IDENTITY")

    def test_project_rejects_generic_health(self):
        self.assert_generic_health_rejected("GET_PROJECT_INFO")

    def test_service_rejects_generic_health(self):
        self.assert_generic_health_rejected("GET_CLOUD_RUN_SERVICE")

    def test_service_account_inventory_rejects_generic_health(self):
        self.assert_generic_health_rejected("LIST_SERVICE_ACCOUNTS")

    def test_identity_accepts_action_specific_payload(self):
        body = {"runtimeIdentity": {"principal": "example@project.iam.gserviceaccount.com"}}
        self.assertEqual(
            body,
            validate_action_response("GET_RUNTIME_IDENTITY", {"body": body}),
        )

    def test_project_accepts_action_specific_payload(self):
        body = {"projectInfo": {"projectId": "sov-hybrid-suite"}}
        self.assertEqual(
            body,
            validate_action_response("GET_PROJECT_INFO", {"body": body}),
        )

    def test_service_accepts_action_specific_payload(self):
        body = {"service": {"name": "architron9", "region": "africa-south1"}}
        self.assertEqual(
            body,
            validate_action_response("GET_CLOUD_RUN_SERVICE", {"body": body}),
        )

    def test_service_account_inventory_accepts_action_specific_payload(self):
        body = {
            "serviceAccounts": [
                {"email": "reader@sov-hybrid-suite.iam.gserviceaccount.com"}
            ]
        }
        self.assertEqual(
            body,
            validate_action_response("LIST_SERVICE_ACCOUNTS", {"body": body}),
        )

    def test_service_account_inventory_requires_canonical_readback_key(self):
        with self.assertRaises(SemanticContractError) as ctx:
            validate_action_response(
                "LIST_SERVICE_ACCOUNTS",
                {"body": {"accounts": ["not-action-specific-enough"]}},
            )
        self.assertIn("serviceAccounts", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
