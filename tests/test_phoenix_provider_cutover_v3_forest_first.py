from __future__ import annotations

import unittest

from evidenceops.lex_omega.forest_first import (
    DefectClass,
    ForestFirstJusticeGate,
    ForestFirstRequest,
    LegalRouteCard,
    MeritsClaim,
    MeritsGenome,
    PleadingIntegrityFinding,
    PositionChangeCard,
    ProtectivePosture,
    RiskSignal,
    TeachBackCard,
)
from evidenceops.lex_omega.lex_omega import ReleaseState


class ForestFirstAirlockTests(unittest.TestCase):
    def genome(self) -> MeritsGenome:
        return MeritsGenome(
            matter_id="SYNTHETIC-MATTER",
            claims={
                "C1": MeritsClaim(
                    claim_id="C1",
                    text="A synthetic employer act occurred.",
                    evidence_refs=("SYNTHETIC-SRC-1",),
                )
            },
        )

    def route(self, **overrides: object) -> LegalRouteCard:
        data = dict(
            route_id="SYNTHETIC-ROUTE",
            forum="SYNTHETIC-FORUM",
            jurisdiction_source="SYNTHETIC-STATUTE",
            cause_of_action="SYNTHETIC-CAUSE",
            challenged_act_or_omission="SYNTHETIC-ACT",
            operative_date="2026-01-01",
            operative_date_basis="SYNTHETIC-SRC-1 records the act",
            filing_period="90 days",
            elements=("E1",),
            evidence_refs=("SYNTHETIC-SRC-1",),
            primary_remedy="SYNTHETIC-REMEDY",
            strongest_adverse_argument="Synthetic jurisdiction objection",
        )
        data.update(overrides)
        return LegalRouteCard(**data)

    def teach_back(self, **overrides: object) -> TeachBackCard:
        data = dict(
            dispute_or_issue="Synthetic statutory dispute",
            challenged_act="SYNTHETIC-ACT",
            operative_date_and_reason="2026-01-01 because SYNTHETIC-SRC-1 records it",
            forum_jurisdiction_reason="SYNTHETIC-STATUTE gives the forum power",
            strongest_evidence=("SYNTHETIC-SRC-1",),
            likely_opponent_argument="The forum lacks jurisdiction",
            requested_decision_or_remedy="SYNTHETIC-REMEDY",
        )
        data.update(overrides)
        return TeachBackCard(**data)

    def test_risk_signal_triggers_reversible_protection_without_accusation_proof(self) -> None:
        signal = RiskSignal(
            description="Synthetic adverse action may be developing",
            observed_indicators=("indicator-1", "indicator-2"),
            competing_explanations=("innocent explanation",),
            reversible_protective_actions=("preserve synthetic record",),
            falsification_tests=("inspect synthetic source",),
        )
        result = ForestFirstJusticeGate().evaluate(
            ForestFirstRequest(
                merits_genome=self.genome(),
                route_card=self.route(),
                teach_back=self.teach_back(),
                risk_signals=(signal,),
            )
        )
        self.assertEqual(result.posture, ProtectivePosture.ADVERSARIAL_READINESS)
        self.assertEqual(result.release_state, ReleaseState.PASS)
        self.assertEqual(result.protective_actions, ("preserve synthetic record",))

    def test_unproved_external_accusation_is_held(self) -> None:
        result = ForestFirstJusticeGate().evaluate(
            ForestFirstRequest(
                merits_genome=self.genome(),
                route_card=self.route(),
                teach_back=self.teach_back(),
                proposed_external_accusations=("A person deliberately leaked strategy",),
            )
        )
        self.assertFalse(result.accusation_release_allowed)
        self.assertIn("ACCUSATION_PROOF_REQUIRED", result.reason_codes)
        self.assertEqual(result.release_state, ReleaseState.PASS_WITH_LIMITATIONS)

    def test_missing_jurisdiction_or_source_forces_reframe(self) -> None:
        result = ForestFirstJusticeGate().evaluate(
            ForestFirstRequest(
                merits_genome=self.genome(),
                route_card=self.route(jurisdiction_source="", evidence_refs=()),
                teach_back=self.teach_back(),
            )
        )
        self.assertIn("ROUTE_MISSING_JURISDICTION_SOURCE", result.reason_codes)
        self.assertIn("ROUTE_MISSING_EVIDENCE_REFS", result.reason_codes)
        self.assertEqual(result.release_state, ReleaseState.REFRAME)

    def test_position_change_cannot_silently_adopt_opponent_premise(self) -> None:
        change = PositionChangeCard(
            subject="operative date",
            current_position="later date",
            proposed_position="earlier date",
            proposer="opponent",
            legal_basis="synthetic legal premise",
            factual_basis="synthetic factual premise",
            effect_if_accepted="may create a time-bar issue",
            effect_if_rejected="opponent must prove the earlier date",
            waiver_or_concession_risk="could be treated as a concession",
            recommendation="verify before adopting",
            informed_human_decision="",
        )
        result = ForestFirstJusticeGate().evaluate(
            ForestFirstRequest(
                merits_genome=self.genome(),
                route_card=self.route(),
                teach_back=self.teach_back(),
                position_changes=(change,),
            )
        )
        self.assertIn("POSITION_CHANGE_MISSING_INFORMED_HUMAN_DECISION", result.reason_codes)
        self.assertEqual(result.release_state, ReleaseState.PASS_WITH_LIMITATIONS)

    def test_teach_back_is_a_release_gate(self) -> None:
        result = ForestFirstJusticeGate().evaluate(
            ForestFirstRequest(
                merits_genome=self.genome(),
                route_card=self.route(),
                teach_back=self.teach_back(forum_jurisdiction_reason=""),
            )
        )
        self.assertIn("TEACHBACK_MISSING_FORUM_JURISDICTION_REASON", result.reason_codes)
        self.assertEqual(result.release_state, ReleaseState.PASS_WITH_LIMITATIONS)

    def test_ai_pleading_jurisdiction_defect_forces_reframe(self) -> None:
        finding = PleadingIntegrityFinding(
            defect=DefectClass.D3_JURISDICTIONAL_EXPOSURE,
            intended_meaning="statutory claim",
            filed_or_proposed_wording="wording that sounds like another route",
            legal_consequence="wrong-forum objection",
            safer_formulation="state statutory cause first",
        )
        result = ForestFirstJusticeGate().evaluate(
            ForestFirstRequest(
                merits_genome=self.genome(),
                route_card=self.route(),
                teach_back=self.teach_back(),
                pleading_findings=(finding,),
            )
        )
        self.assertIn("PLEADING_D3_JURISDICTIONAL_EXPOSURE", result.reason_codes)
        self.assertEqual(result.release_state, ReleaseState.REFRAME)

    def test_jfrie_is_non_bypassable(self) -> None:
        result = ForestFirstJusticeGate().evaluate(
            ForestFirstRequest(
                merits_genome=self.genome(),
                route_card=self.route(),
                teach_back=self.teach_back(),
                jfrie_status="FAIL",
            )
        )
        self.assertIn("JFRIE_FAIL_CLOSED", result.reason_codes)
        self.assertEqual(result.release_state, ReleaseState.DO_NOT_FILE)


if __name__ == "__main__":
    unittest.main()
