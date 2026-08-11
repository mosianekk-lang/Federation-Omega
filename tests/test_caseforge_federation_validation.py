from __future__ import annotations

import unittest

from evidenceops.caseforge.federation_validation import (
    AutoFixLaboratory,
    CapabilityForge,
    CapabilityProbe,
    ContinuityForge,
    ContinuityProbe,
    FederationEvaluationContract,
    MaturityState,
    RecoveryTrace,
    promote_contract,
)


class FederationEvaluationContractTests(unittest.TestCase):
    def test_contract_is_internal_and_requires_proof_above_design(self) -> None:
        designed = FederationEvaluationContract(
            component_id="X",
            mission="test mission",
            hypothesis="test hypothesis",
            baseline_ref="BASE",
            metrics={"accuracy": 1.0},
        ).validate()
        self.assertEqual(MaturityState.DESIGNED, designed.maturity)
        self.assertFalse(designed.external_effect)

        with self.assertRaisesRegex(ValueError, "regression proof"):
            FederationEvaluationContract(
                component_id="X",
                mission="test mission",
                hypothesis="test hypothesis",
                baseline_ref="BASE",
                metrics={"accuracy": 1.0},
                maturity=MaturityState.DETERMINISTIC_TESTED,
            ).validate()

    def test_maturity_must_promote_sequentially(self) -> None:
        designed = FederationEvaluationContract(
            component_id="X",
            mission="test mission",
            hypothesis="test hypothesis",
            baseline_ref="BASE",
            metrics={"accuracy": 1.0},
        ).validate()
        tested = promote_contract(
            designed,
            target=MaturityState.DETERMINISTIC_TESTED,
            regression_passed=True,
            red_team_passed=False,
            proof_receipt="RCP-1",
        )
        self.assertEqual(MaturityState.DETERMINISTIC_TESTED, tested.maturity)
        with self.assertRaisesRegex(ValueError, "sequential"):
            promote_contract(
                tested,
                target=MaturityState.CANARY_VALIDATED,
                regression_passed=True,
                red_team_passed=True,
                proof_receipt="RCP-2",
            )


class ContinuityForgeTests(unittest.TestCase):
    def test_clean_recovery_preserves_corrections_provenance_and_routes(self) -> None:
        probe = ContinuityProbe(
            expected_state={"status": "CURRENT", "date": "2026-08-11", "route": "PAIA"},
            recovered_state={"status": "CURRENT", "date": "2026-08-11", "route": "PAIA"},
            expected_sources={"status": "SRC-1", "date": "SRC-2"},
            recovered_sources={"status": "SRC-1", "date": "SRC-2"},
            corrected_keys=frozenset({"date"}),
            superseded_values={"date": "2026-07-01"},
            expected_routes={"claim-1": "PAIA", "claim-2": "LABOUR"},
            recovered_routes={"claim-1": "PAIA", "claim-2": "LABOUR"},
            expected_contradictions=frozenset({"C-1"}),
            detected_contradictions=frozenset({"C-1"}),
        )
        result = ContinuityForge().evaluate(probe)
        self.assertEqual(1.0, result.score)
        self.assertEqual((), result.failure_fingerprints)

    def test_stale_corrected_state_is_a_permanent_failure_signal(self) -> None:
        probe = ContinuityProbe(
            expected_state={"referral": "NOT_FILED"},
            recovered_state={"referral": "FILED"},
            expected_sources={"referral": "PRIMARY-1"},
            recovered_sources={"referral": "OLD-SUMMARY"},
            corrected_keys=frozenset({"referral"}),
            superseded_values={"referral": "FILED"},
            expected_routes={"claim": "188A"},
            recovered_routes={"claim": "ULP"},
        )
        result = ContinuityForge().evaluate(probe)
        joined = "|".join(result.failure_fingerprints)
        self.assertIn("CONTINUITY_STALE_STATE_REINTRODUCED", joined)
        self.assertIn("CONTINUITY_PROVENANCE_DRIFT", joined)
        self.assertIn("CONTINUITY_ROUTE_COLLAPSE", joined)
        self.assertLess(result.score, 1.0)


