import json
import tempfile
import unittest
from pathlib import Path

from evidenceops.cloud_capability.capability import CloudCapability, CloudCapabilityError
from evidenceops.cloud_capability.inheritance import CONTRACT_REF, audit_inheritance


class RecordingTransport:
    def __init__(self):
        self.calls = []

    def call(self, **kwargs):
        self.calls.append(kwargs)
        return {"projectId": "sov-hybrid-suite", "state": "READBACK_VERIFIED"}


class CloudCapabilityTests(unittest.TestCase):
    def test_all_evidenceops_element_classes_inherit_full_control(self):
        capability = CloudCapability.load(env={})
        for element in (
            "evidenceops://systems/root", "evidenceops://subsystems/heartbeat",
            "evidenceops://ai-agents/researcher", "evidenceops://workers/deployer",
            "evidenceops://nodes/kimmie", "evidenceops://elements/new-component",
        ):
            context = capability.inherited_context(element)
            self.assertTrue(context["inherited"])
            self.assertEqual("FULL_PROJECT_CONTROL", context["control_breadth"])
            self.assertFalse(context["raw_credentials"])

    def test_diluted_contract_is_rejected(self):
        contract = json.loads(Path("evidenceops/cloud_capability/contract.json").read_text())
        contract["scope"]["control_breadth"] = "READ_ONLY"
        with self.assertRaises(CloudCapabilityError):
            CloudCapability.validate_contract(contract)

    def test_unbound_runtime_fails_closed_without_losing_inheritance(self):
        capability = CloudCapability.load(env={})
        self.assertEqual("SOURCE_REGISTERED_RUNTIME_UNBOUND", capability.readiness()["state"])
        with self.assertRaises(CloudCapabilityError):
            capability.call("omega_status")

    def test_bound_runtime_calls_operator_and_returns_semantic_readback(self):
        transport = RecordingTransport()
        capability = CloudCapability.load(
            env={"OMEGA_MCP_URL": "https://operator.example/mcp", "OMEGA_MCP_SHARED_SECRET": "x" * 40},
            transport=transport,
        )
        result = capability.call("omega_inventory")
        self.assertEqual("READBACK_VERIFIED", result["state"])
        self.assertEqual("omega_inventory", transport.calls[0]["tool"])
        self.assertNotIn("x" * 40, str(result))

    def test_inheritance_audit_detects_and_closes_missing_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "evidenceops" / "child" / "BUILD_CONTRACT.json"
            path.parent.mkdir(parents=True)
            path.write_text("{}", encoding="utf-8")
            self.assertFalse(audit_inheritance(root)["all_bound"])
            path.write_text(json.dumps({"cloud_capability_inheritance": {
                "required": True, "contract_ref": CONTRACT_REF,
            }}), encoding="utf-8")
            self.assertTrue(audit_inheritance(root)["all_bound"])


if __name__ == "__main__":
    unittest.main()
