from __future__ import annotations

import unittest

from evidenceops.jurisdiction_first_referral_integrity.jfrie import (
    AuthorityClass,
    CauseElement,
    ReferralInput,
)
from evidenceops.jurisdiction_first_referral_integrity.jfrie_v2 import (
    ClaimRecord,
    ClaimStatus,
    ContaminationState,
    IntegrityGraph,
    JfrieV2Core,
    ProvenanceClass,
    ReleaseRequest,
    ReleaseState,
    SourceRecord,
)


def valid_referral() -> ReferralInput:
    return ReferralInput(
        instrument="LRA section 188A inquiry by arbitrator",
        forum="CCMA",
        cause_of_action="inquiry by arbitrator under LRA section 188A",
        cause_authority_ref="LRA s188A",
        cause_authority_class=AuthorityClass.STATUTE,
        specific_act_or_omission="initiated the prescribed inquiry procedure",
        dispute_date="2026-08-01",
        filing_date="2026-08-02",
        filing_period_rule="current verified forum rule",
        maturity_basis="prescribed trigger has arisen",
        elements=(
            CauseElement(
                "prescribed inquiry trigger",
                ("FACT-1",),
                "LRA s188A",
            ),
        ),
        remedy="conduct the inquiry within statutory/forum competence",
        remedy_authority_ref="LRA s188A",
        narrative="Bounded source-controlled referral narrative.",
        source_refs=("SRC-PRIMARY-1",),
        form_category="inquiry by arbitrator",
    )


def source(
    source_id: str,
    *,
    parent: str | None = None,
    primary: bool = True,
) -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
        provenance_class=(
            ProvenanceClass.PRIMARY_EVIDENCE
            if primary
            else ProvenanceClass.DERIVATIVE_SUMMARY
        ),
        authenticated=primary,
        parent_source_id=parent,
    )


def claim(
    claim_id: str,
    *,
    sources=("SRC-PRIMARY-1",),
    dependencies=(),
    status=ClaimStatus.VERIFIED,
    contamination=ContaminationState.CLEAN,
    contradictions=(),
    legal=True,
) -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id,
        exact_text=f"Exact proposition {claim_id}",
        normalized_text=f"normalized proposition {claim_id}",
        matter_id="MAT-188A",
        workstream_id="WS-JFRIE",
        origin_type=ProvenanceClass.PRIMARY_EVIDENCE,
        origin_reference="SRC-PRIMARY-1",
        source_ids=tuple(sources),
        evidence_status=status,
        authority_status="VERIFIED" if legal else "N/A",
        created_at="2026-08-12T00:00:00Z",
        last_verified_at="2026-08-12T00:00:00Z",
        dependency_ids=tuple(dependencies),
        contradiction_ids=tuple(contradictions),
        contamination_state=contamination,
        release_eligibility=False,
        legal_category="LRA s188A inquiry" if legal else "",
        authority_ref="LRA s188A" if legal else "",
    )