class CapabilityForgeTests(unittest.TestCase):
    def test_only_fresh_semantic_readback_and_authority_verified_capabilities_are_eligible(self) -> None:
        probes = [
            CapabilityProbe(
                capability_id="github",
                heartbeat_state="SESSION_CONNECTOR_AVAILABLE",
                ttl_seconds=3600,
                age_seconds=20,
                semantic_ok=True,
                readback_ok=True,
                authority_verified=True,
                reliability=0.99,
            ),
            CapabilityProbe(
                capability_id="ai-studio",
                heartbeat_state="ADAPTER_REQUIRED",
                ttl_seconds=3600,
                age_seconds=20,
                semantic_ok=False,
                readback_ok=False,
                authority_verified=False,
                reliability=0.5,
            ),
            CapabilityProbe(
                capability_id="stale-drive",
                heartbeat_state="SESSION_CONNECTOR_AVAILABLE",
                ttl_seconds=60,
                age_seconds=600,
                semantic_ok=True,
                readback_ok=True,
                authority_verified=True,
                reliability=0.9,
            ),
        ]
        result = CapabilityForge().evaluate(probes)
        self.assertEqual(("github",), result.eligible)
        self.assertEqual(("ai-studio", "stale-drive"), result.degraded)
        self.assertIn("AO-CRA:CAPABILITY:ai-studio", result.ao_cra_builds)
        self.assertIn("AO-CRA:CAPABILITY:stale-drive", result.ao_cra_builds)

    def test_minimum_sufficient_route_uses_verified_set_only(self) -> None:
        forge = CapabilityForge()
        result = forge.evaluate(
            [
                CapabilityProbe("A", "SESSION_CONNECTOR_AVAILABLE", 60, 1, True, True, True),
                CapabilityProbe("B", "SESSION_CONNECTOR_AVAILABLE", 60, 1, True, True, True),
                CapabilityProbe("C", "ADAPTER_REQUIRED", 60, 1, True, True, True),
            ]
        )
        selected, unresolved = forge.select_minimum_sufficient(
            {"read", "legal", "visual"},
            {"A": {"read", "legal"}, "B": {"visual"}, "C": {"read", "legal", "visual"}},
            result,
        )
        self.assertEqual(("A", "B"), selected)
        self.assertEqual((), unresolved)


class AutoFixLaboratoryTests(unittest.TestCase):
    def test_good_recovery_trace_scores_full_marks(self) -> None:
        trace = RecoveryTrace(
            failure_fingerprint="TIMEOUT-A",
            original_failure_preserved=True,
            deterministic_classification=True,
            circuit_opened_on_repeat=True,
            unchanged_broken_lane_retried=False,
            unaffected_lanes_continued=True,
            reversible_repair=True,
            state_integrity_ok=True,
            independent_readback_ok=True,
            rollback_available=True,
            recovery_completed=True,
        )
        result = AutoFixLaboratory().evaluate([trace])
        self.assertEqual(1.0, result.score)
        self.assertEqual((), result.failure_fingerprints)

    def test_false_completion_repeat_route_and_corruption_are_detected(self) -> None:
        trace = RecoveryTrace(
            failure_fingerprint="BROKEN-LANE",
            original_failure_preserved=False,
            deterministic_classification=False,
            circuit_opened_on_repeat=False,
            unchanged_broken_lane_retried=True,
            unaffected_lanes_continued=False,
            reversible_repair=False,
            state_integrity_ok=False,
            independent_readback_ok=False,
            rollback_available=False,
            recovery_completed=True,
        )
        result = AutoFixLaboratory().evaluate([trace])
        joined = "|".join(result.failure_fingerprints)
        self.assertIn("AUTOFIX_FAILURE_EVIDENCE_LOST", joined)
        self.assertIn("AUTOFIX_REPEAT_ROUTE_VIOLATION", joined)
        self.assertIn("AUTOFIX_STATE_CORRUPTION", joined)
        self.assertIn("AUTOFIX_FALSE_COMPLETION", joined)
        self.assertIn("AUTOFIX_ROLLBACK_MISSING", joined)
        self.assertLess(result.score, 0.5)


if __name__ == "__main__":
    unittest.main()
