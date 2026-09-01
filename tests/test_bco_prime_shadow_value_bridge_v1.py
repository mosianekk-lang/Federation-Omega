from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from benchmarking.cfbe_omega.bco_prime_shadow_value_bridge_v1 import (
    PAIR_COUNT,
    SCHEMA,
    _canonical_hash,
    build_cases,
    evaluate_prime_value_bridge,
    probe_case,
    run_shadow_campaign,
)
from benchmarking.cfbe_omega.federation_competitive_upgrade_fabric_v1 import (
    ResolvedEvidenceRef,
)


SOURCE = "a" * 40


def _resolved(subject: str, seed: str) -> ResolvedEvidenceRef:
    return ResolvedEvidenceRef(
        evidence_id=f"evidence-{seed}",
        subject=subject,
        verifier_id="proofos-independent",
        payload_sha256="sha256:" + seed * 64,
        receipt_sha256="sha256:" + ("f" if seed != "f" else "e") * 64,
        independently_read_back=True,
    )


def _hosted_shadow() -> dict:
    with patch.dict(os.environ, {"GITHUB_ACTIONS": ""}, clear=False):
        receipt = run_shadow_campaign(
            source_head_sha=SOURCE,
            require_github_actions=False,
            cross_process_cases=0,
        ).to_dict()
    receipt.update(
        evidence_mode="HOSTED_SHADOW",
        github_actions_runtime=True,
        hosted_shadow_qualified=True,
        candidate_mean_quality=0.95,
        baseline_mean_quality=0.50,
        quality_delta=0.45,
        hard_regressions=0,
        pairwise_regression_count=0,
        pair_count=30,
    )
    return receipt


def _foundry(*, source: str = SOURCE, pairs: int = 30, value: bool = True,
             stable: bool = False, effect: bool = False) -> dict:
    payload = {
        "schema": "CFBE-VALUE-FOUNDRY-V1",
        "champion_id": "bco-incumbent",
        "candidate_id": "bco-prime",
        "source_head_sha": source,
        "resolved_evidence_count": pairs * 2,
        "owner_value_pair_count": pairs,
        "owner_value_proven": value,
        "provider_deployment_proven": False,
        "decision": "OWNER_VALUE_PROVEN_FOR_BOUNDED_INTERNAL_REVIEW" if value else "HOLD_OWNER_VALUE_OPEN",
        "blockers": (),
        "stable_promotion_allowed": stable,
        "provider_effect_authorized": effect,
        "external_effect": effect,
        "truth_boundary": ("test-fixture",),
    }
    return {**payload, "receipt_sha256": _canonical_hash(payload)}


