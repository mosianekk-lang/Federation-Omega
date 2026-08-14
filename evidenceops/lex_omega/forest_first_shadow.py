from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Tuple

from .forest_first import (
    DefectClass,
    ForestFirstJusticeGate,
    ForestFirstRequest,
    LegalRouteCard,
    MeritsClaim,
    MeritsGenome,
    PleadingIntegrityFinding,
    PositionChangeCard,
    RiskSignal,
    TeachBackCard,
)
from .lex_omega import ReleaseState


@dataclass(frozen=True)
class ShadowCase:
    case_id: str
    description: str
    request: ForestFirstRequest
    expected_forest_release: ReleaseState
    expected_legacy_release: ReleaseState
    expected_reason: str = ""


@dataclass(frozen=True)
class ShadowObservation:
    case_id: str
    description: str
    forest_release: str
    legacy_release: str
    expected_forest_release: str
    expected_legacy_release: str
    forest_match: bool
    legacy_match: bool
    forest_reason_codes: Tuple[str, ...]


@dataclass(frozen=True)
class ShadowReport:
    schema: str
    version: str
    no_external_effect: bool
    case_count: int
    forest_expected_match_count: int
    legacy_expected_match_count: int
    forest_expected_match_rate: float
    legacy_expected_match_rate: float
    forest_detected_risk_cases: int
    legacy_detected_risk_cases: int
    observations: Tuple[ShadowObservation, ...]
    limitations: Tuple[str, ...]


def _genome() -> MeritsGenome:
    return MeritsGenome(
        matter_id="SYNTHETIC-MATTER",
        claims={
            "C1": MeritsClaim(
                claim_id="C1",
                text="A synthetic employment act occurred.",
                evidence_refs=("SYNTHETIC-SRC-1",),
            )
        },
    )


def _route(**overrides: object) -> LegalRouteCard:
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
        strongest_adverse_argument="The forum lacks jurisdiction.",
    )
    data.update(overrides)
    return LegalRouteCard(**data)


def _teach_back(**overrides: object) -> TeachBackCard:
    data = dict(
        dispute_or_issue="Synthetic statutory employment dispute",
        challenged_act="SYNTHETIC-ACT",
        operative_date_and_reason="2026-01-01 because SYNTHETIC-SRC-1 records the act",
        forum_jurisdiction_reason="SYNTHETIC-STATUTE gives the forum jurisdiction",
        strongest_evidence=("SYNTHETIC-SRC-1",),
        likely_opponent_argument="The forum lacks jurisdiction.",
        requested_decision_or_remedy="SYNTHETIC-REMEDY",
    )
    data.update(overrides)
    return TeachBackCard(**data)


def legacy_single_pass_release(request: ForestFirstRequest) -> ReleaseState:
    """Deliberately minimal historical-style release heuristic.

    It models a weak single-pass process that asks only whether the external
    JFRIE status is passing and whether some prose/evidence exists. It is not a
    claim about any particular historical model or filing. The benchmark uses
    this as a fixed baseline to measure whether the new gate detects seeded
    failure classes that a shallow release check misses.
    """

    if request.jfrie_status not in {"PASS", "PASS_WITH_LIMITATIONS"}:
        return ReleaseState.DO_NOT_FILE
    if not request.merits_genome.claims:
        return ReleaseState.HOLD_FOR_SOURCE
    return ReleaseState.PASS


