from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import (
    ActionPacket,
    ForecastNode,
    LearningEvent,
    MatterPacket,
    RetrievalRoute,
    StrategyCandidate,
    StrategyRun,
)


class LexAutonomousStrategyEngine:
    """Deterministic A1-internal legal strategy runtime.

    The engine does not call providers directly. It compiles retrieval and action
    packets for authorised adapters/runtimes and keeps consequential external
    effects owner-reserved.
    """

    MODE = "READ_ONLY_AUTONOMOUS"

    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.runs_dir = self.workspace / "runs"
        self.runs_dir.mkdir(exist_ok=True)
        self.ledger_path = self.workspace / "learning-ledger.jsonl"
        self.circuit_path = self.workspace / "circuits.json"

    @staticmethod
    def _sha(payload: Any) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def _id(cls, prefix: str, payload: Any) -> str:
        return f"{prefix}-{cls._sha(payload)[:16]}"

    def _load_circuits(self) -> dict[str, Any]:
        if not self.circuit_path.exists():
            return {}
        return json.loads(self.circuit_path.read_text(encoding="utf-8"))

    def _save_circuits(self, circuits: dict[str, Any]) -> None:
        self.circuit_path.write_text(json.dumps(circuits, indent=2, sort_keys=True), encoding="utf-8")

    def _append_learning(self, event: LearningEvent) -> dict[str, Any]:
        previous_hash = "GENESIS"
        if self.ledger_path.exists():
            last = None
            with self.ledger_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        last = json.loads(line)
            if last:
                previous_hash = last["entry_hash"]
        body = {
            "timestamp_utc": dt.datetime.now(dt.UTC).isoformat(),
            "previous_hash": previous_hash,
            "event": asdict(event),
        }
        body["entry_hash"] = self._sha(body)
        with self.ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(body, sort_keys=True) + "\n")
        return body

    def _surface_score(self, source, unknown) -> float:
        authority = {"PRIMARY": 1.0, "PROVIDER": 0.95, "CANONICAL": 0.9, "DERIVATIVE": 0.5, "UNKNOWN": 0.35}.get(source.authority.upper(), 0.35)
        freshness = {"CURRENT": 1.0, "RECENT": 0.85, "HISTORICAL": 0.55, "UNKNOWN": 0.5}.get(source.freshness.upper(), 0.5)
        burden = max(0.0, 1.0 - min(1.0, (source.cost + source.latency) / 10.0))
        return round((0.35 * authority + 0.20 * freshness + 0.20 * burden + 0.15 * unknown.information_gain + 0.10 * unknown.decision_impact), 4)

    def resolve_access_before_ask(self, matter: MatterPacket) -> dict[str, Any]:
        routes: list[RetrievalRoute] = []
        exhausted: dict[str, bool] = {}
        owner_only_unknowns: list[str] = []

        for unknown in matter.unknowns:
            if unknown.owner_only:
                owner_only_unknowns.append(unknown.unknown_id)
                exhausted[unknown.unknown_id] = True
                continue
            candidate_sources = [s for s in matter.sources if s.available]
            if unknown.source_hints:
                hinted = [s for s in candidate_sources if any(h.lower() in s.name.lower() for h in unknown.source_hints)]
                if hinted:
                    candidate_sources = hinted + [s for s in candidate_sources if s not in hinted]
            for source in candidate_sources:
                score = self._surface_score(source, unknown)
                routes.append(
                    RetrievalRoute(
                        unknown_id=unknown.unknown_id,
                        surface=source.name,
                        query=unknown.question,
                        score=score,
                        reason=f"authority={source.authority}; freshness={source.freshness}; information_gain={unknown.information_gain}",
                        executable=source.available,
                    )
                )
            exhausted[unknown.unknown_id] = len(candidate_sources) == 0

        routes.sort(key=lambda r: (-r.score, r.unknown_id, r.surface))
        unresolved_non_owner = [u.unknown_id for u in matter.unknowns if not u.owner_only and not exhausted.get(u.unknown_id, False)]
        ask_owner_allowed = len(unresolved_non_owner) == 0
        return {
            "routes": [asdict(r) for r in routes],
            "exhausted": exhausted,
            "owner_only_unknowns": owner_only_unknowns,
            "unresolved_non_owner": unresolved_non_owner,
            "ask_owner_allowed": ask_owner_allowed,
            "rule": "ACCESS_BEFORE_ASK",
        }

    def build_case_twin(self, matter: MatterPacket) -> dict[str, Any]:
        unknown_rank = sorted(
            matter.unknowns,
            key=lambda u: (-(0.45 * u.information_gain + 0.35 * u.decision_impact + 0.20 * u.urgency), u.unknown_id),
        )
        return {
            "matter_id": matter.matter_id,
            "objective": matter.objective,
            "forum": matter.forum,
            "stage": matter.stage,
            "verified_or_asserted_facts": matter.facts,
            "disputed_facts": matter.disputed_facts,
            "legal_elements": matter.legal_elements,
            "remedies": matter.remedies,
            "cross_lane_risks": matter.cross_lane_risks,
            "opponent_capabilities": matter.opponent_capabilities,
            "unknown_frontier": [asdict(u) for u in unknown_rank],
            "top_information_unknown": asdict(unknown_rank[0]) if unknown_rank else None,
        }

    def forecast(self, matter: MatterPacket, twin: dict[str, Any]) -> list[ForecastNode]:
        top_unknown = twin.get("top_information_unknown")
        evidence_need = [top_unknown["question"]] if top_unknown else []
        opponent = ", ".join(matter.opponent_capabilities[:3]) or "procedural, evidentiary and merits response"
        cross_lane = ", ".join(matter.cross_lane_risks[:3]) or "waiver/forum/remedy contamination"
        return [
            ForecastNode(1, "OBJECTIVE", matter.objective, 1.0, 1.0),
            ForecastNode(2, "LEGAL_PROCEDURAL_GATE", f"Verify forum, cause, timing, burden and competent remedy for {matter.forum}", 0.9, 0.95),
            ForecastNode(3, "OPPONENT_MOST_LIKELY", f"Opponent uses existing factual/procedural explanation and attacks proof gaps: {opponent}", 0.6, 0.75, evidence_need),
            ForecastNode(4, "OPPONENT_STRONGEST_PIVOT", "Opponent reframes dispute at jurisdiction/classification stage or introduces primary records that cure current gaps", 0.3, 0.95, evidence_need),
            ForecastNode(5, "TRIBUNAL_TWIN", "Neutral/hostile decision-maker tests exact cause, burden, contemporaneous proof and prejudice rather than narrative intensity", 0.75, 0.9),
            ForecastNode(6, "FUTURE_EVIDENCE_DEPENDENCY", f"Secure decision-changing rebuttal evidence before opponent relies on the gap: {evidence_need or ['current primary record']}", 0.8, 0.9, evidence_need),
            ForecastNode(7, "COLLATERAL_EFFECT", f"Check cross-lane effects before outward commitment: {cross_lane}", 0.4, 0.85),
            ForecastNode(8, "COUNTERMOVE_FALLBACK", "Use source-bound clarification, narrower theory, alternate remedy or targeted recovery rather than overclaiming", 0.7, 0.8, fallback="Preserve current route and reserve alternate forum/remedy"),
            ForecastNode(9, "WORST_CASE_RECOVERY", "Adverse threshold ruling or new evidence defeats current theory; preserve record, isolate merits from procedure and retain review/alternate-route options", 0.2, 1.0, fallback="Shadow-review record + alternate cause/remedy assessment"),
            ForecastNode(10, "PIVOT_STOP_TRIGGER", "Pivot when new primary evidence materially changes cause/forum/burden or when information gain falls below cost/risk threshold", 1.0, 0.9),
        ]

    def form_routes(self, matter: MatterPacket, access: dict[str, Any], twin: dict[str, Any]) -> list[StrategyCandidate]:
        unknown = twin.get("top_information_unknown")
        has_open_unknown = unknown is not None
        candidates = [
            StrategyCandidate(
                route_id="LEX-ROUTE-RETRIEVE-FIRST",
                name="Retrieve and harden before commitment",
                description="Exhaust accessible source routes, close the highest-information unknown, then recompute strategy.",
                expected_value=0.92 if has_open_unknown else 0.70,
                reversibility=1.0,
                information_gain=0.95 if has_open_unknown else 0.35,
                owner_burden=0.05,
                legal_risk=0.08,
                proof_quality=0.95,
                reasons=["ACCESS_BEFORE_ASK", "high option value", "reduces surprise"],
            ),
            StrategyCandidate(
                route_id="LEX-ROUTE-NARROW-PREP",
                name="Prepare narrow source-bound position",
                description="Prepare an internal strategy/draft that uses only current verified propositions and explicitly reserves unresolved routes.",
                expected_value=0.82,
                reversibility=0.9,
                information_gain=0.55,
                owner_burden=0.08,
                legal_risk=0.15,
                proof_quality=0.9,
                reasons=["minimum sufficient action", "preserves remedies"],
            ),
            StrategyCandidate(
                route_id="LEX-ROUTE-DIRECT-EFFECT",
                name="Immediate consequential outward move",
                description="File/send/serve or otherwise commit the legal position now.",
                expected_value=0.45,
                reversibility=0.25,
                information_gain=0.25,
                owner_burden=0.2,
                legal_risk=0.7,
                proof_quality=0.5,
                external_effect=True,
                reasons=["may create speed advantage", "held unless proof and owner approval justify"],
            ),
        ]
        return sorted(candidates, key=self._route_score, reverse=True)

    @staticmethod
    def _route_score(route: StrategyCandidate) -> float:
        return (
            0.30 * route.expected_value
            + 0.20 * route.reversibility
            + 0.15 * route.information_gain
            + 0.20 * route.proof_quality
            - 0.10 * route.legal_risk
            - 0.05 * route.owner_burden
        )

    def future_evidence_queue(self, matter: MatterPacket) -> list[dict[str, Any]]:
        ranked = sorted(
            matter.unknowns,
            key=lambda u: (-(0.4 * u.information_gain + 0.4 * u.decision_impact + 0.2 * u.urgency), u.unknown_id),
        )
        return [
            {
                "priority": i,
                "unknown_id": u.unknown_id,
                "question": u.question,
                "source_hints": u.source_hints,
                "owner_only": u.owner_only,
                "evidence_ahead": True,
            }
            for i, u in enumerate(ranked, 1)
        ]

    def build_action_queue(self, matter: MatterPacket, selected: StrategyCandidate | None, access: dict[str, Any]) -> list[ActionPacket]:
        queue: list[ActionPacket] = []
        for route in access["routes"][:10]:
            digest = self._sha({"matter": matter.matter_id, "route": route})
            queue.append(
                ActionPacket(
                    action_id=self._id("ACT", digest),
                    action_type="RETRIEVE",
                    target=route["surface"],
                    state="READY_INTERNAL",
                    consequential=False,
                    owner_approval_required=False,
                    exact_target_digest=digest,
                    prerequisites=[],
                    notes=route["query"],
                )
            )
        if selected and selected.external_effect:
            digest = self._sha({"matter": matter.matter_id, "route": selected.route_id})
            queue.append(
                ActionPacket(
                    action_id=self._id("ACT", digest),
                    action_type="CONSEQUENTIAL_EXTERNAL",
                    target=matter.forum,
                    state="OWNER_APPROVAL_REQUIRED",
                    consequential=True,
                    owner_approval_required=True,
                    exact_target_digest=digest,
                    prerequisites=["LEX_EXTERNAL_ACTION_FIREWALL", "EXACT_TARGET_EXECUTION_LEASE", "PROVIDER_READBACK"],
                    notes="Prepared only; no execution authority granted by strategy selection.",
                )
            )
        return queue

    def ao_cra_builds(self, matter: MatterPacket, access: dict[str, Any]) -> list[dict[str, Any]]:
        builds = []
        for unknown_id, exhausted in access["exhausted"].items():
            if not exhausted:
                continue
            unknown = next((u for u in matter.unknowns if u.unknown_id == unknown_id), None)
            if unknown is None or unknown.owner_only:
                continue
            builds.append(
                {
                    "build_id": self._id("BUILD-LEX", {"matter": matter.matter_id, "unknown": unknown_id}),
                    "gap_statement": f"No currently available retrieval surface for: {unknown.question}",
                    "desired_capability": "Autonomous authorised retrieval route",
                    "classification": "UNRESOLVED_ENGINEERING_BUILD",
                    "owning_engine": "LEX_AUTONOMOUS_STRATEGY_ENGINE",
                    "interim_workaround": "Use alternate source/proposition proof where available; owner ask remains last resort",
                    "lifecycle_state": "DETECTED",
                    "next_executable_action": "Run Formation route discovery against current Federation capabilities",
                    "recheck_trigger": "connector/provider/corpus capability change",
                    "closure_criteria": "executable route + test + readback",
                }
            )
        return builds

    def run(self, raw: dict[str, Any] | MatterPacket) -> StrategyRun:
        matter = raw if isinstance(raw, MatterPacket) else MatterPacket.from_dict(raw)
        access = self.resolve_access_before_ask(matter)
        twin = self.build_case_twin(matter)
        forecast = self.forecast(matter, twin)
        tournament = self.form_routes(matter, access, twin)
        selected = next((r for r in tournament if not r.external_effect), None)
        evidence_queue = self.future_evidence_queue(matter)
        actions = self.build_action_queue(matter, selected, access)
        builds = self.ao_cra_builds(matter, access)

        event = LearningEvent(
            event_type="SUCCESS",
            fingerprint=self._id("FP", {"matter": matter.matter_id, "objective": matter.objective}),
            summary="Autonomous internal strategy cycle compiled without external effect.",
            evidence_refs=[matter.matter_id],
            measurable_delta={"unknowns": len(matter.unknowns), "retrieval_routes": len(access["routes"]), "forecast_nodes": len(forecast)},
        )
        learning_entry = self._append_learning(event)

        run = StrategyRun(
            run_id=self._id("LEXRUN", {"matter": matter.matter_id, "time": dt.datetime.now(dt.UTC).isoformat()}),
            matter_id=matter.matter_id,
            timestamp_utc=dt.datetime.now(dt.UTC).isoformat(),
            mode=self.MODE,
            access_resolution=access,
            ask_owner_allowed=bool(access["ask_owner_allowed"]),
            case_twin=twin,
            forecast_tree=forecast,
            route_tournament=tournament,
            selected_strategy=selected,
            future_evidence_queue=evidence_queue,
            action_queue=actions,
            learning_events=[event],
            ao_cra_builds=builds,
            truth_boundary={
                "authority_ceiling": "A1_INTERNAL",
                "external_effect": False,
                "provider_actions_executed": False,
                "consequential_actions_owner_reserved": True,
                "ask_owner_allowed_only_after_access_exhaustion": True,
                "forecast_is_probability_model_not_fact": True,
                "learning_entry_hash": learning_entry["entry_hash"],
            },
        )
        output = self.runs_dir / f"{run.run_id}.json"
        output.write_text(json.dumps(run.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return run
