from __future__ import annotations

from datetime import datetime, timezone
import unittest

from federation_consolidation.cloudops_runtime_freshness_verifier import (
    FreshnessError,
    canonical_sha256,
    verify_cloudops_runtime_freshness,
)

NOW = datetime(2026, 8, 5, 2, 1, tzinfo=timezone.utc)


def tables(
    health_time: str = "2026-08-05T01:30:00Z",
    processor_time: str = "2026-08-05T01:20:00Z",
):
    return {
        "Health": [
            ["timestamp", "checkType", "status", "detailsJson"],
            [
                health_time,
                "RUNTIME_HEALTH",
                "DONE",
                '{"status":"DONE","httpStatus":200,"body":{"ok":true,"status":"live","service":"architron9"}}',
            ],
        ],
        "Runtime_Control": [
            [
                "ID", "Area", "Observed_State", "Corrected_State",
                "Proof_Source", "Risk", "Next", "Status",
            ],
            [
                "RC1", "route", "ok", "Verified endpoint contract",
                "Direct curl 2026-08-05T01:10:00Z", "Low", "", "VERIFIED",
            ],
        ],
        "Automation_Status": [
            [
                "ID", "Automation", "Designed", "Triggered", "Processed",
                "Output", "Readback", "State",
            ],
            ["AS1", "processor", "YES", "YES", "1", "DONE", "YES", "CURRENT"],
        ],
        "Cloud_Authority_Probe_Log": [
            [
                "Probe_ID", "Timestamp", "Target", "Action", "Expected_Result",
                "Actual_Result", "Status", "Blocker", "Next_Route",
                "Readback_Source", "Owner_Auth", "Notes",
            ],
            [
                "P1", "2026-08-05T01:00:00Z", "Cloud", "READ", "ok", "ok",
                "VERIFIED", "", "", "provider", "", "",
            ],
        ],
        "Processor_Health_Probe": [
            [
                "Probe_ID", "Timestamp", "Processor", "Expected_Behaviour",
                "Observed_State", "Classification", "Current_Status", "Evidence",
                "Next_Action", "Fallback", "Owner", "Notes",
            ],
            [
                "PH1", processor_time, "queue", "process", "processed",
                "CURRENT_PROCESSING_VERIFIED", "VERIFIED", "readback", "", "", "", "",
            ],
        ],
        "OS_Proof_Ledger": [
            [
                "Proof_ID", "OS_Layer", "Claim", "Proof_Source", "Proof_Status",
                "Gap", "Next_Route", "Fallback", "Closure_Condition", "Risk", "Value",
            ],
            [
                "O1", "Direct", "readback", "source", "CONTROL_PROVEN_INTERNAL",
                "", "", "", "", "LOW", "",
            ],
        ],
    }


class CloudOpsFreshnessTests(unittest.TestCase):
    def test_fresh_complete_packet_is_current(self):
        result = verify_cloudops_runtime_freshness(tables=tables(), observed_at=NOW)
        self.assertEqual("CURRENT_RUNTIME_VERIFIED", result["status"])
        self.assertTrue(result["current_runtime_verified"])

    def test_alternate_done_health_schema_is_semantically_valid(self):
        value = tables()
        value["Health"][1][3] = (
            '{"status":"DONE","httpStatus":200,"body":{"ok":true,'
            '"status":"DONE","healthOk":true,"runtime":"architron-unified-core"}}'
        )
        result = verify_cloudops_runtime_freshness(tables=value, observed_at=NOW)
        self.assertEqual("CURRENT_RUNTIME_VERIFIED", result["status"])

    def test_old_health_is_not_current(self):
        result = verify_cloudops_runtime_freshness(
            tables=tables(health_time="2026-06-06T01:00:00Z"), observed_at=NOW
        )
        self.assertEqual(
            "STALE_RUNTIME_PROOF_CURRENT_CONSTRAINTS_ONLY", result["status"]
        )
        self.assertFalse(result["current_runtime_verified"])

    def test_newer_route_constraint_blocks_old_success(self):
        value = tables()
        value["Runtime_Control"][1][3] = (
            "Resolve deployed revision endpoint contract; HTTP 404"
        )
        value["Runtime_Control"][1][7] = "CONSTRAINT_CLASSIFIED_ROUTE_MISMATCH"
        result = verify_cloudops_runtime_freshness(tables=value, observed_at=NOW)
        self.assertEqual("RUNTIME_NOT_CURRENTLY_VERIFIED", result["status"])
        route = next(
            item for item in result["findings"]
            if item["category"] == "ROUTE_CONSTRAINT"
        )
        self.assertEqual("CURRENT_CONSTRAINT_VERIFIED", route["state"])

    def test_stale_processor_blocks_current(self):
        result = verify_cloudops_runtime_freshness(
            tables=tables(processor_time="2026-06-30T00:00:00Z"),
            observed_at=NOW,
        )
        self.assertFalse(result["current_runtime_verified"])
        processor = next(
            item for item in result["findings"]
            if item["category"] == "QUEUE_PROCESSOR"
        )
        self.assertEqual("STALE_PROCESSOR_EVIDENCE", processor["state"])

    def test_malformed_health_json_fails_semantics(self):
        value = tables()
        value["Health"][1][3] = "{bad"
        result = verify_cloudops_runtime_freshness(tables=value, observed_at=NOW)
        self.assertEqual("INVALID_OR_MISSING_EVIDENCE", result["status"])

    def test_future_timestamp_fails_closed(self):
        with self.assertRaisesRegex(FreshnessError, "future"):
            verify_cloudops_runtime_freshness(
                tables=tables(health_time="2026-08-06T01:00:00Z"),
                observed_at=NOW,
            )

    def test_missing_table_fails_closed(self):
        value = tables()
        del value["Health"]
        with self.assertRaisesRegex(FreshnessError, "missing required"):
            verify_cloudops_runtime_freshness(tables=value, observed_at=NOW)

    def test_undated_tables_never_prove_current(self):
        result = verify_cloudops_runtime_freshness(tables=tables(), observed_at=NOW)
        automation = next(
            item for item in result["findings"]
            if item["category"] == "AUTOMATION_CONTROL"
        )
        self.assertEqual("UNDATED_SOURCE_ONLY", automation["state"])
        self.assertFalse(automation["current"])

    def test_secret_shaped_material_rejected(self):
        value = tables()
        value["OS_Proof_Ledger"][1][3] = ("github" + "_pat_") + "A" * 30
        with self.assertRaises(FreshnessError):
            verify_cloudops_runtime_freshness(tables=value, observed_at=NOW)

    def test_deterministic_receipt(self):
        first = verify_cloudops_runtime_freshness(tables=tables(), observed_at=NOW)
        second = verify_cloudops_runtime_freshness(tables=tables(), observed_at=NOW)
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])
        body = dict(first)
        claimed = body.pop("receipt_sha256")
        self.assertEqual(claimed, canonical_sha256(body))

    def test_never_claims_mutation_or_credentials(self):
        result = verify_cloudops_runtime_freshness(tables=tables(), observed_at=NOW)
        self.assertFalse(result["provider_mutation_performed"])
        self.assertFalse(result["credential_value_recorded"])
        self.assertFalse(result["external_effect_performed"])


if __name__ == "__main__":
    unittest.main()