class BCOPrimeShadowValueBridgeV1Tests(unittest.TestCase):
    def test_corpus_has_thirty_pairs_and_all_six_meta_actions(self):
        cases = build_cases()
        self.assertEqual(PAIR_COUNT, len(cases))
        counts: dict[str, int] = {}
        for case in cases:
            counts[case.oracle.expected_action.value] = counts.get(case.oracle.expected_action.value, 0) + 1
        self.assertEqual(
            {
                "CONTINUE": 5,
                "REFLECT": 5,
                "SEEK_EVIDENCE": 5,
                "REPLAN": 5,
                "CHALLENGE": 5,
                "ROLLBACK": 5,
            },
            counts,
        )

    def test_local_campaign_is_synthetic_and_cannot_promote(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": ""}, clear=False):
            receipt = run_shadow_campaign(
                source_head_sha=SOURCE,
                cross_process_cases=3,
            )
        self.assertEqual(SCHEMA, receipt.schema)
        self.assertEqual("SYNTHETIC_SHADOW", receipt.evidence_mode)
        self.assertFalse(receipt.hosted_shadow_qualified)
        self.assertEqual(30, receipt.pair_count)
        self.assertEqual(3, receipt.cross_process_replay_count)
        self.assertEqual(1.0, receipt.cross_process_replay_ratio)
        self.assertGreaterEqual(receipt.quality_delta, 0.02)
        self.assertEqual(0, receipt.pairwise_regression_count)
        self.assertEqual(0, receipt.hard_regressions)
        self.assertFalse(receipt.owner_value_proven)
        self.assertFalse(receipt.bounded_topology_control_authorized)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.stable_promotion_authorized)

    def test_hosted_classification_cannot_be_claimed_by_argument_only(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": ""}, clear=False):
            with self.assertRaises(RuntimeError):
                run_shadow_campaign(
                    source_head_sha=SOURCE,
                    require_github_actions=True,
                    cross_process_cases=0,
                )

    def test_probe_receipt_is_deterministic(self):
        self.assertEqual(probe_case(0), probe_case(0))
        self.assertNotEqual(probe_case(0)["case_id"], probe_case(1)["case_id"])

    def test_bridge_holds_without_independently_resolved_shadow_and_rollback(self):
        result = evaluate_prime_value_bridge(
            shadow_receipt=_hosted_shadow(),
            value_foundry_receipt=_foundry(),
            resolved_shadow_evidence=None,
            resolved_rollback_evidence=None,
        )
        self.assertFalse(result.bounded_topology_control_candidate)
        self.assertIn("PRIME_RESOLVED_SHADOW_EVIDENCE_REQUIRED", result.blockers)
        self.assertIn("PRIME_RESOLVED_ROLLBACK_EVIDENCE_REQUIRED", result.blockers)

    def test_bridge_requires_same_source_head(self):
        shadow = _hosted_shadow()
        result = evaluate_prime_value_bridge(
            shadow_receipt=shadow,
            value_foundry_receipt=_foundry(source="b" * 40),
            resolved_shadow_evidence=_resolved(f"bco-prime-shadow:{SOURCE}", "1"),
            resolved_rollback_evidence=_resolved(f"bco-prime-rollback:{SOURCE}", "2"),
        )
        self.assertFalse(result.bounded_topology_control_candidate)
        self.assertIn("PRIME_FOUNDRY_SOURCE_HEAD_MISMATCH", result.blockers)

    def test_bridge_requires_thirty_real_owner_value_pairs(self):
        result = evaluate_prime_value_bridge(
            shadow_receipt=_hosted_shadow(),
            value_foundry_receipt=_foundry(pairs=29),
            resolved_shadow_evidence=_resolved(f"bco-prime-shadow:{SOURCE}", "1"),
            resolved_rollback_evidence=_resolved(f"bco-prime-rollback:{SOURCE}", "2"),
        )
        self.assertFalse(result.bounded_topology_control_candidate)
        self.assertIn("PRIME_THIRTY_PROSPECTIVE_OWNER_VALUE_PAIRS_REQUIRED", result.blockers)

    def test_complete_typed_evidence_can_only_reach_bounded_topology_candidate(self):
        result = evaluate_prime_value_bridge(
            shadow_receipt=_hosted_shadow(),
            value_foundry_receipt=_foundry(),
            resolved_shadow_evidence=_resolved(f"bco-prime-shadow:{SOURCE}", "1"),
            resolved_rollback_evidence=_resolved(f"bco-prime-rollback:{SOURCE}", "2"),
        )
        self.assertTrue(result.bounded_topology_control_candidate, result.blockers)
        self.assertEqual("CANDIDATE_BOUNDED_TOPOLOGY_CONTROL", result.decision)
        self.assertFalse(result.external_effect_control_allowed)
        self.assertFalse(result.stable_self_promotion_allowed)

    def test_foundry_authority_violation_blocks_bridge(self):
        result = evaluate_prime_value_bridge(
            shadow_receipt=_hosted_shadow(),
            value_foundry_receipt=_foundry(stable=True, effect=True),
            resolved_shadow_evidence=_resolved(f"bco-prime-shadow:{SOURCE}", "1"),
            resolved_rollback_evidence=_resolved(f"bco-prime-rollback:{SOURCE}", "2"),
        )
        self.assertFalse(result.bounded_topology_control_candidate)
        self.assertIn("PRIME_FOUNDRY_AUTHORITY_BOUNDARY_VIOLATION", result.blockers)


if __name__ == "__main__":
    unittest.main()
