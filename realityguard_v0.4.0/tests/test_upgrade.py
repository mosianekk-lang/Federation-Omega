from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from realityguard import FederationUpgradeAdapter, GovernedUpgradeEngine, RealityGuard, UpgradeDecisionCode
from realityguard.prebuild import manifest_snapshot_hash
from realityguard.schema import InputError


ROOT = Path(__file__).resolve().parents[1]


def capability(capability_id: str, provides: list[str], **extra) -> dict:
    return {
        "capability_id": capability_id,
        "name": capability_id,
        "provides": provides,
        "state": "VERIFIED_SCOPED",
        "current": True,
        "authority_ceiling": "A2",
        "source_ref": "test:" + capability_id,
        **extra,
    }


def manifest(*items: dict) -> dict:
    return {"capabilities": list(items)}


def request(capabilities: dict) -> dict:
    return {
        "cycle": {
            "cycle_id": "CYCLE-1", "kind": "FAILURE", "system_id": "REALITYGUARD", "material": True,
            "claim": "The system handles corrections proactively.",
            "observed_fruit": "The owner had to request the upgrade.",
            "desired_outcome": "Material failures trigger governed improvement without owner prompting.",
            "failure_code": "RG-028", "severity": "HIGH", "recurrence_count": 1,
            "metric": "avoidable_owner_prompt_count", "metric_breached": True,
            "claim_fruit_contradiction": True, "unsafe_route_active": False,
            "changed_source_ids": ["REALITYGUARD-CORE"],
        },
        "inventory": {
            "enumerated": True, "inspected_to_end": True, "snapshot_current": True,
            "snapshot_hash": manifest_snapshot_hash(capabilities), "sources": ["test:capability-manifest"],
        },
        "environment": {
            "environment_id": "LOCAL-TEST", "scope": "LOCAL_WORKSPACE_ONLY", "attested": True,
            "current": True, "evidence_refs": ["test:environment-readback"],
        },
        "candidate": {
            "component_id": "REALITYGUARD-0.4.0", "is_new_component": False,
            "existing_target_id": "REALITYGUARD-CORE", "provides": ["governed_auto_upgrade_assessment"],
            "preserve_capabilities": ["claim_detection"], "removed_capabilities": [],
            "authority_class": "A2", "recurring_cost": 0, "manual_user_tasks": [],
            "external_effects": False, "background_daemon": False,
            "foundation_model_modification": False,
            "regression_tests": ["test_material_failure_routes_to_existing_patch"],
            "healthy_case_tests": ["test_non_material_cycle_does_not_open_upgrade"],
            "rollback": "Remove the caller hook and restore the prior source revision.",
        },
        "dependencies": [
            {"artifact_id": "REPORT", "depends_on": ["REALITYGUARD-CORE"]},
            {"artifact_id": "MEMORY", "depends_on": ["REPORT"]},
        ],
        "governance": {
            "automatic_cycle_hook": True, "maximum_authority": "A2", "maximum_recurring_cost": 0,
            "manual_user_tasks_allowed": False, "external_execution_authorized": False,
        },
    }


class GovernedUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.capabilities = manifest(capability("REALITYGUARD-CORE", ["claim_detection"]))
        self.engine = GovernedUpgradeEngine()

    def test_material_failure_routes_to_existing_patch(self):
        result = self.engine.evaluate(request(self.capabilities), self.capabilities)
        self.assertEqual(result.decision, UpgradeDecisionCode.PATCH_EXISTING)
        self.assertTrue(result.automatic_assessment_invoked)
        self.assertTrue(result.formation_permit_required)
        self.assertFalse(result.automatic_execution_authorized)
        self.assertFalse(result.promotion_authorized)

    def test_non_material_cycle_does_not_open_upgrade(self):
        payload = request(self.capabilities)
        payload["cycle"]["material"] = False
        result = self.engine.evaluate(payload, self.capabilities)
        self.assertEqual(result.decision, UpgradeDecisionCode.NO_UPGRADE_REQUIRED)
        self.assertFalse(result.automatic_assessment_invoked)

    def test_weak_single_observation_is_observed(self):
        payload = request(self.capabilities)
        payload["cycle"].update({"severity": "MEDIUM", "metric_breached": False, "claim_fruit_contradiction": False, "recurrence_count": 1})
        self.assertEqual(self.engine.evaluate(payload, self.capabilities).decision, UpgradeDecisionCode.OBSERVE)

    def test_stale_inventory_is_observed_not_patched(self):
        payload = request(self.capabilities)
        payload["inventory"]["snapshot_current"] = False
        result = self.engine.evaluate(payload, self.capabilities)
        self.assertEqual(result.decision, UpgradeDecisionCode.OBSERVE)
        self.assertFalse(result.inventory_verified)

    def test_unattested_environment_is_observed_not_inherited(self):
        payload = request(self.capabilities)
        payload["environment"]["attested"] = False
        result = self.engine.evaluate(payload, self.capabilities)
        self.assertEqual(result.decision, UpgradeDecisionCode.OBSERVE)
        self.assertFalse(result.environment_attested)

    def test_missing_regression_evidence_is_observed(self):
        payload = request(self.capabilities)
        payload["candidate"]["regression_tests"] = []
        result = self.engine.evaluate(payload, self.capabilities)
        self.assertEqual(result.decision, UpgradeDecisionCode.OBSERVE)
        self.assertIn("original_failure_test", result.required_evidence)

    def test_new_duplicate_is_blocked(self):
        payload = request(self.capabilities)
        payload["candidate"].update({"is_new_component": True, "existing_target_id": "", "provides": ["claim_detection"]})
        self.assertEqual(self.engine.evaluate(payload, self.capabilities).decision, UpgradeDecisionCode.BLOCK_DUPLICATE_UPGRADE)

    def test_exact_residual_gap_creates_bounded_candidate(self):
        capabilities = manifest(capability("EXISTING", ["existing_control"]))
        payload = request(capabilities)
        payload["candidate"].update({"is_new_component": True, "existing_target_id": "", "provides": ["new_control"], "preserve_capabilities": ["existing_control"]})
        result = self.engine.evaluate(payload, capabilities)
        self.assertEqual(result.decision, UpgradeDecisionCode.CREATE_CANDIDATE)
        self.assertEqual(result.capability_gaps, ("new_control",))

    def test_capability_loss_blocks_safety_overcorrection(self):
        payload = request(self.capabilities)
        payload["candidate"]["removed_capabilities"] = ["claim_detection"]
        result = self.engine.evaluate(payload, self.capabilities)
        self.assertEqual(result.decision, UpgradeDecisionCode.BLOCK_UNSAFE_UPGRADE)
        self.assertEqual(result.capability_losses, ("claim_detection",))

    def test_unsafe_self_upgrade_routes_are_blocked(self):
        for field, value in (("background_daemon", True), ("foundation_model_modification", True), ("external_effects", True), ("recurring_cost", 1), ("authority_class", "A3")):
            with self.subTest(field=field):
                payload = request(self.capabilities)
                payload["candidate"][field] = value
                self.assertEqual(self.engine.evaluate(payload, self.capabilities).decision, UpgradeDecisionCode.BLOCK_UNSAFE_UPGRADE)

    def test_manual_user_burden_is_blocked_and_not_emitted(self):
        payload = request(self.capabilities)
        payload["candidate"]["manual_user_tasks"] = ["Ask the owner to copy the patch"]
        result = self.engine.evaluate(payload, self.capabilities)
        self.assertEqual(result.decision, UpgradeDecisionCode.BLOCK_UNSAFE_UPGRADE)
        self.assertEqual(result.manual_user_tasks, ())
        self.assertFalse(result.owner_action_required)

    def test_correction_debt_is_propagated_in_dependency_order(self):
        result = self.engine.evaluate(request(self.capabilities), self.capabilities)
        self.assertEqual(result.correction_debt_invalidated, ("MEMORY", "REPORT"))
        self.assertEqual(result.correction_repair_order, ("REPORT", "MEMORY"))

    def test_cyclic_correction_debt_blocks_upgrade(self):
        payload = request(self.capabilities)
        payload["dependencies"] = [{"artifact_id": "REALITYGUARD-CORE", "depends_on": ["REPORT"]}, {"artifact_id": "REPORT", "depends_on": ["REALITYGUARD-CORE"]}]
        self.assertEqual(self.engine.evaluate(payload, self.capabilities).decision, UpgradeDecisionCode.BLOCK_UNSAFE_UPGRADE)

    def test_decision_and_learning_ids_are_deterministic(self):
        first = self.engine.evaluate(request(self.capabilities), self.capabilities)
        second = self.engine.evaluate(copy.deepcopy(request(self.capabilities)), self.capabilities)
        self.assertEqual(first.decision_id, second.decision_id)
        self.assertEqual(first.learning_fingerprint, second.learning_fingerprint)

    def test_invalid_cycle_kind_fails_closed(self):
        payload = request(self.capabilities)
        payload["cycle"]["kind"] = "SOMEDAY"
        with self.assertRaises(InputError):
            self.engine.evaluate(payload, self.capabilities)

    def test_public_engine_exposes_upgrade_route(self):
        result = RealityGuard().upgrade(request(self.capabilities), self.capabilities)
        self.assertEqual(result["decision"], "PATCH_EXISTING")
        self.assertEqual(result["invocation_mode"], "HOST_INVOKED_AT_MATERIAL_CYCLE_BOUNDARY")


