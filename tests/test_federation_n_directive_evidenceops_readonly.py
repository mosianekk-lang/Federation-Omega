from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "governance" / "federation_n_directive_evidenceops_readonly.py"
SPEC = importlib.util.spec_from_file_location("evidenceops_readonly", MODULE_PATH)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)
PACKET_PATH = ROOT / "tests" / "fixtures" / "federation_n_evidenceops_fevx_cse_v110.json"


def load_packet() -> dict:
    return json.loads(PACKET_PATH.read_text(encoding="utf-8"))


class EvidenceOpsRealReadonlyTests(unittest.TestCase):
    def test_packet_validates(self) -> None:
        result = MOD.validate_packet(load_packet())
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["evidence"]["source_count"], 4)
        self.assertGreaterEqual(result["evidence"]["provider_proof_count"], 8)

    def test_source_omission_fails_closed(self) -> None:
        packet = load_packet()
        packet["sources"].pop()
        result = MOD.validate_packet(packet)
        self.assertFalse(result["passed"])
        self.assertIn("SOURCE_COUNT_MISMATCH", {v["code"] for v in result["violations"]})

    def test_source_fingerprint_tamper_fails_closed(self) -> None:
        packet = load_packet()
        packet["sources"][0]["assertions"][0]["statement"] += " altered"
        result = MOD.validate_packet(packet)
        self.assertFalse(result["passed"])
        self.assertIn("SOURCE_FINGERPRINT_MISMATCH", {v["code"] for v in result["violations"]})

    def test_secret_like_material_is_rejected(self) -> None:
        packet = load_packet()
        packet["objective"] = "unsafe " + "sk" + "-" + ("x" * 32)
        result = MOD.validate_packet(packet)
        self.assertFalse(result["passed"])
        self.assertIn("SECRET_LIKE_MATERIAL_REJECTED", {v["code"] for v in result["violations"]})

    def test_authority_or_external_effect_tamper_is_rejected(self) -> None:
        packet = load_packet()
        packet["external_effect"] = True
        result = MOD.validate_packet(packet)
        self.assertFalse(result["passed"])
        self.assertIn("PACKET_FIELD_MISMATCH", {v["code"] for v in result["violations"]})

    def test_canonical_state_preserves_provider_boundary(self) -> None:
        result = MOD.build_experiment(load_packet())
        state = result["canonical_control_state"]
        self.assertEqual(state["validation_state"], "STATICALLY_VALIDATED_AND_LOCAL_CANARY_PASSED")
        self.assertEqual(state["provider_state"], "PROVIDER_AUTHORITY_REPAIR_REQUIRED")
        self.assertEqual(state["external_runtime"], "STAGED_NOT_RUNNING")
        self.assertFalse(state["provider_mutation_attempted"])
        self.assertEqual(state["deployment_truth"], "NOT_DEPLOYED_PROVIDER_RUNTIME_UNVERIFIED")

    def test_maturity_scope_does_not_promote_simulation(self) -> None:
        result = MOD.build_experiment(load_packet())
        state = result["canonical_control_state"]
        self.assertEqual(state["current_verified_level"], 3)
        self.assertEqual(state["highest_demonstrated_level"], 4)
        self.assertEqual(state["highest_level_state"], "SIMULATION_PASSED")
        self.assertEqual(result["proof_and_maturity"]["real_world_intelligence_gain"], "UNVERIFIED")

    def test_cross_source_tensions_are_resolved_by_scope(self) -> None:
        result = MOD.build_experiment(load_packet())
        tensions = result["cross_source_tensions"]
        self.assertEqual(len(tensions), 2)
        self.assertEqual(
            {item["result"] for item in tensions},
            {"RESOLVED_BY_SCOPE_SEPARATION", "RESOLVED_BY_MATURITY_SCOPE"},
        )

    def test_gap_schedule_preserves_every_provider_proof_requirement(self) -> None:
        packet = load_packet()
        result = MOD.build_experiment(packet)
        self.assertEqual(len(result["gap_schedule"]), len(packet["required_provider_proof"]))
        self.assertTrue(
            all(item["state"] == "UNVERIFIED_PENDING_PROVIDER_READBACK" for item in result["gap_schedule"])
        )

    def test_formation_tournament_has_three_routes_and_selects_composition(self) -> None:
        result = MOD.build_experiment(load_packet())
        formation = result["formation_engine_result"]
        self.assertEqual(set(formation["route_families"]), MOD.REQUIRED_ROUTE_FAMILIES)
        self.assertEqual(formation["selected_route_family"], "COMPOSE_OR_EXTEND")
        self.assertEqual(len(formation["route_alternatives"]), 3)

    def test_control_completeness_delta_is_measured_not_overpromoted(self) -> None:
        result = MOD.build_experiment(load_packet())
        metrics = result["metrics"]
        self.assertEqual(metrics["baseline_control_coverage"]["covered"], 3)
        self.assertEqual(metrics["treatment_control_coverage"]["covered"], 8)
        self.assertEqual(metrics["control_completeness_delta"], 5)
        self.assertEqual(result["performance_boundary"]["measured"], "CONTROL_COMPLETENESS_DELTA_ON_REAL_REGISTERED_SOURCE_PACKET")

    def test_result_is_deterministic(self) -> None:
        packet = load_packet()
        first = MOD.build_experiment(packet)
        second = MOD.build_experiment(packet)
        self.assertEqual(first, second)
        self.assertTrue(MOD.verify_result(first)["passed"])

    def test_receipt_tamper_is_detected(self) -> None:
        result = MOD.build_experiment(load_packet())
        result["metrics"]["authority_violations"] = 1
        check = MOD.verify_result(result)
        self.assertFalse(check["passed"])
        self.assertIn("RESULT_RECEIPT_MISMATCH", {v["code"] for v in check["violations"]})

    def test_overclaim_is_rejected(self) -> None:
        result = MOD.build_experiment(load_packet())
        result["release_claims"].append("Cloud Run deployed and production live")
        without_receipt = copy.deepcopy(result)
        without_receipt.pop("receipt_sha256", None)
        result["receipt_sha256"] = MOD.canonical_sha256(without_receipt)
        check = MOD.verify_result(result)
        self.assertFalse(check["passed"])
        self.assertIn("PROHIBITED_RELEASE_OVERCLAIM", {v["code"] for v in check["violations"]})

    def test_cli_emits_verified_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "result.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(MODULE_PATH),
                    "--packet",
                    str(PACKET_PATH),
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["verification"]["passed"])
            self.assertEqual(
                payload["experiment"]["status"],
                "REAL_REGISTERED_SOURCE_CONTROL_STATE_PASSED_READ_ONLY",
            )


if __name__ == "__main__":
    unittest.main()
