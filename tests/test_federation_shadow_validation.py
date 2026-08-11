from __future__ import annotations

import unittest

from evidenceops.caseforge.federation_shadow_validation import (
    HistoricalShadowValidator,
    ShadowIncident,
)


REAL_INCIDENTS = (
    ShadowIncident(
        "INVALID_ARGUMENT_OR_SCHEMA",
        "CONTROL tab/range lookup failed",
        "DISCOVER_SCHEMA_AND_RETRY_CORRECTED_ROUTE",
        "CAN-CRG-001",
    ),
    ShadowIncident(
        "STALE_BASE_HEAD_REJECTED",
        "PR stale-base rejection",
        "RECUT_CURRENT_MAIN_REAPPLY_DELTA_RERUN",
        "PR#334",
    ),
    ShadowIncident(
        "PHOENIX_EXPORT_REGRESSION",
        "Phoenix export purity test failed",
        "REPAIR_CODE_NOT_GATE_RERUN",
        "Airlock-31541736887",
    ),
    ShadowIncident(
        "CONNECTOR_STATE_STALE",
        "historical capability state was stale",
        "REPROBE_REFRESH_TWIN",
        "CAPABILITY-RESOLUTION+EVO02",
    ),
    ShadowIncident(
        "DIAGNOSIS_SUBSTITUTION",
        "diagnosis was substituted for mission repair",
        "DEFECT_TO_REPAIR_CONTINUE",
        "MISSION-CONTINUATION",
    ),
    ShadowIncident(
        "CONTROLLER_SOURCE_ADMISSION_DRIFT",
        "private receipt outran current main",
        "RECUT_CURRENT_MAIN_REAPPLY_DELTA_RERUN",
        "PR#349+PR#352",
    ),
    ShadowIncident(
        "SCHEDULED_ATTESTATION_WITHOUT_EXECUTION_PROOF",
        "attestation claimed runtime execution before provider scheduler proof",
        "QUARANTINE_REVERSE_REQUIRE_ACTUAL_RUNTIME",
        "ATT-NONCHAT-20260812-001-QUARANTINE",
    ),
    ShadowIncident(
        "RECEIPT_BINDING_DRIFT",
        "preliminary digest used non-identical proof strings instead of exact provider-persisted replay fields",
        "READBACK_RECOMPUTE_EXACT_PERSISTED_RECEIPT_BEFORE_PROMOTION",
        "RCP-FED-SHADOW-20260812-001-PRELIM-CORRECTION",
    ),
)


class HistoricalShadowValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = HistoricalShadowValidator()

    def test_real_incidents_match_current_safe_repair_policy(self) -> None:
        replays, receipt = self.validator.validate_suite(
            system_id="FEDERATION_OMEGA",
            source_commit="shadow-test-head",
            incidents=REAL_INCIDENTS,
        )
        self.assertEqual(8, len(replays))
        self.assertTrue(all(item.matched for item in replays))
        self.assertEqual("PASS", receipt.status)
        self.assertEqual(8, receipt.matched_count)
        self.assertEqual((), receipt.failed_fingerprints)
        self.assertFalse(receipt.external_effect)
        self.assertEqual(64, len(receipt.receipt_sha256))

    def test_false_attestation_replay_requires_quarantine_not_promotion(self) -> None:
        replay = self.validator.replay(REAL_INCIDENTS[6])
        self.assertEqual(
            "QUARANTINE_REVERSE_REQUIRE_ACTUAL_RUNTIME",
            replay.predicted_repair_code,
        )
        self.assertIn("quarantine", replay.expected_behavior.lower())
        self.assertIn("scheduler title", replay.prohibited_behavior.lower())
        self.assertFalse(replay.external_effect)

    def test_receipt_binding_drift_requires_exact_provider_readback(self) -> None:
        replay = self.validator.replay(REAL_INCIDENTS[7])
        self.assertTrue(replay.matched)
        self.assertEqual(
            "READBACK_RECOMPUTE_EXACT_PERSISTED_RECEIPT_BEFORE_PROMOTION",
            replay.predicted_repair_code,
        )
        self.assertIn("exact provider-persisted", replay.expected_behavior.lower())
        self.assertIn("semantically equivalent", replay.prohibited_behavior.lower())

    def test_stale_base_replay_never_forces_merge(self) -> None:
        replay = self.validator.replay(REAL_INCIDENTS[1])
        self.assertTrue(replay.matched)
        self.assertIn("recut", replay.expected_behavior.lower())
        self.assertIn("force", replay.prohibited_behavior.lower())

    def test_phoenix_replay_repairs_code_not_gate(self) -> None:
        replay = self.validator.replay(REAL_INCIDENTS[2])
        self.assertTrue(replay.matched)
        self.assertIn("repair", replay.expected_behavior.lower())
        self.assertIn("disable", replay.prohibited_behavior.lower())

    def test_unknown_failure_fails_closed(self) -> None:
        incident = ShadowIncident(
            "NEW_UNMODELLED_FAILURE",
            "new failure",
            "SOME_HISTORICAL_ACTION",
            "proof-ref",
        )
        replay = self.validator.replay(incident)
        self.assertFalse(replay.matched)
        self.assertEqual("UNKNOWN_POLICY", replay.predicted_repair_code)
        _, receipt = self.validator.validate_suite(
            system_id="FEDERATION_OMEGA",
            source_commit="shadow-test-head",
            incidents=(incident,),
        )
        self.assertEqual("FAIL", receipt.status)
        self.assertEqual(("NEW_UNMODELLED_FAILURE",), receipt.failed_fingerprints)

    def test_divergent_historical_action_fails_shadow(self) -> None:
        incident = ShadowIncident(
            "STALE_BASE_HEAD_REJECTED",
            "stale branch",
            "FORCE_MERGE_STALE_BRANCH",
            "bad-history-fixture",
        )
        replay = self.validator.replay(incident)
        self.assertFalse(replay.matched)
        _, receipt = self.validator.validate_suite(
            system_id="FEDERATION_OMEGA",
            source_commit="shadow-test-head",
            incidents=(incident,),
        )
        self.assertEqual("FAIL", receipt.status)

    def test_receipt_digest_is_deterministic(self) -> None:
        replays, first = self.validator.validate_suite(
            system_id="FEDERATION_OMEGA",
            source_commit="same-head",
            incidents=REAL_INCIDENTS,
        )
        _, second = self.validator.validate_suite(
            system_id="FEDERATION_OMEGA",
            source_commit="same-head",
            incidents=REAL_INCIDENTS,
        )
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)
        self.assertEqual(
            first.receipt_sha256,
            self.validator.receipt_digest_from_persisted_replays(
                system_id="FEDERATION_OMEGA",
                source_commit="same-head",
                replays=replays,
                status="PASS",
            ),
        )

    def test_receipt_digest_changes_if_persisted_proof_changes(self) -> None:
        replays, first = self.validator.validate_suite(
            system_id="FEDERATION_OMEGA",
            source_commit="same-head",
            incidents=REAL_INCIDENTS,
        )
        altered = list(replays)
        last = altered[-1]
        altered[-1] = type(last)(
            fingerprint=last.fingerprint,
            predicted_repair_code=last.predicted_repair_code,
            historical_success_code=last.historical_success_code,
            matched=last.matched,
            expected_behavior=last.expected_behavior,
            prohibited_behavior=last.prohibited_behavior,
            repair_proof_ref=last.repair_proof_ref + "-changed",
            policy_source=last.policy_source,
            external_effect=last.external_effect,
        )
        second = self.validator.receipt_digest_from_persisted_replays(
            system_id="FEDERATION_OMEGA",
            source_commit="same-head",
            replays=tuple(altered),
            status="PASS",
        )
        self.assertNotEqual(first.receipt_sha256, second)

    def test_registered_system_and_source_commit_are_required(self) -> None:
        with self.assertRaises(ValueError):
            self.validator.validate_suite(
                system_id="NOT_A_SYSTEM",
                source_commit="head",
                incidents=REAL_INCIDENTS,
            )
        with self.assertRaises(ValueError):
            self.validator.validate_suite(
                system_id="FEDERATION_OMEGA",
                source_commit="",
                incidents=REAL_INCIDENTS,
            )


if __name__ == "__main__":
    unittest.main()
