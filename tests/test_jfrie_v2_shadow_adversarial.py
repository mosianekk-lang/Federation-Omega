from __future__ import annotations
import unittest
from evidenceops.jurisdiction_first_referral_integrity.jfrie_v2_validation import (
    FULL_V2_PARITY, ValidationMode, run_adversarial_validation, run_shadow_validation,
)
from evidenceops.jurisdiction_first_referral_integrity.jfrie_v2_semantic import (
    FULL_V2_PARITY as SEMANTIC_FULL_V2_PARITY,
    AUTHORITY_CEILING as SEMANTIC_AUTHORITY_CEILING,
    CitationNode, SemanticClaim, VersionObservation, build_release_snapshot,
    citation_cycles, compare_release_snapshot, fingerprint,
    paraphrase_candidates, version_findings,
)
from evidenceops.jurisdiction_first_referral_integrity.jfrie_v2_semantic_validation import (
    Mode as SemanticMode, run_adversarial as run_semantic_adversarial,
    run_shadow as run_semantic_shadow,
)

SOURCE_REF = "github-main-a9e5d331-jfrie-v2-bounded-slices"
OBSERVED_AT = "2026-08-12T06:05:24+02:00"

class JfrieV2ShadowAdversarialTests(unittest.TestCase):
    def test_full_v2_parity_remains_false(self) -> None:
        self.assertFalse(FULL_V2_PARITY)
        self.assertFalse(SEMANTIC_FULL_V2_PARITY)
        self.assertEqual("A1_INTERNAL", SEMANTIC_AUTHORITY_CEILING)

    def test_shadow_replay_suite_qualifies_without_external_effect(self) -> None:
        receipt = run_shadow_validation(source_ref=SOURCE_REF, observed_at=OBSERVED_AT)
        self.assertEqual(ValidationMode.SHADOW, receipt.mode)
        self.assertEqual((5, 5, ()), (receipt.case_count, receipt.passed_count, receipt.failed_case_ids))
        self.assertFalse(receipt.external_effect); self.assertTrue(receipt.qualifies)
        print(f"JFRIE_VALIDATION_RECEIPT mode=SHADOW id={receipt.receipt_id} sha256={receipt.result_sha256} cases={receipt.passed_count}/{receipt.case_count} external_effect={receipt.external_effect}")

    def test_adversarial_replay_suite_qualifies_without_external_effect(self) -> None:
        receipt = run_adversarial_validation(source_ref=SOURCE_REF, observed_at=OBSERVED_AT)
        self.assertEqual(ValidationMode.ADVERSARIAL, receipt.mode)
        self.assertEqual((9, 9, ()), (receipt.case_count, receipt.passed_count, receipt.failed_case_ids))
        self.assertFalse(receipt.external_effect); self.assertTrue(receipt.qualifies)
        print(f"JFRIE_VALIDATION_RECEIPT mode=ADVERSARIAL id={receipt.receipt_id} sha256={receipt.result_sha256} cases={receipt.passed_count}/{receipt.case_count} external_effect={receipt.external_effect}")

    def test_existing_receipts_are_deterministic_and_distinct(self) -> None:
        s1 = run_shadow_validation(source_ref=SOURCE_REF, observed_at=OBSERVED_AT)
        s2 = run_shadow_validation(source_ref=SOURCE_REF, observed_at=OBSERVED_AT)
        a = run_adversarial_validation(source_ref=SOURCE_REF, observed_at=OBSERVED_AT)
        self.assertEqual((s1.result_sha256, s1.receipt_id), (s2.result_sha256, s2.receipt_id))
        self.assertNotEqual(s1.result_sha256, a.result_sha256)

    def test_semantic_fingerprint_normalizes_without_truth_inference(self) -> None:
        a = SemanticClaim("C1", " The SOURCE records—the event! ", "MAT-1")
        b = SemanticClaim("C1", "the source records the event", "MAT-1")
        self.assertEqual(fingerprint(a), fingerprint(b))
        self.assertEqual(64, len(fingerprint(a)))

    def test_semantic_paraphrase_review_respects_matter_wall(self) -> None:
        candidates = paraphrase_candidates((
            SemanticClaim("C1", "employer initiated prescribed inquiry procedure", "MAT-1"),
            SemanticClaim("C2", "prescribed inquiry procedure employer initiated", "MAT-1"),
            SemanticClaim("C3", "network outage resolved", "MAT-1"),
            SemanticClaim("C4", "employer initiated prescribed inquiry procedure", "MAT-2"),
        ))
        self.assertEqual(1, len(candidates))
        self.assertEqual(("C1", "C2"), candidates[0][:2])

    def test_semantic_citation_cycle_is_explicit(self) -> None:
        cycles = citation_cycles((CitationNode("A", ("B",)), CitationNode("B", ("C",)), CitationNode("C", ("A",)), CitationNode("D", ())))
        self.assertEqual((("A", "B", "C", "A"),), cycles)

    def test_semantic_version_conflict_and_version_drift_are_separate(self) -> None:
        conflict = {f.code for f in version_findings((VersionObservation("O1", "V1", "1"*64), VersionObservation("O1", "V1", "2"*64)))}
        drift = {f.code for f in version_findings((VersionObservation("O2", "V1", "1"*64), VersionObservation("O2", "V2", "2"*64)))}
        self.assertIn("VERSION_IDENTITY_CONFLICT", conflict)
        self.assertIn("VERSION_SEMANTIC_DRIFT_REVIEW", drift)

    def test_semantic_post_release_monitor_detects_drift_and_missing(self) -> None:
        original = (SemanticClaim("A", "source records event", "MAT-1"), SemanticClaim("B", "attachment verified", "MAT-1"))
        snap = build_release_snapshot(original, "SNAP-1")
        drift = {f.code for f in compare_release_snapshot(snap, (SemanticClaim("A", "source records different event", "MAT-1"), SemanticClaim("B", "attachment verified", "MAT-1")))}
        missing = {f.code for f in compare_release_snapshot(snap, (SemanticClaim("A", "source records event", "MAT-1"),))}
        self.assertEqual({"POST_RELEASE_CLAIM_DRIFT"}, drift)
        self.assertEqual({"POST_RELEASE_CLAIM_MISSING"}, missing)

    def test_semantic_shadow_validation_qualifies_no_effect(self) -> None:
        receipt = run_semantic_shadow(SOURCE_REF, OBSERVED_AT)
        self.assertEqual(SemanticMode.SHADOW, receipt.mode)
        self.assertEqual((4, 4, ()), (receipt.case_count, receipt.passed_count, receipt.failed_case_ids))
        self.assertFalse(receipt.external_effect); self.assertTrue(receipt.qualifies)
        print(f"JFRIE_SEMANTIC_VALIDATION_RECEIPT mode=SHADOW id={receipt.receipt_id} sha256={receipt.result_sha256} cases={receipt.passed_count}/{receipt.case_count} external_effect={receipt.external_effect}")

    def test_semantic_adversarial_validation_qualifies_no_effect(self) -> None:
        receipt = run_semantic_adversarial(SOURCE_REF, OBSERVED_AT)
        self.assertEqual(SemanticMode.ADVERSARIAL, receipt.mode)
        self.assertEqual((6, 6, ()), (receipt.case_count, receipt.passed_count, receipt.failed_case_ids))
        self.assertFalse(receipt.external_effect); self.assertTrue(receipt.qualifies)
        print(f"JFRIE_SEMANTIC_VALIDATION_RECEIPT mode=ADVERSARIAL id={receipt.receipt_id} sha256={receipt.result_sha256} cases={receipt.passed_count}/{receipt.case_count} external_effect={receipt.external_effect}")

    def test_semantic_receipts_are_deterministic_and_distinct(self) -> None:
        s1 = run_semantic_shadow(SOURCE_REF, OBSERVED_AT); s2 = run_semantic_shadow(SOURCE_REF, OBSERVED_AT); a = run_semantic_adversarial(SOURCE_REF, OBSERVED_AT)
        self.assertEqual((s1.result_sha256, s1.receipt_id), (s2.result_sha256, s2.receipt_id))
        self.assertNotEqual(s1.result_sha256, a.result_sha256)

if __name__ == "__main__": unittest.main()
