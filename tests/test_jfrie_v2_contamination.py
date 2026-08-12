from __future__ import annotations

import unittest

from evidenceops.jurisdiction_first_referral_integrity.jfrie_v2 import IntegrityGraph, ProvenanceClass, SourceRecord
from evidenceops.jurisdiction_first_referral_integrity.jfrie_v2_contamination import (
    ArtifactNode,
    ArtifactState,
    AssertionKind,
    JfrieV2ContaminationScanner,
    PromptTemplateInput,
    PropositionInput,
    SignalSeverity,
)


class JfrieV2ContaminationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = IntegrityGraph()
        self.graph.register_source(SourceRecord("SRC-P", ProvenanceClass.PRIMARY_EVIDENCE, authenticated=True))
        self.graph.register_source(SourceRecord("SRC-D", ProvenanceClass.DERIVATIVE_SUMMARY, parent_source_id="SRC-P"))
        self.graph.register_source(SourceRecord("SRC-AI", ProvenanceClass.AI_ORIGIN))
        self.scanner = JfrieV2ContaminationScanner()

    def codes(self, signals):
        return {signal.code for signal in signals}

    def test_primary_fact_with_disclosed_origin_passes(self) -> None:
        proposition = PropositionInput(
            "P1", "The source records the event.", AssertionKind.FACT,
            ProvenanceClass.PRIMARY_EVIDENCE, ProvenanceClass.PRIMARY_EVIDENCE,
            ("SRC-P",), human_verified=True,
        )
        self.assertEqual((), self.scanner.scan_proposition(proposition, self.graph))

    def test_ai_or_derivative_origin_cannot_be_laundered_as_fact(self) -> None:
        proposition = PropositionInput(
            "P2", "The event definitely occurred.", AssertionKind.FACT,
            ProvenanceClass.AI_ORIGIN, ProvenanceClass.AI_ORIGIN,
            ("SRC-AI",), human_verified=False,
        )
        signals = self.scanner.scan_proposition(proposition, self.graph)
        codes = self.codes(signals)
        self.assertIn("INFERENCE_OR_DERIVATIVE_LAUNDERED_AS_FACT", codes)
        self.assertIn("FACT_WITHOUT_PRIMARY_OR_VERIFIED_SUPPORT", codes)
        self.assertIn("AI_ORIGIN_REQUIRES_HUMAN_OR_INDEPENDENT_VERIFICATION", codes)
        self.assertTrue(any(s.severity is SignalSeverity.BLOCK for s in signals))

    def test_origin_disclosure_mismatch_is_blocking(self) -> None:
        proposition = PropositionInput(
            "P3", "A summary says X.", AssertionKind.OBSERVATION,
            ProvenanceClass.DERIVATIVE_SUMMARY, ProvenanceClass.PRIMARY_EVIDENCE,
            ("SRC-D",),
        )
        signals = self.scanner.scan_proposition(proposition, self.graph)
        self.assertIn("ORIGIN_CLASS_DISCLOSURE_MISMATCH", self.codes(signals))
        self.assertTrue(any(s.severity is SignalSeverity.BLOCK for s in signals))

    def test_inference_requires_explicit_basis(self) -> None:
        proposition = PropositionInput(
            "P4", "X likely explains Y.", AssertionKind.INFERENCE,
            ProvenanceClass.INFERENCE, ProvenanceClass.INFERENCE,
            ("SRC-P",), inference_basis_ids=(),
        )
        signals = self.scanner.scan_proposition(proposition, self.graph)
        self.assertIn("INFERENCE_WITHOUT_EXPLICIT_BASIS", self.codes(signals))

    def test_causation_requires_basis_and_source_support(self) -> None:
        proposition = PropositionInput(
            "P5", "X caused Y.", AssertionKind.CAUSATION,
            ProvenanceClass.INFERENCE, ProvenanceClass.INFERENCE,
            ("SRC-AI",), causation_basis_ids=(),
        )
        codes = self.codes(self.scanner.scan_proposition(proposition, self.graph))
        self.assertIn("CAUSATION_WITHOUT_EXPLICIT_BASIS", codes)
        self.assertIn("CAUSATION_WITHOUT_PRIMARY_OR_VERIFIED_SUPPORT", codes)

    def test_legal_conclusion_requires_authority(self) -> None:
        proposition = PropositionInput(
            "P6", "The process was unlawful.", AssertionKind.LEGAL_CONCLUSION,
            ProvenanceClass.INFERENCE, ProvenanceClass.INFERENCE,
            ("SRC-P",), authority_ref="",
        )
        self.assertIn(
            "LEGAL_CONCLUSION_WITHOUT_AUTHORITY_PROVENANCE",
            self.codes(self.scanner.scan_proposition(proposition, self.graph)),
        )

    def test_unregistered_source_is_blocking(self) -> None:
        proposition = PropositionInput(
            "P7", "A fact.", AssertionKind.FACT,
            ProvenanceClass.PRIMARY_EVIDENCE, ProvenanceClass.PRIMARY_EVIDENCE,
            ("MISSING",), human_verified=True,
        )
        signals = self.scanner.scan_proposition(proposition, self.graph)
        self.assertIn("UNREGISTERED_PROPOSITION_SOURCE", self.codes(signals))

    def test_explicit_template_integrity_weakening_is_blocked(self) -> None:
        template = PromptTemplateInput(
            "T1", "Produce a filing.", ProvenanceClass.USER_SUPPLIED, "DOC-1",
            promotes_unverified_to_verified=True,
            suppresses_adverse_evidence=True,
            overrides_release_gate=True,
        )
        signals = self.scanner.scan_template(template)
        codes = self.codes(signals)
        self.assertIn("TEMPLATE_PROMOTES_UNVERIFIED_TO_VERIFIED", codes)
        self.assertIn("TEMPLATE_SUPPRESSES_ADVERSE_EVIDENCE", codes)
        self.assertIn("TEMPLATE_OVERRIDES_RELEASE_GATE", codes)
        self.assertTrue(all(s.severity is SignalSeverity.BLOCK for s in signals))

    def test_prompt_language_matches_are_review_not_automatic_misconduct(self) -> None:
        template = PromptTemplateInput(
            "T2",
            "Ignore previous formatting instructions but do not bypass verification.",
            ProvenanceClass.USER_SUPPLIED,
            "DOC-2",
        )
        signals = self.scanner.scan_template(template)
        self.assertTrue(signals)
        self.assertTrue(any(s.code.startswith("PROMPT_LANGUAGE_REVIEW:") for s in signals))
        self.assertTrue(all(s.severity is SignalSeverity.REVIEW for s in signals))

    def test_tainted_template_propagates_to_children_not_unrelated_artifacts(self) -> None:
        artifacts = (
            ArtifactNode("ROOT", template_ids=("BAD-TEMPLATE",)),
            ArtifactNode("CHILD", parent_artifact_ids=("ROOT",)),
            ArtifactNode("GRANDCHILD", parent_artifact_ids=("CHILD",)),
            ArtifactNode("UNRELATED"),
        )
        result = self.scanner.propagate_artifact_contamination(
            artifacts,
            contaminated_template_ids=("BAD-TEMPLATE",),
        )
        self.assertEqual(ArtifactState.TAINTED, result.states["ROOT"])
        self.assertEqual(ArtifactState.NEEDS_REVIEW, result.states["CHILD"])
        self.assertEqual(ArtifactState.NEEDS_REVIEW, result.states["GRANDCHILD"])
        self.assertEqual(ArtifactState.CLEAN, result.states["UNRELATED"])
        self.assertEqual(("ROOT",), result.contaminated_roots)
        self.assertEqual(("CHILD", "GRANDCHILD"), result.affected_descendants)
        self.assertEqual(("UNRELATED",), result.unaffected_artifacts)

    def test_directly_tainted_artifact_propagates_without_touching_siblings(self) -> None:
        artifacts = (
            ArtifactNode("A"),
            ArtifactNode("B", parent_artifact_ids=("A",)),
            ArtifactNode("C", parent_artifact_ids=("A",)),
        )
        result = self.scanner.propagate_artifact_contamination(
            artifacts,
            directly_tainted_artifact_ids=("B",),
        )
        self.assertEqual(ArtifactState.CLEAN, result.states["A"])
        self.assertEqual(ArtifactState.TAINTED, result.states["B"])
        self.assertEqual(ArtifactState.CLEAN, result.states["C"])

    def test_unknown_tainted_artifact_and_missing_parent_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            self.scanner.propagate_artifact_contamination(
                (ArtifactNode("A"),), directly_tainted_artifact_ids=("MISSING",)
            )
        with self.assertRaises(ValueError):
            self.scanner.propagate_artifact_contamination(
                (ArtifactNode("A", parent_artifact_ids=("MISSING",)),)
            )


if __name__ == "__main__":
    unittest.main()