class UpgradeCliTests(unittest.TestCase):
    def run_cli(self, input_path: str, capabilities_path: str):
        return subprocess.run([sys.executable, "-m", "realityguard.cli", "upgrade", "--input", input_path, "--capabilities", capabilities_path], cwd=ROOT, text=True, capture_output=True, env={"PYTHONPATH": str(ROOT / "src")})

    def test_cli_emits_governed_upgrade_decision(self):
        capabilities = manifest(capability("REALITYGUARD-CORE", ["claim_detection"]))
        with tempfile.TemporaryDirectory() as temp:
            manifest_path, input_path = Path(temp) / "capabilities.json", Path(temp) / "upgrade.json"
            manifest_path.write_text(json.dumps(capabilities))
            input_path.write_text(json.dumps(request(capabilities)))
            proc = self.run_cli(str(input_path), str(manifest_path))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["decision"], "PATCH_EXISTING")

    def test_cli_uses_five_for_unsafe_upgrade(self):
        capabilities = manifest(capability("REALITYGUARD-CORE", ["claim_detection"]))
        payload = request(capabilities)
        payload["candidate"]["background_daemon"] = True
        with tempfile.TemporaryDirectory() as temp:
            manifest_path, input_path = Path(temp) / "capabilities.json", Path(temp) / "upgrade.json"
            manifest_path.write_text(json.dumps(capabilities))
            input_path.write_text(json.dumps(payload))
            proc = self.run_cli(str(input_path), str(manifest_path))
        self.assertEqual(proc.returncode, 5)
        self.assertEqual(json.loads(proc.stdout)["decision"], "BLOCK_UNSAFE_UPGRADE")


