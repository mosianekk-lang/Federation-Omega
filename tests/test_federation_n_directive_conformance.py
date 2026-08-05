from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "governance" / "federation_n_directive_conformance.py"
SPEC = importlib.util.spec_from_file_location(
    "federation_n_directive_conformance",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
CONFORMANCE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CONFORMANCE
SPEC.loader.exec_module(CONFORMANCE)

BOOTSTRAP = ROOT / "governance" / "federation_node_bootstrap_v2.json"
POLICY = ROOT / "governance" / "federation_n_directive_v2.yaml"
INVALID_FIXTURE = (
    ROOT / "tests" / "fixtures" / "federation_n_future_node_invalid.json"
)
VALID_FIXTURE = (
    ROOT / "tests" / "fixtures" / "federation_n_future_node_valid.json"
)


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


class FederationNDirectiveConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bootstrap = load_json(BOOTSTRAP)
        cls.invalid_fixture = load_json(INVALID_FIXTURE)
        cls.valid_fixture = load_json(VALID_FIXTURE)
        cls.policy_text = POLICY.read_text(encoding="utf-8")

    def test_invalid_future_node_fails_closed(self) -> None:
        result = CONFORMANCE.validate_future_node_fixture(
            self.invalid_fixture,
            self.bootstrap,
        )
        self.assertFalse(result["passed"])
        self.assertEqual("BOOTSTRAP_BLOCKED_FAIL_CLOSED", result["status"])
        codes = {item["code"] for item in result["violations"]}
        self.assertIn("POLICY_VERSION_TOO_OLD", codes)
        self.assertIn("ENGINE_INHERITANCE_MISSING", codes)
        self.assertIn("FIXTURE_EXTERNAL_EFFECT_NOT_FALSE", codes)
        self.assertIn("FIXTURE_TRUST_INHERITANCE_NOT_FALSE", codes)
        self.assertIn("FIXTURE_OUTPUT_FIELD_MISSING", codes)
        self.assertIn("FIXTURE_INNOVATION_EVENTS_INCOMPLETE", codes)
        self.assertIn("DIRECTIVE_NOT_N", codes)

    def test_corrected_future_node_passes(self) -> None:
        first = CONFORMANCE.validate_future_node_fixture(
            self.valid_fixture,
            self.bootstrap,
        )
        second = CONFORMANCE.validate_future_node_fixture(
            self.valid_fixture,
            self.bootstrap,
        )
        self.assertTrue(first["passed"])
        self.assertEqual("BOOTSTRAP_PASSED", first["status"])
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])
        self.assertFalse(first["external_effect"])
        self.assertEqual("A1_INTERNAL", first["authority_ceiling"])

    def test_generated_canary_contains_both_engines_and_frontier(self) -> None:
        canary = CONFORMANCE.run_synthetic_n_canary(
            self.valid_fixture,
            self.bootstrap,
            self.policy_text,
        )
        validation = CONFORMANCE.validate_canary_receipt(canary)
        self.assertTrue(validation["passed"])
        self.assertEqual(
            "PASSED",
            canary["formation_engine_result"]["status"],
        )
        self.assertEqual(
            "PASSED",
            canary["alpha_omega_foundry_result"]["status"],
        )
        self.assertEqual(3, len(canary["solution_alternatives_considered"]))
        self.assertEqual(4, len(canary["innovation_frontier"]))
        self.assertEqual(
            1,
            sum(
                item["selected"] is True
                for item in canary["innovation_frontier"]
            ),
        )
        self.assertEqual(
            "SUCCESS",
            canary["learning_delta"]["terminal_event"],
        )
        self.assertEqual("n = proceed", canary["continuation"])
        self.assertFalse(canary["proof_and_maturity"]["external_effect"])
        self.assertFalse(canary["proof_and_maturity"]["provider_mutation"])
        self.assertFalse(canary["proof_and_maturity"]["trust_transfer"])

    def test_first_viable_route_cannot_skip_innovation_frontier(self) -> None:
        canary = CONFORMANCE.run_synthetic_n_canary(
            self.valid_fixture,
            self.bootstrap,
            self.policy_text,
        )
        tampered = copy.deepcopy(canary)
        tampered["innovation_frontier"] = tampered["innovation_frontier"][:1]
        unhashed = dict(tampered)
        unhashed.pop("receipt_sha256", None)
        tampered["receipt_sha256"] = CONFORMANCE.canonical_sha256(unhashed)

        validation = CONFORMANCE.validate_canary_receipt(tampered)
        self.assertFalse(validation["passed"])
        self.assertIn(
            "INNOVATION_FRONTIER_INCOMPLETE",
            {item["code"] for item in validation["violations"]},
        )

    def test_receipt_tamper_is_detected(self) -> None:
        canary = CONFORMANCE.run_synthetic_n_canary(
            self.valid_fixture,
            self.bootstrap,
            self.policy_text,
        )
        canary["selected_solution"]["dominance_reason"] = "tampered"
        validation = CONFORMANCE.validate_canary_receipt(canary)
        self.assertFalse(validation["passed"])
        self.assertIn(
            "CANARY_RECEIPT_HASH_MISMATCH",
            {item["code"] for item in validation["violations"]},
        )

    def test_bundle_proves_negative_positive_and_canary_paths(self) -> None:
        first = CONFORMANCE.build_conformance_bundle(
            bootstrap=self.bootstrap,
            policy_text=self.policy_text,
            invalid_fixture=self.invalid_fixture,
            valid_fixture=self.valid_fixture,
        )
        second = CONFORMANCE.build_conformance_bundle(
            bootstrap=self.bootstrap,
            policy_text=self.policy_text,
            invalid_fixture=self.invalid_fixture,
            valid_fixture=self.valid_fixture,
        )
        self.assertTrue(first["passed"])
        self.assertEqual("CONFORMANCE_VERIFIED_SYNTHETIC", first["status"])
        self.assertTrue(
            first["invalid_fixture_experiment"][
                "expected_failure_observed"
            ]
        )
        self.assertEqual(
            "BOOTSTRAP_PASSED",
            first["valid_fixture_experiment"]["observed"],
        )
        self.assertEqual(
            "SUCCESS",
            first["terminal_learning_event"]["event"],
        )
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])
        self.assertFalse(first["external_effect"])
        self.assertEqual("n = proceed", first["continuation"])

        unhashed = dict(first)
        claimed = unhashed.pop("receipt_sha256")
        self.assertEqual(CONFORMANCE.canonical_sha256(unhashed), claimed)

    def test_cli_executes_complete_fixture(self) -> None:
        process = subprocess.run(
            [sys.executable, str(MODULE_PATH)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, process.returncode, process.stderr)
        payload = json.loads(process.stdout)
        self.assertTrue(payload["passed"])
        self.assertEqual("CONFORMANCE_VERIFIED_SYNTHETIC", payload["status"])
        self.assertEqual("n = proceed", payload["continuation"])


if __name__ == "__main__":
    unittest.main()
