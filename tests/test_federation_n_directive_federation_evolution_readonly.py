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
MODULE_PATH = (
    ROOT / "governance" /
    "federation_n_directive_federation_evolution_readonly.py"
)
SPEC = importlib.util.spec_from_file_location(
    "federation_evolution_readonly", MODULE_PATH
)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)
PACKET_PATH = (
    ROOT / "tests" / "fixtures" /
    "federation_n_federation_evolution_packet.json"
)


def load_packet() -> dict:
    return json.loads(PACKET_PATH.read_text(encoding="utf-8"))


class FederationEvolutionRealReadonlyTests(unittest.TestCase):
    def test_packet_validates(self) -> None:
        result = MOD.validate_packet(load_packet())
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["evidence"]["source_count"], 4)
        self.assertGreaterEqual(result["evidence"]["future_proof_count"], 8)

    def test_source_omission_fails_closed(self) -> None:
        packet = load_packet()
        packet["sources"].pop()
        result = MOD.validate_packet(packet)
        self.assertFalse(result["passed"])
        self.assertIn(
            "SOURCE_COUNT_MISMATCH",
            {item["code"] for item in result["violations"]},
        )

    def test_source_fingerprint_tamper_fails_closed(self) -> None:
        packet = load_packet()
        packet["sources"][0]["assertions"][0]["statement"] += " altered"
        result = MOD.validate_packet(packet)
        self.assertFalse(result["passed"])
        self.assertIn(
            "SOURCE_FINGERPRINT_MISMATCH",
            {item["code"] for item in result["violations"]},
        )

    def test_secret_like_material_is_rejected(self) -> None:
        packet = load_packet()
        packet["objective"] = "unsafe " + "s" + "k-" + ("x" * 32)
        result = MOD.validate_packet(packet)
        self.assertFalse(result["passed"])
        self.assertIn(
            "SECRET_LIKE_MATERIAL_REJECTED",
            {item["code"] for item in result["violations"]},
        )

    def test_authority_external_effect_or_trust_tamper_is_rejected(self) -> None:
        packet = load_packet()
        packet["trust_transfer_permitted"] = True
        result = MOD.validate_packet(packet)
        self.assertFalse(result["passed"])
        self.assertIn(
            "PACKET_FIELD_MISMATCH",
            {item["code"] for item in result["violations"]},
        )

    def test_canonical_state_preserves_exact_maturity(self) -> None:
        result = MOD.build_experiment(load_packet())
        state = result["canonical_control_state"]
        self.assertEqual(state["algorithm_count"], 15)
        self.assertEqual(
            state["foundry_target_maturity"],
            "PROVIDER_INDEPENDENT_RUNTIME_REPLICATION_AND_REAL_WORKFLOW_CALIBRATION",
        )
        self.assertEqual(state["provider_runtime_state"], "UNVERIFIED")
        self.assertFalse(state["provider_mutation_performed"])

    def test_lineage_preserves_two_parents(self) -> None:
        result = MOD.build_experiment(load_packet())
        lineage = result["lineage_graph"]
        self.assertEqual(len(result["canonical_control_state"]["parent_shas"]), 2)
        parent_edges = [
            item for item in lineage["edges"] if item["relation"] == "PARENT"
        ]
        self.assertEqual(len(parent_edges), 2)
        self.assertFalse(lineage["trust_transfer"])

    def test_no_trust_transfer_is_explicit(self) -> None:
        result = MOD.build_experiment(load_packet())
        self.assertFalse(result["no_trust_transfer"]["permitted"])
        self.assertFalse(result["no_trust_transfer"]["performed"])
        self.assertFalse(result["trust_transfer_performed"])

    def test_cross_source_tensions_are_scope_resolved(self) -> None:
        result = MOD.build_experiment(load_packet())
        tensions = result["cross_source_tensions"]
        self.assertEqual(len(tensions), 3)
        self.assertEqual(
            {item["result"] for item in tensions},
            {
                "RESOLVED_BY_EXACT_MATURITY_SEPARATION",
                "RESOLVED_BY_SOURCE_RUNTIME_SEPARATION",
                "RESOLVED_BY_SIMULATION_PROVIDER_SEPARATION",
            },
        )

    def test_future_proof_schedule_preserves_every_gap(self) -> None:
        packet = load_packet()
        result = MOD.build_experiment(packet)
        self.assertEqual(
            len(result["proof_schedule"]),
            len(packet["required_future_proof"]),
        )
        self.assertTrue(
            all(
                item["state"] == "UNVERIFIED_PENDING_FRESH_PROOF"
                for item in result["proof_schedule"]
            )
        )

    def test_formation_tournament_selects_composition(self) -> None:
        result = MOD.build_experiment(load_packet())
        formation = result["formation_engine_result"]
        self.assertEqual(
            set(formation["route_families"]),
            MOD.REQUIRED_ROUTE_FAMILIES,
        )
        self.assertEqual(
            formation["selected_route_family"],
            "COMPOSE_OR_EXTEND",
        )
        self.assertEqual(len(formation["route_alternatives"]), 3)

    def test_control_completeness_delta_is_five(self) -> None:
        result = MOD.build_experiment(load_packet())
        metrics = result["metrics"]
        self.assertEqual(
            metrics["baseline_control_coverage"]["covered"], 4
        )
        self.assertEqual(
            metrics["treatment_control_coverage"]["covered"], 9
        )
        self.assertEqual(metrics["control_completeness_delta"], 5)
        self.assertEqual(
            result["performance_boundary"]["measured"],
            (
                "CONTROL_COMPLETENESS_DELTA_ON_REAL_REGISTERED_"
                "FEDERATION_EVOLUTION_PACKET"
            ),
        )

    def test_rollback_remains_unverified_at_provider(self) -> None:
        result = MOD.build_experiment(load_packet())
        rollback = result["regression_and_rollback"]
        self.assertTrue(rollback["rollback_plan_required"])
        self.assertFalse(
            rollback["rollback_simulation_proves_provider_rollback"]
        )
        self.assertEqual(
            rollback["provider_rollback_execution"], "UNVERIFIED"
        )

    def test_supersession_preserves_history_and_negative_results(self) -> None:
        result = MOD.build_experiment(load_packet())
        supersession = result["supersession_map"]
        self.assertFalse(supersession["historical_state_deleted"])
        self.assertTrue(supersession["negative_results_preserved"])
        self.assertTrue(supersession["failure_evidence_preserved"])

    def test_collision_integrity_fails_closed(self) -> None:
        result = MOD.build_experiment(load_packet())
        collision = result["collision_integrity"]
        self.assertTrue(collision["duplicate_effect_suppression"])
        self.assertTrue(collision["collision_reconciliation_required"])
        self.assertTrue(collision["duplicate_readbacks_fail_closed"])
        self.assertFalse(collision["unchanged_retry_permitted"])

    def test_result_is_deterministic_and_verifies(self) -> None:
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
        self.assertIn(
            "RESULT_RECEIPT_MISMATCH",
            {item["code"] for item in check["violations"]},
        )

    def test_overclaim_is_rejected(self) -> None:
        result = MOD.build_experiment(load_packet())
        result["release_claims"].append(
            "Provider runtime verified and recurring autonomy proven"
        )
        without_receipt = copy.deepcopy(result)
        without_receipt.pop("receipt_sha256", None)
        result["receipt_sha256"] = MOD.canonical_sha256(without_receipt)
        check = MOD.verify_result(result)
        self.assertFalse(check["passed"])
        self.assertIn(
            "PROHIBITED_RELEASE_OVERCLAIM",
            {item["code"] for item in check["violations"]},
        )

    def test_lineage_hash_tamper_is_detected(self) -> None:
        result = MOD.build_experiment(load_packet())
        result["lineage_graph"]["parents_preserved"] = False
        without_receipt = copy.deepcopy(result)
        without_receipt.pop("receipt_sha256", None)
        result["receipt_sha256"] = MOD.canonical_sha256(without_receipt)
        check = MOD.verify_result(result)
        self.assertFalse(check["passed"])
        self.assertIn(
            "LINEAGE_GRAPH_HASH_MISMATCH",
            {item["code"] for item in check["violations"]},
        )

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
                (
                    "REAL_REGISTERED_SOURCE_FEDERATION_EVOLUTION_"
                    "PASSED_READ_ONLY"
                ),
            )


if __name__ == "__main__":
    unittest.main()
