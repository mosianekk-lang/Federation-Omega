from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Any, Iterable

MATURITY_STATES = {
    "SOURCE_PRESENT",
    "TESTED",
    "RUNTIME_VERIFIED",
    "PROVIDER_VERIFIED",
    "BEHAVIOUR_VERIFIED",
    "OWNER_VALUE_PROVEN",
}


def _digest(obj: Any) -> str:
    return sha256(json.dumps(obj, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def _iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True)
class GateFinding:
    gate: str
    state: str
    severity: str
    message: str
    refs: tuple[str, ...] = ()


class LexHardeningSupportV2:
    """Additive structural assurance for LEX.

    This module intentionally does not reimplement LEX-OMEGA authority semantics,
    TruthGrid evidence finality, JFRIE release integrity, CASEFORGE falsification,
    LASE strategy selection, or HORIZON foresight. It adds missing cross-engine
    structural checks and composes their explicit proof states.
    """

    VERSION = "2.0.0"
    MODE = "READ_ONLY_COMPOSITION"

    def capability_graph(self, capabilities: Iterable[dict[str, Any]]) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        duplicates: set[str] = set()
        invalid_maturity: set[str] = set()
        for raw in capabilities:
            cid = str(raw.get("capability_id", "")).strip()
            if not cid:
                continue
            if cid in seen:
                duplicates.add(cid)
            seen.add(cid)
            maturity = str(raw.get("maturity", "SOURCE_PRESENT"))
            if maturity not in MATURITY_STATES:
                invalid_maturity.add(cid)
            rows.append({
                "capability_id": cid,
                "name": raw.get("name", cid),
                "owner": raw.get("owner", "UNKNOWN"),
                "maturity": maturity,
                "source_proof": list(raw.get("source_proof", [])),
                "test_proof": list(raw.get("test_proof", [])),
                "runtime_proof": list(raw.get("runtime_proof", [])),
                "provider_proof": list(raw.get("provider_proof", [])),
                "behaviour_proof": list(raw.get("behaviour_proof", [])),
                "owner_value_proof": list(raw.get("owner_value_proof", [])),
                "fallback_routes": list(raw.get("fallback_routes", [])),
                "limitations": list(raw.get("limitations", [])),
            })
        return {
            "rows": rows,
            "duplicate_ids": sorted(duplicates),
            "invalid_maturity": sorted(invalid_maturity),
            "digest": _digest(rows),
        }

    def chronology_gate(self, events: Iterable[dict[str, Any]]) -> list[GateFinding]:
        findings: list[GateFinding] = []
        rows = list(events)
        by_id = {str(x.get("event_id")): x for x in rows if x.get("event_id")}
        for event in rows:
            eid = str(event.get("event_id", "UNKNOWN"))
            source_time = _iso(event.get("source_native_time"))
            derivative_time = _iso(event.get("derivative_time"))
            if source_time and derivative_time and derivative_time < source_time:
                findings.append(GateFinding("TEMPORAL_DERIVATIVE", "HOLD", "P0", f"{eid}: derivative timestamp predates source-native timestamp", (eid,)))
            decision_time = _iso(event.get("decision_time"))
            evidence_time = _iso(event.get("evidence_available_time"))
            if decision_time and evidence_time and evidence_time > decision_time and event.get("claimed_considered", False):
                findings.append(GateFinding("DECISION_EVIDENCE_SEQUENCE", "HOLD", "P0", f"{eid}: evidence claimed considered but became available after decision", (eid,)))
            predecessor = event.get("must_follow_event_id")
            if predecessor and predecessor in by_id:
                predecessor_time = _iso(by_id[predecessor].get("event_time"))
                event_time = _iso(event.get("event_time"))
                if predecessor_time and event_time and event_time < predecessor_time:
                    findings.append(GateFinding("EVENT_SEQUENCE", "HOLD", "P0", f"{eid}: occurs before required predecessor {predecessor}", (eid, str(predecessor))))
        return findings

    def decision_record_gate(self, decisions: Iterable[dict[str, Any]]) -> list[GateFinding]:
        findings: list[GateFinding] = []
        required = (
            "decision_id", "decision_maker", "authority", "decision_date",
            "evidence_considered", "findings", "alternatives_considered",
            "prejudice_weighed", "reasons", "review_path",
        )
        for decision in decisions:
            did = str(decision.get("decision_id", "UNKNOWN"))
            missing = [key for key in required if decision.get(key) in (None, "", [])]
            if missing:
                findings.append(GateFinding("DECISION_RECORD", "HOLD", "P1", f"{did}: decision architecture incomplete: {', '.join(missing)}", (did,)))
        return findings

    def remedy_gate(self, remedies: Iterable[dict[str, Any]]) -> list[GateFinding]:
        findings: list[GateFinding] = []
        for remedy in remedies:
            rid = str(remedy.get("remedy_id", "UNKNOWN"))
            missing = [key for key in ("forum", "prerequisites", "evidence_required", "timing", "enforcement_path") if remedy.get(key) in (None, "", [])]
            if missing:
                findings.append(GateFinding("REMEDY_STACK", "HOLD", "P1", f"{rid}: missing {', '.join(missing)}", (rid,)))
        return findings

    def opponent_twin(self, matter: dict[str, Any]) -> dict[str, Any]:
        required = ("opponent_strongest_factual", "opponent_strongest_legal", "opponent_strongest_procedural")
        return {
            "factual": list(matter.get("opponent_strongest_factual", [])),
            "legal": list(matter.get("opponent_strongest_legal", [])),
            "procedural": list(matter.get("opponent_strongest_procedural", [])),
            "likely_next": list(matter.get("opponent_likely_next", [])),
            "surprise_high_impact": list(matter.get("opponent_surprise", [])),
            "complete": all(bool(matter.get(key)) for key in required),
        }

    def tribunal_twins(self, matter: dict[str, Any]) -> dict[str, Any]:
        base = {
            "lose_reasons": list(matter.get("reasons_we_could_lose", [])),
            "weak_authorities": list(matter.get("weak_authorities", [])),
            "missing_evidentiary_links": list(matter.get("missing_evidentiary_links", [])),
        }
        return {
            "neutral": {**base, "lens": "balanced merits + procedure"},
            "hostile": {**base, "lens": "strongest lawful adverse interpretation"},
            "strict_procedural": {**base, "lens": "forum + timing + pleading + record"},
            "complete": bool(base["lose_reasons"]) and bool(matter.get("do_not_concede")),
        }

    def information_gain_queue(self, unknowns: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for unknown in unknowns:
            score = (
                0.22 * float(unknown.get("legal_importance", 0.5))
                + 0.18 * float(unknown.get("case_theory_impact", 0.5))
                + 0.15 * float(unknown.get("opponent_defeat_value", 0.5))
                + 0.13 * float(unknown.get("procedural_urgency", 0.5))
                + 0.10 * float(unknown.get("fragility", 0.5))
                + 0.08 * float(unknown.get("accessibility", 0.5))
                + 0.08 * (1.0 - float(unknown.get("cost", 0.5)))
                + 0.03 * (1.0 - float(unknown.get("owner_effort", 0.5)))
                + 0.03 * float(unknown.get("downstream_leverage", 0.5))
            )
            row = dict(unknown)
            row["information_gain_score"] = round(score, 6)
            rows.append(row)
        rows.sort(key=lambda row: (-row["information_gain_score"], str(row.get("unknown_id", ""))))
        return rows

    def failure_to_operational_win(self, failure: dict[str, Any]) -> dict[str, Any]:
        required = (
            "failed_expectation", "observed_result", "root_cause_hypothesis",
            "counter_hypothesis", "falsification_test", "repair", "failure_first_test",
            "healthy_path_test", "canary", "readback", "regression", "rollback_test",
            "owner_value", "portable_lesson",
        )
        missing = [key for key in required if not failure.get(key)]
        return {
            "state": "REPAIR_CYCLE_OPEN" if missing else "READY_FOR_BEHAVIOURAL_VALIDATION",
            "missing": missing,
            "operational_win_verified": False,
            "digest": _digest(failure),
        }


class LexMatterReleaseCourtV2:
    """Cross-engine matter-release court with no external effects."""

    VERSION = "2.0.0"
    MODE = "READ_ONLY_COMPOSITION"
    LEX_OK = {"PASS", "PASS_WITH_LIMITATIONS"}
    JFRIE_OK = {"PASS", "PASS_WITH_LIMITATIONS"}
    TRUTHGRID_OK = {"READY", "CONDITIONAL"}
    CASEFORGE_OK = {"PASS", "NOT_REQUIRED"}

    def __init__(self) -> None:
        self.support = LexHardeningSupportV2()

    def upstream_gate(self, upstream: dict[str, Any]) -> list[GateFinding]:
        findings: list[GateFinding] = []
        if upstream.get("lex_omega_state") not in self.LEX_OK:
            findings.append(GateFinding("LEX_OMEGA", "HOLD", "P0", "LEX-OMEGA legal convergence is not passing"))
        if upstream.get("jfrie_state") not in self.JFRIE_OK:
            findings.append(GateFinding("JFRIE", "HOLD", "P0", "JFRIE release integrity is not passing"))
        if upstream.get("truthgrid_state") not in self.TRUTHGRID_OK:
            findings.append(GateFinding("TRUTHGRID", "HOLD", "P0", "TruthGrid decision readiness is not READY/CONDITIONAL"))
        if upstream.get("caseforge_state", "NOT_REQUIRED") not in self.CASEFORGE_OK:
            findings.append(GateFinding("CASEFORGE", "HOLD", "P1", "CASEFORGE falsification/benchmark state is not passing"))
        if upstream.get("authority_semantic_verified") is not True:
            findings.append(GateFinding("AUTHSEM_UPSTREAM", "HOLD", "P0", "Existing LEX AUTHSEM proof not bound to this matter/proposition set"))
        if upstream.get("current_law_verified") is not True:
            findings.append(GateFinding("CURRENT_LAW", "HOLD", "P0", "Current-law verification not bound to consequential propositions"))
        return findings

    def lase_gate(self, lase_run: dict[str, Any]) -> list[GateFinding]:
        findings: list[GateFinding] = []
        truth_boundary = dict(lase_run.get("truth_boundary", {}))
        if truth_boundary.get("external_effect") is not False:
            findings.append(GateFinding("LASE_EFFECT", "HOLD", "P0", "LASE run is not proven no-effect"))
        if truth_boundary.get("consequential_actions_owner_reserved") is not True:
            findings.append(GateFinding("OWNER_RESERVATION", "HOLD", "P0", "Consequential-action owner reservation missing"))
        if not lase_run.get("forecast_tree"):
            findings.append(GateFinding("HORIZON_INPUT", "HOLD", "P1", "No forecast tree bound from LASE/HORIZON"))
        if not lase_run.get("selected_strategy"):
            findings.append(GateFinding("STRATEGY_SELECTION", "HOLD", "P1", "No bounded strategy selection available"))
        return findings

    def adjudicate(self, packet: dict[str, Any]) -> dict[str, Any]:
        matter = dict(packet.get("matter", {}))
        upstream = dict(packet.get("upstream", {}))
        lase_run = dict(packet.get("lase_run", {}))
        findings = self.upstream_gate(upstream) + self.lase_gate(lase_run)
        findings += self.support.chronology_gate(matter.get("events", []))
        findings += self.support.decision_record_gate(matter.get("decisions", []))
        findings += self.support.remedy_gate(matter.get("remedies", []))

        opponent = self.support.opponent_twin(matter)
        tribunal = self.support.tribunal_twins(matter)
        if not opponent["complete"]:
            findings.append(GateFinding("OPPONENT_TWIN", "HOLD", "P1", "Strongest opponent case incomplete"))
        if not tribunal["complete"]:
            findings.append(GateFinding("TRIBUNAL_TWIN", "HOLD", "P1", "Neutral/hostile/strict tribunal stress test incomplete"))

        p0 = [finding for finding in findings if finding.severity == "P0"]
        p1 = [finding for finding in findings if finding.severity == "P1"]
        state = "INTERNAL_WORK_PRODUCT_ELIGIBLE" if not p0 and not p1 else "HOLD"
        return {
            "version": self.VERSION,
            "mode": self.MODE,
            "matter_id": matter.get("matter_id", "UNKNOWN"),
            "state": state,
            "p0_count": len(p0),
            "p1_count": len(p1),
            "findings": [asdict(finding) for finding in findings],
            "opponent_twin": opponent,
            "tribunal_twins": tribunal,
            "information_gain_queue": self.support.information_gain_queue(matter.get("unknowns", [])),
            "upstream_reuse": {
                "legal_authority": "LEX_OMEGA_REUSED",
                "evidence_finality": "TRUTHGRID_REUSED",
                "release_integrity": "JFRIE_REUSED",
                "falsification": "CASEFORGE_REUSED",
                "strategy": "LASE_HORIZON_REUSED",
            },
            "external_effect": False,
            "consequential_actions_owner_reserved": True,
            "digest": _digest({"packet": packet, "findings": [asdict(finding) for finding in findings]}),
        }