class FederationAdapterTests(unittest.TestCase):
    def adapter(self):
        return json.loads((ROOT / "federation/REALITYGUARD_AUTO_UPGRADE_ADAPTER.v1.json").read_text())

    def test_adapter_contract_declares_single_host_binding_candidate(self):
        value = self.adapter()
        declared = [item for item in value["systems"] if item["integration_state"] == "LIVE_BOUND_VERIFIED"]
        pending = [item for item in value["systems"] if item["integration_state"] == "ADAPTER_REQUIRED"]
        self.assertEqual([item["system_id"] for item in declared], ["SYS-FEDERATION-OMEGA"])
        self.assertEqual(len(pending), 19)
        self.assertTrue(declared[0]["current"])
        self.assertTrue(declared[0]["runtime_binding_evidence"])
        self.assertEqual(declared[0]["binding_scope"], "FEDERATION_GITHUB_ACTIONS_ACTIVE_HOST_ONLY")
        self.assertFalse(value["background_daemon"])
        self.assertFalse(value["promotion_authorized"])

    def test_one_source_adapter_accepts_every_registered_system(self):
        contract = self.adapter()
        capabilities = manifest(capability("REALITYGUARD-CORE", ["claim_detection"]))
        for entry in contract["systems"]:
            with self.subTest(system_id=entry["system_id"]):
                payload = request(capabilities)
                payload["cycle"]["system_id"] = entry["system_id"]
                result = FederationUpgradeAdapter().evaluate(payload, capabilities, contract)
                self.assertTrue(result["federation_adapter"]["source_adapter_supported"])
                self.assertTrue(result["federation_adapter"]["adapter_invocation_observed"])

    def test_source_invocation_never_self_certifies_target_runtime_binding(self):
        contract = self.adapter()
        capabilities = manifest(capability("REALITYGUARD-CORE", ["claim_detection"]))
        payload = request(capabilities)
        payload["cycle"]["system_id"] = contract["systems"][0]["system_id"]
        result = FederationUpgradeAdapter().evaluate(payload, capabilities, contract)
        state = result["federation_adapter"]
        self.assertTrue(state["adapter_invocation_observed"])
        self.assertTrue(state["contract_declares_binding"])
        self.assertTrue(state["runtime_binding_evidence_declared"])
        self.assertFalse(state["independent_runtime_binding_verifier_available"])
        self.assertFalse(state["target_runtime_binding_proven"])
        self.assertEqual(state["manual_user_tasks"], [])

        payload["cycle"]["system_id"] = contract["systems"][1]["system_id"]
        pending = FederationUpgradeAdapter().evaluate(payload, capabilities, contract)["federation_adapter"]
        self.assertFalse(pending["contract_declares_binding"])
        self.assertFalse(pending["target_runtime_binding_proven"])

    def test_contract_labels_and_receipt_references_are_not_independent_binding_proof(self):
        contract = self.adapter()
        capabilities = manifest(capability("REALITYGUARD-CORE", ["claim_detection"]))
        first = contract["systems"][0]
        self.assertEqual(first["integration_state"], "LIVE_BOUND_VERIFIED")
        self.assertTrue(first["runtime_binding_evidence"])
        payload = request(capabilities)
        payload["cycle"]["system_id"] = first["system_id"]
        state = FederationUpgradeAdapter().evaluate(payload, capabilities, contract)["federation_adapter"]
        self.assertTrue(state["contract_declares_binding"])
        self.assertFalse(state["target_runtime_binding_proven"])

    def test_unknown_system_fails_closed(self):
        contract = self.adapter()
        capabilities = manifest(capability("REALITYGUARD-CORE", ["claim_detection"]))
        payload = request(capabilities)
        payload["cycle"]["system_id"] = "SYS-NOT-REGISTERED"
        with self.assertRaises(InputError):
            FederationUpgradeAdapter().evaluate(payload, capabilities, contract)

    def test_unsafe_adapter_contract_fails_closed(self):
        contract = self.adapter()
        contract["background_daemon"] = True
        capabilities = manifest(capability("REALITYGUARD-CORE", ["claim_detection"]))
        with self.assertRaises(InputError):
            FederationUpgradeAdapter().evaluate(request(capabilities), capabilities, contract)


if __name__ == "__main__":
    unittest.main()
