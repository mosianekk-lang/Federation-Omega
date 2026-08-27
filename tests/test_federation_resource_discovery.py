import unittest

from federation_resource_discovery import DISCOVERY_ORDER, classify_execution_route


FUNCTION = "sovaraProviderFabricStatusV2"
SOURCE_SHA = "18903d3b57fbb15b92f0605c969de712dbff37582629c4f13ca356f3bcc2ea36"
CAPABILITIES = [{"name": FUNCTION, "enabled": True}]
COMMANDS = [{
    "status": "DONE",
    "event": "MODULE_INSTALLED_FROM_DRIVE",
    "sourceSha256": SOURCE_SHA,
}]


class FederationResourceDiscoveryTests(unittest.TestCase):
    def test_failure_first_installed_without_receipt_is_not_route_exhaustion(self):
        result = classify_execution_route(
            function_name=FUNCTION,
            source_sha256=SOURCE_SHA,
            capabilities=CAPABILITIES,
            commands=COMMANDS,
            receipts=[],
        )
        self.assertEqual(result["state"], "INSTALLED_UNPROVEN")
        self.assertFalse(result["routeExhaustionAllowed"])
        self.assertEqual(result["checked"], DISCOVERY_ORDER)

    def test_healthy_path_requires_exact_source_bound_semantic_receipt(self):
        result = classify_execution_route(
            function_name=FUNCTION,
            source_sha256=SOURCE_SHA,
            capabilities=CAPABILITIES,
            commands=COMMANDS,
            receipts=[{
                "functionName": FUNCTION,
                "sourceSha256": SOURCE_SHA,
                "semanticState": "VERIFIED",
                "proofRef": "receipt:example",
            }],
        )
        self.assertEqual(result["state"], "VERIFIED_LIVE")
        self.assertEqual(result["proofRef"], "receipt:example")
        self.assertFalse(result["routeExhaustionAllowed"])


if __name__ == "__main__":
    unittest.main()
