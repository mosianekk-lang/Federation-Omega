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
    RiskSignalState,
    TeachBackCard,
)
from evidenceops.lex_omega.lex_omega import ReleaseState


def _genome() -> MeritsGenome:
    return MeritsGenome(
        matter_id="MATTER-1",
        claims={
            "C1": MeritsClaim(
                claim_id="C1",
                text="An employer act occurred.",
                evidence_refs=("SRC-1",),
            )
        },
    )


def _route(**overrides: object) -> LegalRouteCard:
    data = dict(
        route_id="ROUTE-1",
        forum="FORUM",
        jurisdiction_source="STATUTE-1",
        cause_of_action="CAUSE-1",
        challenged_act_or_omission="ACT-1",
        operative_date="2026-01-01",
        operative_date_basis="SRC-1 records the act on that date",
        filing_period="90 days",
        elements=("E1",),
        evidence_refs=("SRC-1",),
        primary_remedy="REMEDY-1",
        strongest_adverse_argument="OPPONENT-ARGUMENT-1",
    )
    data.update(overrides)
    return LegalRouteCard(**data)


def _teach_back(**overrides: object) -> TeachBackCard:
    data = dict(
        dispute_or_issue="The employer act is challenged under CAUSE-1.",
        challenged_act="ACT-1",
        operative_date_and_reason="2026-01-01 because SRC-1 records the act.",
        forum_jurisdiction_reason="STATUTE-1 gives FORUM power over CAUSE-1.",
        strongest_evidence=("SRC-1",),
        likely_opponent_argument="The forum lacks jurisdiction.",
        requested_decision_or_remedy="REMEDY-1",
    )
    data.update(overrides)
    return TeachBackCard(**data)


def test_user_risk_signal_triggers_protection_without_proving_accusation() -> None:
    signal = RiskSignal(
        description="Possible adverse action is developing",
        observed_indicators=("tone changed", "access changed"),
        reversible_protective_actions=("preserve records", "calculate deadlines"),
        competing_explanations=("ordinary administration",),
        falsification_tests=("check written instruction",),
    )
    result = ForestFirstJusticeGate().evaluate(
        ForestFirstRequest(
            merits_genome=_genome(),
            route_card=_route(),
            teach_back=_teach_back(),
            risk_signals=(signal,),
        )
    )

    assert result.posture is ProtectivePosture.ADVERSARIAL_READINESS
    assert result.protective_actions == ("preserve records", "calculate deadlines")
    assert result.release_state is ReleaseState.PASS
    assert result.accusation_release_allowed is True


def test_external_accusation_is_held_without_proof_even_when_risk_is_active() -> None:
    signal = RiskSignal(
        description="Possible information leakage",
        state=RiskSignalState.USER_SUPPLIED_RISK_SIGNAL,
        reversible_protective_actions=("compartmentalise future disclosures",),
    )
    result = ForestFirstJusticeGate().evaluate(
        ForestFirstRequest(
            merits_genome=_genome(),
            route_card=_route(),
            teach_back=_teach_back(),
            risk_signals=(signal,),
            proposed_external_accusations=("A named person deliberately leaked strategy",),
        )
    )

    assert result.posture is ProtectivePosture.PROTECTIVE_READINESS
    assert result.accusation_release_allowed is False
    assert "ACCUSATION_PROOF_REQUIRED" in result.reason_codes
    assert result.release_state is ReleaseState.PASS_WITH_LIMITATIONS


def test_external_accusation_may_clear_threshold_when_evidence_is_bound() -> None:
    result = ForestFirstJusticeGate().evaluate(
        ForestFirstRequest(
            merits_genome=_genome(),
            route_card=_route(),
            teach_back=_teach_back(),
            proposed_external_accusations=("A factual allegation requiring proof",),
            accusation_evidence_refs=("SRC-A", "SRC-B"),
        )
    )

    assert result.accusation_release_allowed is True
    assert "ACCUSATION_PROOF_REQUIRED" not in result.reason_codes
    assert result.release_state is ReleaseState.PASS


def test_incomplete_legal_route_reframes_before_drafting() -> None:
    result = ForestFirstJusticeGate().evaluate(
        ForestFirstRequest(
            merits_genome=_genome(),
            route_card=_route(jurisdiction_source="", evidence_refs=()),
            teach_back=_teach_back(),
        )
    )

    assert "ROUTE_MISSING_JURISDICTION_SOURCE" in result.reason_codes
    assert "ROUTE_MISSING_EVIDENCE_REFS" in result.reason_codes
    assert result.release_state is ReleaseState.REFRAME


def test_position_change_requires_informed_human_decision() -> None:
    change = PositionChangeCard(
        subject="operative date",
        current_position="2026-01-30",
        proposed_position="2026-01-01",
        proposer="opponent",
        legal_basis="opponent says accrual occurred on first act",
        factual_basis="SRC-0",
        effect_if_accepted="may create a time-bar issue",
        effect_if_rejected="opponent must prove the earlier accrual date",
        waiver_or_concession_risk="could be treated as a concession on accrual",
        recommendation="do not adopt until legal and factual basis is verified",
        informed_human_decision="",
    )
    result = ForestFirstJusticeGate().evaluate(
        ForestFirstRequest(
            merits_genome=_genome(),
            route_card=_route(),
            teach_back=_teach_back(),
            position_changes=(change,),
        )
    )

    assert "POSITION_CHANGE_MISSING_INFORMED_HUMAN_DECISION" in result.reason_codes
    assert result.release_state is ReleaseState.PASS_WITH_LIMITATIONS


def test_teach_back_failure_blocks_unexplained_filing_readiness() -> None:
    result = ForestFirstJusticeGate().evaluate(
        ForestFirstRequest(
            merits_genome=_genome(),
            route_card=_route(),
            teach_back=_teach_back(forum_jurisdiction_reason=""),
        )
    )

    assert "TEACHBACK_MISSING_FORUM_JURISDICTION_REASON" in result.reason_codes
    assert result.release_state is ReleaseState.PASS_WITH_LIMITATIONS


def test_ai_pleading_integrity_blocking_defect_requires_reframe() -> None:
    finding = PleadingIntegrityFinding(
        defect=DefectClass.D3_JURISDICTIONAL_EXPOSURE,
        intended_meaning="statutory employment claim",
        filed_or_proposed_wording="language sounding like contract enforcement",
        legal_consequence="opponent can argue wrong forum",
        safer_formulation="state the statutory cause first",
    )
    result = ForestFirstJusticeGate().evaluate(
        ForestFirstRequest(
            merits_genome=_genome(),
            route_card=_route(),
            teach_back=_teach_back(),
            pleading_findings=(finding,),
        )
    )

    assert "PLEADING_D3_JURISDICTIONAL_EXPOSURE" in result.reason_codes
    assert result.release_state is ReleaseState.REFRAME


def test_jfrie_remains_a_non_bypassable_hard_gate() -> None:
    result = ForestFirstJusticeGate().evaluate(
        ForestFirstRequest(
            merits_genome=_genome(),
            route_card=_route(),
            teach_back=_teach_back(),
            jfrie_status="FAIL",
        )
    )

    assert "JFRIE_FAIL_CLOSED" in result.reason_codes
    assert result.release_state is ReleaseState.DO_NOT_FILE