class JfrieV2CoreParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = IntegrityGraph()
        self.graph.register_source(source("SRC-PRIMARY-1"))
        self.engine = JfrieV2Core(self.graph)

    def eligible(self, claim_id: str) -> None:
        self.graph.mark_release_eligible(
            claim_id,
            timestamp="2026-08-12T00:30:00Z",
        )

    def test_verified_claim_requires_registered_source_provenance(self) -> None:
        with self.assertRaises(ValueError):
            self.graph.register_claim(claim("CLM-1", sources=()))
        with self.assertRaises(ValueError):
            self.graph.register_claim(claim("CLM-2", sources=("MISSING",)))

    def test_legal_category_requires_authority_provenance(self) -> None:
        broken = claim("CLM-1")
        broken = ClaimRecord(**{**broken.__dict__, "authority_ref": ""})
        with self.assertRaises(ValueError):
            self.graph.register_claim(broken)

    def test_derivative_copies_do_not_multiply_independent_support(self) -> None:
        self.graph.register_source(
            source("SRC-COPY-1", parent="SRC-PRIMARY-1", primary=False)
        )
        self.graph.register_source(
            source("SRC-COPY-2", parent="SRC-PRIMARY-1", primary=False)
        )
        roots = self.graph.independent_source_roots(
            ("SRC-PRIMARY-1", "SRC-COPY-1", "SRC-COPY-2")
        )
        self.assertEqual(("SRC-PRIMARY-1",), roots)
        self.assertEqual(
            "SRC-PRIMARY-1",
            self.graph.best_source(("SRC-COPY-1", "SRC-PRIMARY-1")).source_id,
        )

    def test_verified_clean_claim_is_not_implicitly_release_eligible(self) -> None:
        self.graph.register_claim(claim("CLM-1"))
        decision = self.engine.evaluate_release(
            ReleaseRequest(
                referral=valid_referral(),
                claim_ids=("CLM-1",),
                mandatory_gates={"truthgrid": True, "lex": True},
                owner_exclusions_passed=True,
                jfrie_recheck_passed=True,
                readback_ref="readback",
                snapshot_ref="snapshot",
            )
        )
        self.assertFalse(decision.allowed)
        self.assertIn("CLAIM_RELEASE_ELIGIBILITY_FALSE:CLM-1", decision.blockers)
        eligible = self.graph.mark_release_eligible(
            "CLM-1",
            timestamp="2026-08-12T00:31:00Z",
        )
        self.assertTrue(eligible.release_eligibility)

    def test_release_eligibility_requires_clean_releasable_claim(self) -> None:
        self.graph.register_claim(
            claim(
                "CLM-C",
                contradictions=("CON-1",),
            )
        )
        with self.assertRaisesRegex(ValueError, "UNRESOLVED_CONTRADICTIONS"):
            self.graph.mark_release_eligible(
                "CLM-C",
                timestamp="2026-08-12T00:31:00Z",
            )

        self.graph.register_claim(
            claim(
                "CLM-U",
                status=ClaimStatus.UNVERIFIED,
            )
        )
        with self.assertRaisesRegex(ValueError, "CLAIM_NOT_VERIFIED"):
            self.graph.mark_release_eligible(
                "CLM-U",
                timestamp="2026-08-12T00:31:00Z",
            )

    def test_claim_revision_preserves_history_and_revokes_release_eligibility(self) -> None:
        self.graph.register_claim(claim("CLM-1"))
        self.eligible("CLM-1")
        self.assertTrue(self.graph.claims["CLM-1"].release_eligibility)
        revised = self.graph.revise_claim(
            "CLM-1",
            new_text="Corrected proposition",
            new_normalized_text="corrected proposition",
            new_status=ClaimStatus.VERIFIED_WITH_LIMITATION,
            actor="JFRIE",
            reason="source conflict repaired",
            timestamp="2026-08-12T01:00:00Z",
        )
        self.assertEqual("Corrected proposition", revised.exact_text)
        self.assertFalse(revised.release_eligibility)
        self.assertEqual(1, len(self.graph.mutations))
        self.assertEqual(
            "Exact proposition CLM-1",
            self.graph.mutations[0].prior_text,
        )

    def test_quarantine_calculates_radius_recall_and_revokes_eligibility(self) -> None:
        self.graph.register_claim(claim("CLM-ROOT"))
        self.graph.register_claim(
            claim("CLM-CHILD", dependencies=("CLM-ROOT",))
        )
        self.graph.register_claim(claim("CLM-UNRELATED"))
        self.eligible("CLM-ROOT")
        self.eligible("CLM-CHILD")
        self.eligible("CLM-UNRELATED")
        self.graph.bind_artifact("ART-A", ("CLM-CHILD",))
        self.graph.bind_artifact("ART-B", ("CLM-UNRELATED",))
        result = self.engine.invalidate_and_recall(
            "CLM-ROOT",
            reason="material contradiction",
            timestamp="2026-08-12T02:00:00Z",
        )
        self.assertEqual(
            ("CLM-CHILD", "CLM-ROOT"),
            result.contamination_radius,
        )
        self.assertEqual(("ART-A",), result.affected_artifacts)
        self.assertTrue(result.recall_required)
        self.assertEqual(
            ContaminationState.QUARANTINED,
            self.graph.claims["CLM-ROOT"].contamination_state,
        )
        self.assertEqual(
            ContaminationState.NEEDS_REVIEW,
            self.graph.claims["CLM-CHILD"].contamination_state,
        )
        self.assertEqual(
            ContaminationState.CLEAN,
            self.graph.claims["CLM-UNRELATED"].contamination_state,
        )
        self.assertFalse(self.graph.claims["CLM-ROOT"].release_eligibility)
        self.assertFalse(self.graph.claims["CLM-CHILD"].release_eligibility)
        self.assertTrue(self.graph.claims["CLM-UNRELATED"].release_eligibility)

    def test_synchronization_claim_requires_readback(self) -> None:
        self.assertFalse(self.graph.synchronization_verified(""))
        self.assertTrue(
            self.graph.synchronization_verified("provider-readback-001")
        )

    def test_v1_hard_gate_is_preserved_inside_v2_release(self) -> None:
        self.graph.register_claim(claim("CLM-1"))
        self.eligible("CLM-1")
        invalid = valid_referral()
        invalid.cause_authority_ref = None
        decision = self.engine.evaluate_release(
            ReleaseRequest(
                referral=invalid,
                claim_ids=("CLM-1",),
                mandatory_gates={"truthgrid": True},
                owner_exclusions_passed=True,
                jfrie_recheck_passed=True,
                readback_ref="readback",
                snapshot_ref="snapshot",
            )
        )
        self.assertFalse(decision.allowed)
        self.assertIn("V1_REFERRAL_GATE_NOT_RELEASABLE", decision.blockers)

    def test_release_firewall_requires_gates_readback_snapshot_and_recheck(self) -> None:
        self.graph.register_claim(claim("CLM-1"))
        self.eligible("CLM-1")
        decision = self.engine.evaluate_release(
            ReleaseRequest(
                referral=valid_referral(),
                claim_ids=("CLM-1",),
                mandatory_gates={"truthgrid": False, "lex": True},
                owner_exclusions_passed=False,
                jfrie_recheck_passed=False,
                readback_ref="",
                snapshot_ref="",
            )
        )
        self.assertFalse(decision.allowed)
        self.assertIn("MANDATORY_GATE_FAILED:truthgrid", decision.blockers)
        self.assertIn("OWNER_EXCLUSIONS_NOT_CLEARED", decision.blockers)
        self.assertIn("POST_REPAIR_JFRIE_RECHECK_REQUIRED", decision.blockers)
        self.assertIn("NODE_READBACK_REQUIRED", decision.blockers)
        self.assertIn(
            "VERSION_IDENTIFIABLE_RELEASE_SNAPSHOT_REQUIRED",
            decision.blockers,
        )

    def test_quarantined_claim_blocks_release_and_cannot_be_reeligible(self) -> None:
        self.graph.register_claim(
            claim(
                "CLM-Q",
                status=ClaimStatus.QUARANTINED,
                contamination=ContaminationState.QUARANTINED,
            )
        )
        with self.assertRaises(ValueError):
            self.graph.mark_release_eligible(
                "CLM-Q",
                timestamp="2026-08-12T02:01:00Z",
            )
        decision = self.engine.evaluate_release(
            ReleaseRequest(
                referral=valid_referral(),
                claim_ids=("CLM-Q",),
                mandatory_gates={"truthgrid": True, "lex": True},
                owner_exclusions_passed=True,
                jfrie_recheck_passed=True,
                readback_ref="readback",
                snapshot_ref="snapshot",
            )
        )
        self.assertFalse(decision.allowed)
        self.assertTrue(
            any(
                item.startswith("CLAIM_NOT_RELEASE_VERIFIED:CLM-Q")
                for item in decision.blockers
            )
        )
        self.assertTrue(
            any(
                item.startswith("CLAIM_CONTAMINATED:CLM-Q")
                for item in decision.blockers
            )
        )

    def test_excluded_matter_cannot_be_resurrected_by_history(self) -> None:
        self.graph.register_claim(claim("CLM-1"))
        self.eligible("CLM-1")
        decision = self.engine.evaluate_release(
            ReleaseRequest(
                referral=valid_referral(),
                claim_ids=("CLM-1",),
                mandatory_gates={"truthgrid": True, "lex": True},
                owner_exclusions_passed=True,
                jfrie_recheck_passed=True,
                readback_ref="readback",
                snapshot_ref="snapshot",
                excluded_matter_ids=("MAT-188A",),
            )
        )
        self.assertFalse(decision.allowed)
        self.assertIn("EXCLUDED_MATTER_CLAIM:CLM-1", decision.blockers)

    def test_clean_release_requires_all_v1_and_v2_controls(self) -> None:
        self.graph.register_claim(claim("CLM-1"))
        self.eligible("CLM-1")
        decision = self.engine.evaluate_release(
            ReleaseRequest(
                referral=valid_referral(),
                claim_ids=("CLM-1",),
                mandatory_gates={
                    "truthgrid": True,
                    "lex": True,
                    "caseforge": True,
                },
                owner_exclusions_passed=True,
                jfrie_recheck_passed=True,
                readback_ref="provider-readback-001",
                snapshot_ref="snapshot-revision-sha256-001",
            )
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(ReleaseState.RELEASE_CLEARED, decision.state)
        self.assertEqual((), decision.blockers)
        self.assertFalse(decision.external_effect)


if __name__ == "__main__":
    unittest.main()