def build_shadow_cases() -> Tuple[ShadowCase, ...]:
    clean = ForestFirstRequest(
        merits_genome=_genome(),
        route_card=_route(),
        teach_back=_teach_back(),
    )

    missing_jurisdiction = ForestFirstRequest(
        merits_genome=_genome(),
        route_card=_route(jurisdiction_source=""),
        teach_back=_teach_back(),
    )

    missing_date_basis = ForestFirstRequest(
        merits_genome=_genome(),
        route_card=_route(operative_date_basis=""),
        teach_back=_teach_back(),
    )

    position_change = PositionChangeCard(
        subject="operative date",
        current_position="2026-01-30",
        proposed_position="2026-01-01",
        proposer="opponent",
        legal_basis="Opponent advances an earlier accrual theory.",
        factual_basis="SYNTHETIC-SRC-0",
        effect_if_accepted="May create a time-bar problem.",
        effect_if_rejected="Opponent must prove the earlier accrual theory.",
        waiver_or_concession_risk="Could be treated as an accrual concession.",
        recommendation="Verify before adopting.",
        informed_human_decision="",
    )
    unresolved_position_change = ForestFirstRequest(
        merits_genome=_genome(),
        route_card=_route(),
        teach_back=_teach_back(),
        position_changes=(position_change,),
    )

    missing_teachback = ForestFirstRequest(
        merits_genome=_genome(),
        route_card=_route(),
        teach_back=_teach_back(forum_jurisdiction_reason=""),
    )

    pleading_defect = ForestFirstRequest(
        merits_genome=_genome(),
        route_card=_route(),
        teach_back=_teach_back(),
        pleading_findings=(
            PleadingIntegrityFinding(
                defect=DefectClass.D3_JURISDICTIONAL_EXPOSURE,
                intended_meaning="statutory employment claim",
                filed_or_proposed_wording="wording that sounds like contract enforcement",
                legal_consequence="wrong-forum objection",
                safer_formulation="state the statutory cause before the remedy",
            ),
        ),
    )

    unsupported_accusation = ForestFirstRequest(
        merits_genome=_genome(),
        route_card=_route(),
        teach_back=_teach_back(),
        proposed_external_accusations=("A named person deliberately sabotaged the worker.",),
    )

    risk_signal = ForestFirstRequest(
        merits_genome=_genome(),
        route_card=_route(),
        teach_back=_teach_back(),
        risk_signals=(
            RiskSignal(
                description="Adverse action may be developing.",
                observed_indicators=("indicator-1", "indicator-2"),
                competing_explanations=("ordinary administration",),
                reversible_protective_actions=("preserve records", "calculate deadlines"),
                falsification_tests=("check primary record",),
            ),
        ),
    )

    jfrie_fail = ForestFirstRequest(
        merits_genome=_genome(),
        route_card=_route(),
        teach_back=_teach_back(),
        jfrie_status="FAIL",
    )

    return (
        ShadowCase("FF-SHADOW-001", "Clean complete synthetic route", clean, ReleaseState.PASS, ReleaseState.PASS),
        ShadowCase("FF-SHADOW-002", "Missing jurisdiction source", missing_jurisdiction, ReleaseState.REFRAME, ReleaseState.PASS, "ROUTE_MISSING_JURISDICTION_SOURCE"),
        ShadowCase("FF-SHADOW-003", "Missing operative-date basis", missing_date_basis, ReleaseState.REFRAME, ReleaseState.PASS, "ROUTE_MISSING_OPERATIVE_DATE_BASIS"),
        ShadowCase("FF-SHADOW-004", "Opponent-originated position change lacks informed human decision", unresolved_position_change, ReleaseState.PASS_WITH_LIMITATIONS, ReleaseState.PASS, "POSITION_CHANGE_MISSING_INFORMED_HUMAN_DECISION"),
        ShadowCase("FF-SHADOW-005", "Teach-back cannot explain forum jurisdiction", missing_teachback, ReleaseState.PASS_WITH_LIMITATIONS, ReleaseState.PASS, "TEACHBACK_MISSING_FORUM_JURISDICTION_REASON"),
        ShadowCase("FF-SHADOW-006", "AI pleading wording creates jurisdiction exposure", pleading_defect, ReleaseState.REFRAME, ReleaseState.PASS, "PLEADING_D3_JURISDICTIONAL_EXPOSURE"),
        ShadowCase("FF-SHADOW-007", "Serious external accusation lacks bound proof", unsupported_accusation, ReleaseState.PASS_WITH_LIMITATIONS, ReleaseState.PASS, "ACCUSATION_PROOF_REQUIRED"),
        ShadowCase("FF-SHADOW-008", "Risk signal should activate protection without changing release truth", risk_signal, ReleaseState.PASS, ReleaseState.PASS),
        ShadowCase("FF-SHADOW-009", "JFRIE hard failure remains non-bypassable", jfrie_fail, ReleaseState.DO_NOT_FILE, ReleaseState.DO_NOT_FILE, "JFRIE_FAIL_CLOSED"),
    )


def run_shadow(
    cases: Iterable[ShadowCase] | None = None,
    baseline: Callable[[ForestFirstRequest], ReleaseState] = legacy_single_pass_release,
) -> ShadowReport:
    selected = tuple(cases or build_shadow_cases())
    gate = ForestFirstJusticeGate()
    observations = []
    forest_risk_count = 0
    legacy_risk_count = 0

    for case in selected:
        forest = gate.evaluate(case.request)
        legacy = baseline(case.request)
        if forest.posture.value != "NORMAL":
            forest_risk_count += 1
        # The fixed legacy baseline has no risk-signal model by design.
        if False:
            legacy_risk_count += 1
        if case.expected_reason and case.expected_reason not in forest.reason_codes:
            forest_match = False
        else:
            forest_match = forest.release_state is case.expected_forest_release
        observations.append(
            ShadowObservation(
                case_id=case.case_id,
                description=case.description,
                forest_release=forest.release_state.value,
                legacy_release=legacy.value,
                expected_forest_release=case.expected_forest_release.value,
                expected_legacy_release=case.expected_legacy_release.value,
                forest_match=forest_match,
                legacy_match=legacy is case.expected_legacy_release,
                forest_reason_codes=forest.reason_codes,
            )
        )

    forest_matches = sum(item.forest_match for item in observations)
    legacy_matches = sum(item.legacy_match for item in observations)
    count = len(observations)
    return ShadowReport(
        schema="FOREST-FIRST-SYNTHETIC-SHADOW-V1",
        version="1.0.0",
        no_external_effect=True,
        case_count=count,
        forest_expected_match_count=forest_matches,
        legacy_expected_match_count=legacy_matches,
        forest_expected_match_rate=forest_matches / count if count else 0.0,
        legacy_expected_match_rate=legacy_matches / count if count else 0.0,
        forest_detected_risk_cases=forest_risk_count,
        legacy_detected_risk_cases=legacy_risk_count,
        observations=tuple(observations),
        limitations=(
            "Synthetic fixtures are designed around known failure classes and are not an estimate of real-world legal accuracy.",
            "The legacy baseline is a deliberately shallow fixed comparator, not a reconstruction of a named historical ChatGPT model.",
            "No live case evidence, legal filing, provider mutation or model inference is performed.",
            "A later blind/anonymised historical regression and independent legal review are required before operational superiority claims.",
        ),
    )


def _to_jsonable(report: ShadowReport) -> dict:
    payload = asdict(report)
    payload["observations"] = [asdict(item) for item in report.observations]
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Forest-First synthetic no-effect shadow benchmark.")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    report = run_shadow()
    payload = _to_jsonable(report)
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    return 0 if report.forest_expected_match_count == report.case_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
