from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from evidenceops.fevx_adapter_v1.adapter import EvidenceOpsFEVXAdapter
from evidenceops.fevx_adapter_v1.base_runner import FixtureBaseRunner
from evidenceops.fevx_adapter_v1.contracts import (
    BoundaryViolation,
    PacketValidationError,
    validate_packet,
)
from evidenceops.fevx_adapter_v1.core import digest, semantic_digest
from evidenceops.fevx_adapter_v1.store import DerivedStore


class EvidenceOpsFEVXAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parents[3]
        cls.fixture_path = (
            cls.repo_root
            / "evidenceops/fevx_adapter_v1/fixtures/synthetic_case_packet.json"
        )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "derived.db"
        self.store = DerivedStore(self.database)
        self.adapter = EvidenceOpsFEVXAdapter(
            store=self.store,
            repo_root=self.repo_root,
            base_runner=FixtureBaseRunner(),
        )
        self.packet = json.loads(self.fixture_path.read_text(encoding="utf-8"))

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_01_valid_packet(self):
        self.assertEqual(
            validate_packet(self.packet)["packet_id"], self.packet["packet_id"]
        )

    def test_02_combined_twenty_modules(self):
        result = self.adapter.analyse(self.packet)
        self.assertEqual(result["derived_payload"]["combined_module_count"], 20)

    def test_03_source_packet_immutable(self):
        before = copy.deepcopy(self.packet)
        self.adapter.analyse(self.packet)
        self.assertEqual(self.packet, before)
        self.assertEqual(digest(self.packet), digest(before))

    def test_04_source_and_fact_manifests_are_hash_only(self):
        result = self.adapter.analyse(self.packet)["derived_payload"]
        self.assertNotIn("statement", result["source_manifest"][0])
        self.assertNotIn("statement", result["fact_manifest"][0])
        self.assertFalse(result["authority"]["source_write"])
        self.assertFalse(result["authority"]["verified_fact_write"])

    def test_05_top_level_case_wall_mismatch_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["sources"][0]["case_wall_id"] = "OTHER"
        with self.assertRaises(BoundaryViolation):
            self.adapter.analyse(packet)

    def test_06_nested_case_wall_mismatch_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["strategies"][0]["target_case_wall_id"] = "OTHER"
        with self.assertRaises(BoundaryViolation):
            self.adapter.analyse(packet)

    def test_07_matter_mismatch_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["claims"][0]["matter_id"] = "OTHER-MATTER"
        with self.assertRaises(BoundaryViolation):
            self.adapter.analyse(packet)

    def test_08_external_effect_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["authority"]["external_effect"] = True
        with self.assertRaises(BoundaryViolation):
            self.adapter.analyse(packet)

    def test_09_held_action_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["authority"]["requested_actions"].append("LEGAL_FILE")
        with self.assertRaises(BoundaryViolation):
            self.adapter.analyse(packet)

    def test_10_output_is_held_and_advisory(self):
        result = self.adapter.analyse(self.packet)["derived_payload"]
        self.assertEqual(result["release_state"], "HELD_FOR_EVIDENCEOPS_REVIEW")
        self.assertEqual(result["fact_status"], "DERIVED_NOT_FACT")
        self.assertFalse(result["level_6_eligible"])

    def test_11_store_has_no_source_or_fact_tables(self):
        self.adapter.analyse(self.packet)
        verification = self.store.verify_schema_boundary()
        self.assertEqual(verification["status"], "PASSED")
        self.assertEqual(
            set(verification["tables"]),
            {"recommendations", "proofs", "ledger", "checkpoints"},
        )

    def test_12_idempotent_repeat(self):
        first = self.adapter.analyse(self.packet)
        count = self.store.recommendation_count()
        events = self.store.ledger_count()
        second = self.adapter.analyse(self.packet)
        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(self.store.recommendation_count(), count)
        self.assertEqual(self.store.ledger_count(), events)

    def test_13_ledger_verifies(self):
        self.adapter.analyse(self.packet)
        self.assertEqual(self.store.verify_ledger()["status"], "PASSED")

    def test_14_tamper_detected(self):
        self.adapter.analyse(self.packet)
        self.store.connection.execute(
            "UPDATE ledger SET payload_json='{}' WHERE sequence=1"
        )
        self.store.connection.commit()
        self.assertEqual(self.store.verify_ledger()["status"], "FAILED")

    def test_15_rollback_and_reapply(self):
        before = self.store.dump_sql()
        self.adapter.analyse(self.packet)
        after = self.store.dump_sql()
        rollback_path = Path(self.temp.name) / "rollback.db"
        rollback = DerivedStore.restore_sql(rollback_path, before)
        self.assertEqual(digest(rollback.dump_sql()), digest(before))
        rollback.close()
        reapplied = DerivedStore.restore_sql(rollback_path, after)
        self.assertEqual(digest(reapplied.dump_sql()), digest(after))
        self.assertEqual(reapplied.verify_all()["status"], "PASSED")
        reapplied.close()

    def test_16_semantic_hash_stable(self):
        first = self.adapter.analyse(self.packet)
        self.assertEqual(
            first["semantic_hash"],
            semantic_digest(first["derived_payload"]),
        )

    def test_17_unknown_source_reference_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["verified_facts"][0]["source_refs"] = ["UNKNOWN"]
        with self.assertRaises(PacketValidationError):
            self.adapter.analyse(packet)

    def test_18_unverified_fact_in_verified_register_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["verified_facts"][0]["verification_state"] = "UNVERIFIED"
        with self.assertRaises(PacketValidationError):
            self.adapter.analyse(packet)

    def test_19_no_external_execution_endpoint(self):
        source = (
            self.repo_root / "evidenceops/fevx_adapter_v1/adapter.py"
        ).read_text(encoding="utf-8")
        for token in ("FastAPI(", "@app.post", "requests.post", "send_email("):
            self.assertNotIn(token, source)

    def test_20_full_integrity_bundle(self):
        self.adapter.analyse(self.packet)
        self.assertEqual(self.store.verify_all()["status"], "PASSED")


if __name__ == "__main__":
    unittest.main()
