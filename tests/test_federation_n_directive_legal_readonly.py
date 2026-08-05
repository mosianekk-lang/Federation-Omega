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
    ROOT / "governance" / "federation_n_directive_legal_readonly.py"
)
SPEC = importlib.util.spec_from_file_location(
    "federation_n_directive_legal_readonly",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)

PACKET_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "federation_n_legal_authority_control_packet.json"
)


def load_packet() -> dict:
    return json.loads(PACKET_PATH.read_text(encoding="utf-8"))


def refresh_source_fingerprint(source: dict) -> None:
    payload = {
        "source_id": source["source_id"],
        "source_type": source["source_type"],
        "title": source["title"],
        "assertions": source["assertions"],
    }
    source["source_fingerprint_sha256"] = MOD.canonical_sha256(payload)


class LegalRealReadonlyTests(unittest.TestCase):
    def test_packet_validates(self) -> None:
        validation = MOD.validate_packet(load_packet())
        self.assertTrue(validation["passed"], validation)
        self.assertEqual(validation["evidence"]["source_count"], 4)
        self.assertEqual(validation["evidence"]["legal_proof_gap_count"], 8)

    def test_source_omission_fails_closed(self) -> None:
        packet = load_packet()
        packet["sources"].pop()
        validation = MOD.validate_packet(packet)
        self.assertFalse(validation["passed"])
        self.assertIn(
            "SOURCE_COUNT_MISMATCH",
            {item["code"] for item in validation["violations"]},
        )

    def test_source_fingerprint_tamper_fails_closed(self) -> None:
        packet = load_packet()
        packet["sources"][0]["assertions"][0]["statement"] += " altered"
        validation = MOD.validate_packet(packet)
        self.assertFalse(validation["passed"])
        self.assertIn(
            "SOURCE_FINGERPRINT_MISMATCH",
            {item["code"] for item in validation["violations"]},
        )

    def test_duplicate_claim_id_fails_closed(self) -> None:
        packet = load_packet()
        packet["sources"][1]["assertions"][0]["claim_id"] = "CLM-P13-001"
        refresh_source_fingerprint(packet["sources"][1])
        validation = MOD.validate_packet(packet)
        self.assertFalse(validation["passed"])
        self.assertIn(
            "DUPLICATE_CLAIM_ID",
            {item["code"] for item in validation["violations"]},
        )

    def test_legal_or_external_authority_tamper_fails_closed(self) -> None:
        packet = load_packet()
        packet["legal_finding_permitted"] = True
        validation = MOD.validate_packet(packet)
        self.assertFalse(validation["passed"])
        self.assertIn(
            "PACKET_FIELD_MISMATCH",
            {item["code"] for item in validation["violations"]},
        )

    def test_ccma_hash_disagreement_fails_closed(self) -> None:
        packet = load_packet()
        manifest = packet["sources"][2]
        manifest["assertions"][0]["value"] = "0" * 64
        refresh_source_fingerprint(manifest)
        self.assertTrue(MOD.validate_packet(packet)["passed"])
        with self.assertRaisesRegex(
            MOD.LegalReadonlyError, "CCMA_RULES_HASH_MISMATCH"
        ):
            MOD.build_experiment(packet)

    def test_incomplete_page_qa_fails_closed(self) -> None:
        packet = load_packet()
        ledger = packet["sources"][3]
        for assertion in ledger["assertions"]:
            if assertion["field"] == "ccma_rules_visual_scan_count":
                assertion["value"] = 41
        refresh_source_fingerprint(ledger)
        self.assertTrue(MOD.validate_packet(packet)["passed"])
        with self.assertRaisesRegex(
            MOD.LegalReadonlyError, "CCMA_RULES_PAGE_QA_INCOMPLETE"
        ):
            MOD.build_experiment(packet)

    def test_authority_passport_preserves_currentness_boundaries(self) -> None:
        result = MOD.build_experiment(load_packet())
        passport = result["legal_authority_passport"]
        self.assertEqual(
            passport["labour_relations_act"]["currentness"],
            "AMENDMENT_CHECK_REQUIRED",
        )
        self.assertEqual(
            passport["protected_disclosures_act"]["currentness"],
            "CURRENT_OFFICIAL_SOURCE_WITH_AMENDMENT_NOTED",
        )
        self.assertEqual(
            passport["ccma_rules_carrier"]["currentness"],
            "UNVERIFIED_REQUIRES_CURRENT_OFFICIAL_RULES_CHECK",
        )

    def test_historical_schedule8_is_preserved_but_not_current_controller(self) -> None:
        result = MOD.build_experiment(load_packet())
        historical = result["legal_authority_passport"][
            "historical_schedule_8"
        ]
        self.assertEqual(
            historical["state"],
            "HISTORICAL_SUPERSEDED_NATIONALLY_IN_2025",
        )
        self.assertEqual(
            historical["activation"],
            "ARCHIVED_QUERYABLE_NOT_CURRENT_CONTROLLER",
        )

    def test_secondary_archive_failure_does_not_negate_primary_identity(self) -> None:
        result = MOD.build_experiment(load_packet())
        receipt = result["legal_authority_passport"][
            "official_provider_receipt"
        ]
        self.assertTrue(receipt["raw_byte_gate"])
        self.assertFalse(receipt["secondary_archive_gate"])
        self.assertEqual(len(receipt["secondary_provider_blocked_ids"]), 2)

    def test_four_cross_source_tensions_are_resolved_by_scope(self) -> None:
        result = MOD.build_experiment(load_packet())
        tensions = result["cross_source_tensions"]
        self.assertEqual(len(tensions), 4)
        self.assertEqual(
            {item["result"] for item in tensions},
            {
                "RESOLVED_BY_IDENTITY_CURRENTNESS_SEPARATION",
                "RESOLVED_BY_QA_CURRENTNESS_SEPARATION",
                "RESOLVED_BY_HISTORICAL_SUPERSESSION",
                "RESOLVED_BY_PRIMARY_SECONDARY_SEPARATION",
            },
        )

    def test_all_legal_proof_gaps_remain_unverified(self) -> None:
        packet = load_packet()
        result = MOD.build_experiment(packet)
        self.assertEqual(
            len(result["gap_schedule"]),
            len(packet["legal_proof_gaps"]),
        )
        self.assertTrue(
            all(
                item["state"]
                == "UNVERIFIED_REQUIRES_SEPARATE_LEGAL_PROOF"
                for item in result["gap_schedule"]
            )
        )

    def test_formation_tournament_has_three_routes(self) -> None:
        result = MOD.build_experiment(load_packet())
        formation = result["formation_engine_result"]
        self.assertEqual(
            set(formation["route_families"]),
            MOD.REQUIRED_ROUTE_FAMILIES,
        )
        self.assertEqual(
            formation["selected_route_family"], "COMPOSE_OR_EXTEND"
        )
        self.assertEqual(len(formation["route_alternatives"]), 3)

    def test_control_completeness_delta_is_plus_five(self) -> None:
        result = MOD.build_experiment(load_packet())
        metrics = result["metrics"]
        self.assertEqual(
            metrics["baseline_control_coverage"]["covered"], 4
        )
        self.assertEqual(
            metrics["treatment_control_coverage"]["covered"], 9
        )
        self.assertEqual(metrics["control_completeness_delta"], 5)
        self.assertEqual(metrics["ccma_hash_agreement"], "2_OF_2_MATCH")
        self.assertEqual(metrics["ccma_page_qa_coverage"], "42_OF_42")

    def test_no_case_facts_findings_filings_or_effects_are_created(self) -> None:
        result = MOD.build_experiment(load_packet())
        metrics = result["metrics"]
        self.assertEqual(metrics["case_facts_imported"], 0)
        self.assertEqual(metrics["legal_findings_issued"], 0)
        self.assertEqual(metrics["filings_or_communications"], 0)
        self.assertEqual(metrics["external_effects"], 0)
        self.assertEqual(
            result["proof_and_maturity"]["legal_merits_finality"],
            "NOT_ASSESSED",
        )

    def test_result_is_deterministic(self) -> None:
        packet = load_packet()
        first = MOD.build_experiment(packet)
        second = MOD.build_experiment(packet)
        self.assertEqual(first, second)
        self.assertTrue(MOD.verify_result(first)["passed"])

    def test_receipt_tamper_is_detected(self) -> None:
        result = MOD.build_experiment(load_packet())
        result["metrics"]["legal_findings_issued"] = 1
        verification = MOD.verify_result(result)
        self.assertFalse(verification["passed"])
        self.assertIn(
            "RESULT_RECEIPT_MISMATCH",
            {item["code"] for item in verification["violations"]},
        )

    def test_legal_overclaim_is_rejected(self) -> None:
        result = MOD.build_experiment(load_packet())
        result["release_claims"].append(
            "Protected disclosure established and jurisdiction confirmed"
        )
        without_receipt = copy.deepcopy(result)
        without_receipt.pop("receipt_sha256", None)
        result["receipt_sha256"] = MOD.canonical_sha256(without_receipt)
        verification = MOD.verify_result(result)
        self.assertFalse(verification["passed"])
        self.assertIn(
            "PROHIBITED_LEGAL_OVERCLAIM",
            {item["code"] for item in verification["violations"]},
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
                "REAL_REGISTERED_SOURCE_LEGAL_CONTROL_STATE_PASSED_READ_ONLY",
            )


if __name__ == "__main__":
    unittest.main()
