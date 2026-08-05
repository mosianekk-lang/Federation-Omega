from __future__ import annotations

from copy import deepcopy
import unittest

from federation_consolidation.awareness_readback_reconciler import (
    ReconciliationError,
    canonical_sha256,
    reconcile_foundry,
    verify_foundry_receipt,
)

MAIN = "2a7fbfcd1998489c8103219c80b99808708f8f8c"
OLD = "beae4406889351ca83f03685db3204c713f920d9"


def foundry_receipt():
    body = {
        "schema": "FEDOMEGA-AWARENESS-OPPORTUNITY-FOUNDRY-1",
        "status": "VERIFIED_LOCAL_BUILD_SET",
        "observed_main": OLD,
        "mission": "restore federation awareness",
        "binding": {"status": "VERIFIED"},
        "drifts": [],
        "routes": [],
        "credential_preflight": [],
        "gmail_signal_map": [],
        "opportunities": [
            {
                "opportunity_id": "OPP-CANVA-READ",
                "opportunity_class": "PROVIDER_PROBE",
                "source_alias": "CANVA_DESIGN_SURFACE",
                "title": "Resolve Canva",
                "owning_engine": "FORMATION_INNOVATION_ENGINE",
                "desired_capability": "Read probe",
                "current_state": "CONNECTOR_AVAILABLE_REVALIDATE_ON_USE",
                "buildable_now": False,
                "external_effect": True,
                "priority": 70,
                "reason": "needs proof",
                "build_trigger": {
                    "build_id": "BUILD-AO-FED-CANVA000001",
                    "classification": "BLOCKED_DEPENDENCY_ACTIVE",
                    "gap_statement": "Canva needs proof",
                    "desired_capability": "Read probe",
                    "owning_engine": "FORMATION_INNOVATION_ENGINE",
                    "lifecycle_state": "BLOCKED_DEPENDENCY",
                    "dependencies": ["Canva"],
                    "interim_workaround": "none",
                    "next_executable_action": "probe",
                    "acceptance_criteria": ["readback"],
                    "recheck_triggers": ["connector"],
                    "authority_ceiling": "A1_INTERNAL",
                    "external_effect": False,
                    "source_trigger": "test",
                },
            },
            {
                "opportunity_id": "OPP-CLOUDOPS",
                "opportunity_class": "INTERNAL_HARDENING",
                "source_alias": "SOVEREIGN_FEDERATION_CLOUDOPS",
                "title": "Harden CloudOps",
                "owning_engine": "FEDERATION_OMEGA_CORE",
                "desired_capability": "runtime verifier",
                "current_state": "FULL_CONTENT_READ_ACTIVE_PARTIAL",
                "buildable_now": True,
                "external_effect": False,
                "priority": 80,
                "reason": "partial",
                "build_trigger": {
                    "build_id": "BUILD-AO-FED-CLOUDOPS001",
                    "classification": "WORKAROUND_ACTIVE_BUILD_OPEN",
                    "gap_statement": "CloudOps partial",
                    "desired_capability": "runtime verifier",
                    "owning_engine": "FEDERATION_OMEGA_CORE",
                    "lifecycle_state": "WORKAROUND_ACTIVE",
                    "dependencies": [],
                    "interim_workaround": "read bounded tabs",
                    "next_executable_action": "build",
                    "acceptance_criteria": ["readback"],
                    "recheck_triggers": ["runtime"],
                    "authority_ceiling": "A1_INTERNAL",
                    "external_effect": False,
                    "source_trigger": "test",
                },
            },
        ],
        "internal_build_ids": ["BUILD-AO-FED-CLOUDOPS001"],
        "provider_gated_build_ids": ["BUILD-AO-FED-CANVA000001"],
        "node_packet": {},
        "credential_value_recorded": False,
        "provider_mutation_performed": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return body


def readback(status="READ_PROBE_VERIFIED"):
    return {
        "schema": "FEDOMEGA-PROVIDER-READBACK-1",
        "source_alias": "CANVA_DESIGN_SURFACE",
        "provider": "Canva",
        "status": status,
        "evidence": "Owned design search returned current design metadata",
        "credential_value_recorded": False,
        "provider_mutation_performed": False,
    }


def proof():
    return {
        "foundry_source_present": True,
        "airlock_passed": True,
        "leak_guard_passed": True,
        "phoenix_freeze_verified": True,
    }


class ReadbackReconcilerTests(unittest.TestCase):
    def execute(self, **overrides):
        values = dict(
            foundry_receipt=foundry_receipt(),
            provider_readbacks=[readback()],
            observed_main=MAIN,
            private_main_pointers={"awareness": MAIN, "opportunity": MAIN},
            source_merge_proof=proof(),
        )
        values.update(overrides)
        return reconcile_foundry(**values)

    def test_foundry_receipt_hash_verifies(self):
        verify_foundry_receipt(foundry_receipt())

    def test_foundry_tamper_fails(self):
        value = foundry_receipt()
        value["mission"] = "tampered"
        with self.assertRaisesRegex(ReconciliationError, "embedded SHA"):
            verify_foundry_receipt(value)

    def test_read_probe_closes_probe_and_creates_effectful_successor(self):
        result = self.execute()
        self.assertEqual("VERIFIED_RECONCILED", result["status"])
        self.assertEqual(1, result["read_probe_satisfied_count"])
        self.assertEqual(1, len(result["successor_effectful_build_ids"]))
        classes = {item["opportunity_class"] for item in result["active_opportunities"]}
        self.assertIn("PROVIDER_EFFECTFUL_CAPABILITY", classes)
        self.assertNotIn("PROVIDER_PROBE", classes)

    def test_effectful_verified_creates_no_successor(self):
        result = self.execute(provider_readbacks=[readback("EFFECTFUL_CAPABILITY_VERIFIED")])
        self.assertEqual([], result["successor_effectful_build_ids"])
        self.assertEqual(1, result["read_probe_satisfied_count"])

    def test_stale_private_pointer_creates_drift_build(self):
        result = self.execute(private_main_pointers={"awareness": OLD})
        self.assertEqual("DRIFT_REPAIR_REQUIRED", result["status"])
        self.assertEqual(1, len(result["private_pointer_drifts"]))
        self.assertEqual(1, len(result["drift_build_ids"]))

    def test_internal_hardening_remains_runtime_proof_open(self):
        result = self.execute()
        cloud = next(item for item in result["active_opportunities"] if item["source_alias"] == "SOVEREIGN_FEDERATION_CLOUDOPS")
        self.assertEqual("SOURCE_IMPLEMENTED_RUNTIME_PROOF_OPEN", cloud["current_state"])

    def test_duplicate_readback_fails(self):
        with self.assertRaisesRegex(ReconciliationError, "duplicate"):
            self.execute(provider_readbacks=[readback(), readback()])

    def test_secret_shaped_readback_fails(self):
        value = readback()
        value["evidence"] = "github_pat_" + "A" * 30
        with self.assertRaises(ReconciliationError):
            self.execute(provider_readbacks=[value])

    def test_missing_merge_proof_fails(self):
        value = proof()
        value["airlock_passed"] = False
        with self.assertRaisesRegex(ReconciliationError, "Airlock"):
            self.execute(source_merge_proof=value)

    def test_deterministic_replay(self):
        self.assertEqual(self.execute()["receipt_sha256"], self.execute()["receipt_sha256"])


if __name__ == "__main__":
    unittest.main()
