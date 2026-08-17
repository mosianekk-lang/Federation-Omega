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
    def test_provider_actions_reject_generic_health(self):
        actions = [
            "GET_RUNTIME_IDENTITY",
            "GET_PROJECT_INFO",
            "GET_CLOUD_RUN_SERVICE",
            "LIST_CLOUD_RUN_SERVICES",
            "LIST_CLOUD_BUILD_BUILDS",
            "LIST_CLOUD_SCHEDULER_JOBS",
            "LIST_CLOUD_SCHEDULER_JOBS_ALL_REGIONS",
            "LIST_PUBSUB_TOPICS",
            "LIST_SERVICE_ACCOUNTS",
            "LIST_SECRET_NAMES",
        ]
        for action in actions:
            with self.subTest(action=action):
                with self.assertRaisesRegex(
                    SemanticContractError, "collapsed to generic runtime health"
                ):
                    validate_action_response(action, _generic_health())

    def test_identity_accepts_action_specific_payload(self):
        body = {
            "runtimeIdentity": {
                "principal": "example@project.iam.gserviceaccount.com",
                "identitySource": "provider",
            }
        }
        self.assertEqual(
            body,
            validate_action_response("GET_RUNTIME_IDENTITY", {"body": body}),
        )

    def test_project_requires_id_and_number(self):
        with self.assertRaisesRegex(SemanticContractError, "projectNumber"):
            validate_action_response(
                "GET_PROJECT_INFO",
                {"body": {"projectInfo": {"projectId": "example"}}},
            )

        body = {"projectInfo": {"projectId": "example", "projectNumber": "123"}}
        self.assertEqual(
            body,
            validate_action_response("GET_PROJECT_INFO", {"body": body}),
        )

    def test_service_requires_identity_and_provider_locator(self):
        with self.assertRaisesRegex(
            SemanticContractError, "at least one provider field"
        ):
            validate_action_response(
                "GET_CLOUD_RUN_SERVICE",
                {
                    "body": {
                        "service": {
                            "name": "architron9",
                            "region": "africa-south1",
                        }
                    }
                },
            )

        body = {
            "service": {
                "name": "architron9",
                "region": "africa-south1",
                "latestReadyRevision": "architron9-00001-test",
            }
        }
        self.assertEqual(
            body,
            validate_action_response("GET_CLOUD_RUN_SERVICE", {"body": body}),
        )

    def test_inventory_actions_require_typed_lists(self):
        cases = [
            ("LIST_CLOUD_RUN_SERVICES", "services"),
            ("LIST_CLOUD_BUILD_BUILDS", "builds"),
            ("LIST_CLOUD_SCHEDULER_JOBS", "jobs"),
            ("LIST_CLOUD_SCHEDULER_JOBS_ALL_REGIONS", "jobs"),
            ("LIST_PUBSUB_TOPICS", "topics"),
            ("LIST_SERVICE_ACCOUNTS", "serviceAccounts"),
            ("LIST_SECRET_NAMES", "secretNames"),
        ]
        for action, key in cases:
            with self.subTest(action=action, key=key):
                with self.assertRaisesRegex(SemanticContractError, "not a list"):
                    validate_action_response(
                        action, {"body": {key: {"wrong": "shape"}}}
                    )

                body = {key: []}
                self.assertEqual(
                    body,
                    validate_action_response(action, {"body": body}),
                )


if __name__ == "__main__":
    unittest.main()
