from __future__ import annotations

import copy
import unittest

from benchmarking.cfbe_omega.capability_registry_v1 import (
    CapabilityRegistry,
    normalize_kdv_projection,
    normalize_living_state_events,
)
from benchmarking.cfbe_omega.closure_matrix_v1 import load_matrix


NOW = "2026-08-30T13:00:00Z"


def projection_rows():
    matrix = load_matrix()
    return copy.deepcopy(matrix["rows"])


class CapabilityRegistryTests(unittest.TestCase):
    def test_kdv_projection_normalizes_required_scheduler_fields(self):
        records = normalize_kdv_projection(
            projection_rows(), source_ref="KDV:CFBE-CLOSURE-MATRIX", observed_at=NOW
        )
        c03 = next(record for record in records if record.capability_id == "C03")
        self.assertEqual(c03.source_kind, "KDV_PROJECTION")
        self.assertEqual(c03.authority_ceiling, "A1")
        self.assertEqual(c03.cost_units, 0)
        self.assertEqual(c03.latency_ms, 0)
        self.assertTrue(c03.fingerprint)
        self.assertTrue(c03.fresh_at(NOW))

    def test_living_state_export_is_composed_without_mutating_world_model(self):
        events = [{
            "event_type": "NODE_OBSERVED",
            "payload": {"node": {
                "node_id": "C03",
                "kind": "CAPABILITY",
                "name": "Universal Capability Graph and Scheduler Registry",
                "state": "INTEGRATE",
                "attributes": {"rail": "A", "dependencies": ["C02"], "next_action": "read-only selector"},
                "provenance": {
                    "proof_maturity": "SOURCE_PRESENT",
                    "proof_ref": "SOURCE:C03",
                    "source_ref": "LIVING_STATE",
                    "observed_at": NOW,
                    "ttl_seconds": 3600,
                    "authority_ceiling": "A1",
                },
            }},
        }]
        records = normalize_living_state_events(events)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].capability_id, "C03")
        self.assertEqual(records[0].source_kind, "LIVING_STATE")

    def test_query_enforces_wip_and_keeps_effect_authority_false(self):
        matrix = load_matrix()
        registry = CapabilityRegistry(normalize_kdv_projection(
            matrix["rows"], source_ref="KDV:CFBE-CLOSURE-MATRIX", observed_at=NOW
        ))
        receipt = registry.query_closure_wave(matrix, now=NOW)
        self.assertTrue(all(value <= 2 for value in receipt.selected_per_rail.values()))
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.financial_effect_authorized)
        self.assertTrue(receipt.receipt_sha256)
        self.assertIn("C03", {record.capability_id for record in receipt.selected})

    def test_stale_observation_fails_closed(self):
        matrix = load_matrix()
        records = normalize_kdv_projection(
            matrix["rows"],
            source_ref="KDV:STALE",
            observed_at="2026-08-28T00:00:00Z",
            ttl_seconds=60,
        )
        receipt = CapabilityRegistry(records).query_closure_wave(matrix, now=NOW)
        self.assertFalse(receipt.selected)
        self.assertIn("STALE_CAPABILITY_OBSERVATION", receipt.held["C03"])

    def test_split_brain_observation_fails_closed(self):
        matrix = load_matrix()
        rows = projection_rows()
        c03 = next(row for row in rows if row["id"] == "C03")
        conflicting = dict(c03, maturity="PROVIDER_VERIFIED")
        records = (
            *normalize_kdv_projection(rows, source_ref="KDV:A", observed_at=NOW),
            *normalize_kdv_projection([conflicting], source_ref="KDV:B", observed_at=NOW),
        )
        receipt = CapabilityRegistry(records).query_closure_wave(matrix, now=NOW)
        self.assertIn("SPLIT_BRAIN_CAPABILITY_OBSERVATION", receipt.held["C03"])

    def test_missing_dependency_observation_blocks_candidate(self):
        matrix = load_matrix()
        c03 = next(row for row in matrix["rows"] if row["id"] == "C03")
        registry = CapabilityRegistry(normalize_kdv_projection(
            [c03], source_ref="KDV:C03-ONLY", observed_at=NOW
        ))
        receipt = registry.query_closure_wave(matrix, now=NOW)
        self.assertTrue(any(item.startswith("DEPENDENCY_UNREADY:C02") for item in receipt.held["C03"]))


if __name__ == "__main__":
    unittest.main()
