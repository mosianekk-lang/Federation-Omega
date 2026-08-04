from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from alpha_omega_commercial.effective_state import (
    EffectiveStateError,
    build_effective_state,
    digest,
    load_json,
)
from alpha_omega_commercial.prove_effective_state import ROOT, SOURCE_PATHS, build_proof


class EffectiveProgrammeStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.programme = load_json(SOURCE_PATHS["programme"])
        cls.governed_release = load_json(SOURCE_PATHS["governed_release"])
        cls.governed_checkpoint = load_json(SOURCE_PATHS["governed_checkpoint"])
        cls.institution_checkpoint = load_json(SOURCE_PATHS["institution_checkpoint"])
        cls.institution_reconciliation = load_json(
            SOURCE_PATHS["institution_reconciliation"]
        )
        cls.drive_observation = load_json(SOURCE_PATHS["drive_observation"])
        cls.committed_state = load_json(SOURCE_PATHS["effective_state"])

    def reconcile(
        self,
        *,
        programme=None,
        governed_release=None,
        governed_checkpoint=None,
        institution_checkpoint=None,
        institution_reconciliation=None,
        drive_observation=None,
    ):
        return build_effective_state(
            copy.deepcopy(programme or self.programme),
            copy.deepcopy(governed_release or self.governed_release),
            copy.deepcopy(governed_checkpoint or self.governed_checkpoint),
            copy.deepcopy(institution_checkpoint or self.institution_checkpoint),
            copy.deepcopy(
                institution_reconciliation or self.institution_reconciliation
            ),
            copy.deepcopy(drive_observation or self.drive_observation),
        )

    def test_current_state_reconciles(self) -> None:
        result = self.reconcile()
        checks = result.pop("checks")
        self.assertTrue(all(checks.values()))
        self.assertEqual(result, self.committed_state)
        self.assertEqual(
            result["status"],
            "EFFECTIVE_PROGRAMME_STATE_VERIFIED_C15_INSTITUTION_RECONCILED_EXTERNAL_GATES_OPEN",
        )
        self.assertEqual(result["commercial_truth"]["verified_live_revenue_events"], 0)
        self.assertFalse(result["commercial_truth"]["full_commercial_maturity"])

    def test_committed_state_hash_is_valid(self) -> None:
        value = copy.deepcopy(self.committed_state)
        expected = value.pop("state_sha256")
        self.assertEqual(expected, digest(value))

    def test_proof_receipt_is_persisted_and_hash_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "effective-state-receipt.json"
            receipt = build_proof(output)
            readback = json.loads(output.read_text(encoding="utf-8"))
            expected = readback.pop("receipt_sha256")
            self.assertEqual(expected, digest(readback))
            self.assertEqual(receipt["receipt_sha256"], expected)

    def test_dependency_drift_is_rejected(self) -> None:
        programme = copy.deepcopy(self.programme)
        programme["stages"][3]["depends_on"] = ["C15"]
        with self.assertRaisesRegex(EffectiveStateError, "dependency order"):
            self.reconcile(programme=programme)

    def test_governed_release_tampering_is_rejected(self) -> None:
        release = copy.deepcopy(self.governed_release)
        release["implementation"]["canonical_class"] = "LegacyCommercialControlPlane"
        with self.assertRaisesRegex(EffectiveStateError, "release integrity"):
            self.reconcile(governed_release=release)

    def test_external_gate_promotion_is_rejected(self) -> None:
        release = copy.deepcopy(self.governed_release)
        release["external_gates"]["customer_demand"] = True
        checkpoint = self._rehash_release(release)
        with self.assertRaisesRegex(EffectiveStateError, "external maturity gate"):
            self.reconcile(
                governed_release=release,
                governed_checkpoint=checkpoint,
            )

    def test_unverified_revenue_is_rejected(self) -> None:
        release = copy.deepcopy(self.governed_release)
        release["truth_boundary"]["verified_live_revenue_events"] = 1
        checkpoint = self._rehash_release(release)
        with self.assertRaisesRegex(EffectiveStateError, "live revenue"):
            self.reconcile(
                governed_release=release,
                governed_checkpoint=checkpoint,
            )

    def test_cloud_authority_promotion_is_rejected(self) -> None:
        programme = copy.deepcopy(self.programme)
        programme["external_evidence_admission"]["provider_authority"][
            "cloud_run"
        ] = "FRESH_VERIFIED"
        with self.assertRaisesRegex(EffectiveStateError, "provider scope"):
            self.reconcile(programme=programme)

    def test_v3_drive_scope_promotion_is_rejected(self) -> None:
        checkpoint = copy.deepcopy(self.institution_checkpoint)
        checkpoint["provider_authority"]["google_drive_write"] = "FRESH_VERIFIED"
        with self.assertRaisesRegex(EffectiveStateError, "provider scope"):
            self.reconcile(institution_checkpoint=checkpoint)

    def test_drive_readback_loss_is_rejected(self) -> None:
        observation = copy.deepcopy(self.drive_observation)
        observation["readback_verified"] = False
        with self.assertRaisesRegex(EffectiveStateError, "Drive commercial release"):
            self.reconcile(drive_observation=observation)

    def test_final_artifact_drift_is_rejected(self) -> None:
        observation = copy.deepcopy(self.drive_observation)
        observation["artifact_id"] = 1
        with self.assertRaisesRegex(EffectiveStateError, "final PR120"):
            self.reconcile(drive_observation=observation)

    def test_owner_authority_drift_is_rejected(self) -> None:
        release = copy.deepcopy(self.governed_release)
        release["owner_authority"]["contracts"] = "AUTOMATED"
        checkpoint = self._rehash_release(release)
        institution = copy.deepcopy(self.institution_reconciliation)
        institution["owner_authority"]["contracts"] = "AUTOMATED"
        with self.assertRaisesRegex(EffectiveStateError, "owner-reserved authority"):
            self.reconcile(
                governed_release=release,
                governed_checkpoint=checkpoint,
                institution_reconciliation=institution,
            )

    def _rehash_release(self, release: dict) -> dict:
        release.pop("receipt_sha256", None)
        release["receipt_sha256"] = digest(release)
        checkpoint = copy.deepcopy(self.governed_checkpoint)
        checkpoint["release_receipt"]["receipt_sha256"] = release[
            "receipt_sha256"
        ]
        return checkpoint


if __name__ == "__main__":
    unittest.main()
