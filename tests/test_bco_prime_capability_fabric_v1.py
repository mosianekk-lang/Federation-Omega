from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

from benchmarking.cfbe_omega import bco_prime_capability_fabric_v1 as fabric
from benchmarking.cfbe_omega.bco_prime_meta_executive_v1 import prime_capability_manifest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "benchmarking" / "cfbe_omega" / "BCO_PRIME_CAPABILITY_FABRIC_V1.json"


class BCOPrimeCapabilityFabricV1Tests(unittest.TestCase):
    def test_contract_and_registry_are_exactly_ten_by_ten(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual("BCO_PRIME_CAPABILITY_FABRIC_V1", contract["schema"])
        self.assertEqual(10, len(contract["domains"]))
        self.assertTrue(all(len(item["operations"]) == 10 for item in contract["domains"]))
        self.assertEqual(100, len(fabric.CAPABILITY_SPECS))
        self.assertEqual(100, len(fabric.FUNCTION_REGISTRY))
        self.assertEqual(100, len({item.capability_id for item in fabric.CAPABILITY_SPECS}))
        self.assertEqual(100, len({item.function_name for item in fabric.CAPABILITY_SPECS}))

    def test_all_one_hundred_functions_are_callable_zero_manual_and_no_effect(self):
        for spec in fabric.CAPABILITY_SPECS:
            function = getattr(fabric, spec.function_name)
            self.assertIs(function, fabric.FUNCTION_REGISTRY[spec.capability_id])
            receipt = function({})
            self.assertEqual("SUCCESS", receipt["status"])
            self.assertEqual(spec.capability_id, receipt["capability_id"])
            self.assertEqual([], receipt["manual_user_tasks"])
            self.assertFalse(receipt["owner_action_required"])
            self.assertFalse(receipt["external_effect"])
            self.assertFalse(receipt["provider_effect_authorized"])
            self.assertFalse(receipt["authority_expansion"])
            self.assertEqual(64, len(receipt["receipt_sha256"]))

    def test_receipts_are_deterministic_and_input_sensitive(self):
        payload = {"objective": "  improve   BCO Prime ", "values": [3, 1, 2]}
        first = fabric.execute_capability("BCO-PRIME-CAP-001", payload)
        second = fabric.execute_capability("BCO-PRIME-CAP-001", payload)
        changed = fabric.execute_capability("BCO-PRIME-CAP-001", {"objective": "different"})
        self.assertEqual(first, second)
        self.assertNotEqual(first["receipt_sha256"], changed["receipt_sha256"])

    def test_manual_external_and_authority_expansion_requests_fail_closed(self):
        prohibited = (
            {"manual_user_tasks": ["click something"]},
            {"external_effect": True},
            {"provider_effect_authorized": True},
            {"authority_expansion": True},
        )
        for payload in prohibited:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, "CAPABILITY_FABRIC_BOUNDARY"):
                    fabric.execute_capability("BCO-PRIME-CAP-001", payload)

    def test_unknown_capability_fails_closed(self):
        with self.assertRaisesRegex(KeyError, "UNKNOWN_BCO_PRIME_CAPABILITY"):
            fabric.execute_capability("BCO-PRIME-CAP-999", {})

    def test_dependency_order_and_cycle_detection_are_executable(self):
        payload = {
            "nodes": [
                {"id": "build", "depends_on": ["design"]},
                {"id": "design", "depends_on": []},
                {"id": "test", "depends_on": ["build"]},
            ]
        }
        receipt = fabric.cap_021_dependency_order(payload)
        self.assertEqual(["design", "build", "test"], receipt["output"]["ordered"])
        with self.assertRaisesRegex(ValueError, "DEPENDENCY_CYCLE"):
            fabric.cap_021_dependency_order(
                {"nodes": [{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}]}
            )

    def test_secret_scan_reports_shape_without_echoing_secret(self):
        secret = "sk-" + "x" * 32
        receipt = fabric.cap_053_secret_indicators({"text": f"prefix {secret} suffix"})
        rendered = json.dumps(receipt, sort_keys=True)
        self.assertTrue(receipt["output"]["secret_indicator_detected"])
        self.assertNotIn(secret, rendered)

    def test_cli_lists_and_executes_capabilities(self):
        listing = subprocess.run(
            [sys.executable, "-m", "benchmarking.cfbe_omega.bco_prime_capability_fabric_v1", "list"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(100, len(json.loads(listing.stdout)["capabilities"]))
        execution = subprocess.run(
            [
                sys.executable,
                "-m",
                "benchmarking.cfbe_omega.bco_prime_capability_fabric_v1",
                "run",
                "BCO-PRIME-CAP-001",
                "--payload-json",
                '{"objective":"  zero manual   evolution "}',
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        receipt = json.loads(execution.stdout)
        self.assertEqual("zero manual evolution", receipt["output"]["normalized_objective"])

    def test_meta_executive_manifest_binds_fabric_without_new_authority(self):
        manifest = prime_capability_manifest()
        self.assertEqual("BCO_PRIME_CAPABILITY_FABRIC_V1", manifest["capability_fabric"])
        self.assertEqual(100, manifest["zero_manual_capability_functions"])
        self.assertFalse(manifest["capability_fabric_external_effect_authority"])
        self.assertEqual(0, manifest["new_authority_planes"])


if __name__ == "__main__":
    unittest.main()
