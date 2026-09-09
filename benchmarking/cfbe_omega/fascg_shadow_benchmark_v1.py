from __future__ import annotations

"""Effect-free hosted-shadow and Composite Frontier measurement contract for FASCG.

This module does not simulate market superiority. It provides deterministic shadow
scenarios, proof-bound measurement records, and a gate that refuses to feed
synthetic/local measurements into the 10x Composite Frontier court.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from typing import Any, Iterable, Mapping, Sequence

from benchmarking.cfbe_omega.autopilot_sentinel_cognitive_genome_v1 import (
    ActiveSensingPlanner,
    AutonomyContext,
    CausalInterventionCourt,
    HomeostasisAction,
    InterventionCandidate,
    MissionHomeostasisController,
    MissionHomeostasisState,
    SentinelCellEcology,
    SensingCandidate,
)
from benchmarking.cfbe_omega.autopilot_sentinel_frontier_court_v1 import ResilienceRun

SCHEMA = "FASCG-HOSTED-SHADOW-BENCHMARK-V1"
EXTERNAL_EFFECTS = False
TEN_X_VERIFIED = False


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _hash(value: Any) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


def _unit(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label}_NOT_FINITE")
    value = float(value)
    if not 0 <= value <= 1:
        raise ValueError(f"{label}_OUT_OF_RANGE")
    return value


@dataclass(frozen=True, slots=True)
class ShadowScenario:
    scenario_id: str
    family: str
    state: MissionHomeostasisState
    signal_texts: tuple[str, ...]
    sensing_candidates: tuple[SensingCandidate, ...]
    intervention_candidates: tuple[InterventionCandidate, ...]
    autonomy_context: AutonomyContext
    expected_homeostasis: HomeostasisAction
    required_cell_domains: tuple[str, ...] = ()

    def validate(self) -> "ShadowScenario":
        if not self.scenario_id.strip() or not self.family.strip() or not self.signal_texts:
            raise ValueError("FASCG_SHADOW_SCENARIO_IDENTITY_REQUIRED")
        self.state.validate(); self.autonomy_context.validate()
        for item in self.sensing_candidates: item.validate()
        for item in self.intervention_candidates: item.validate()
        return self


@dataclass(frozen=True, slots=True)
class ShadowScenarioReceipt:
    scenario_id: str
    family: str
    homeostasis_action: str
    cell_domains: tuple[str, ...]
    best_sensing_id: str | None
    intervention_id: str | None
    autonomy_level: str
    external_effect_authorized: bool
    passed: bool
    blockers: tuple[str, ...]
    receipt_sha256: str


class HostedShadowHarness:
    """Runs deterministic, no-effect FASCG control scenarios."""

    def __init__(self) -> None:
        self.home = MissionHomeostasisController()
        self.sensing = ActiveSensingPlanner()
        self.intervention = CausalInterventionCourt()
        from benchmarking.cfbe_omega.autopilot_sentinel_cognitive_genome_v1 import RiskAdaptiveAutonomyGate
        self.autonomy = RiskAdaptiveAutonomyGate()

    def run(self, scenario: ShadowScenario) -> ShadowScenarioReceipt:
        scenario.validate()
        home = self.home.decide(scenario.state)
        cells = SentinelCellEcology.form(scenario.signal_texts, evidence_refs=(f"shadow:{scenario.scenario_id}",))
        best = self.sensing.best(scenario.sensing_candidates) if scenario.sensing_candidates else None
        intervention = self.intervention.plan(scenario.intervention_candidates) if scenario.intervention_candidates else None
        autonomy = self.autonomy.decide(scenario.autonomy_context)
        domains = tuple(sorted(c.domain.value for c in cells.cells))
        blockers: list[str] = []
        if home.action is not scenario.expected_homeostasis:
            blockers.append("HOMEOSTASIS_MISMATCH")
        for required in scenario.required_cell_domains:
            if required not in domains:
                blockers.append(f"MISSING_CELL:{required}")
        if autonomy.external_effect_authorized:
            blockers.append("AUTONOMY_EFFECT_ESCAPE")
        if cells and any(c.external_effect for c in cells.cells):
            blockers.append("SENTINEL_CELL_EFFECT_ESCAPE")
        if intervention and intervention.external_effect_authorized:
            blockers.append("INTERVENTION_EFFECT_ESCAPE")
        body = {
            "schema": SCHEMA,
            "scenario_id": scenario.scenario_id,
            "family": scenario.family,
            "homeostasis_action": home.action.value,
            "cell_domains": domains,
            "best_sensing_id": best.sensing_id if best else None,
            "intervention_id": intervention.selected_id if intervention else None,
            "autonomy_level": autonomy.level.value,
            "external_effect_authorized": False,
            "blockers": sorted(set(blockers)),
        }
        return ShadowScenarioReceipt(
            scenario.scenario_id,
            scenario.family,
            body["homeostasis_action"],
            domains,
            body["best_sensing_id"],
            body["intervention_id"],
            body["autonomy_level"],
            False,
            not blockers,
            tuple(body["blockers"]),
            _hash(body),
        )

    def run_suite(self, scenarios: Sequence[ShadowScenario]) -> Mapping[str, Any]:
        if not scenarios:
            raise ValueError("FASCG_SHADOW_SUITE_REQUIRED")
        receipts = tuple(self.run(s) for s in scenarios)
        body = {
            "schema": SCHEMA,
            "scenario_count": len(receipts),
            "passed": sum(r.passed for r in receipts),
            "failed": sum(not r.passed for r in receipts),
            "external_effects": False,
            "ten_x_verified": False,
            "receipts": [asdict(r) for r in receipts],
        }
        return {**body, "sha256": _hash(body)}


MEASUREMENT_CLASSES = frozenset({"REAL_HOSTED_SHADOW", "REAL_PROVIDER_CANARY", "REAL_OPERATIONAL"})


@dataclass(frozen=True, slots=True)
class MeasuredResilienceRun:
    run_id: str
    task_family: str
    measurement_class: str
    source_sha: str
    environment_fingerprint: str
    proof_refs: tuple[str, ...]
    metrics: ResilienceRun
    synthetic: bool = False

    def validate(self) -> "MeasuredResilienceRun":
        if not self.run_id.strip() or not self.task_family.strip() or not self.source_sha.strip():
            raise ValueError("FASCG_MEASUREMENT_IDENTITY_REQUIRED")
        if self.measurement_class not in MEASUREMENT_CLASSES:
            raise ValueError("FASCG_MEASUREMENT_CLASS_NOT_ELIGIBLE")
        if self.synthetic:
            raise ValueError("FASCG_SYNTHETIC_MEASUREMENT_INELIGIBLE")
        if not self.environment_fingerprint.strip() or not self.proof_refs:
            raise ValueError("FASCG_MEASUREMENT_PROOF_REQUIRED")
        self.metrics.validate()
        return self

    @property
    def fingerprint(self) -> str:
        self.validate()
        return _hash({
            "run_id": self.run_id,
            "task_family": self.task_family,
            "measurement_class": self.measurement_class,
            "source_sha": self.source_sha,
            "environment_fingerprint": self.environment_fingerprint,
            "proof_refs": sorted(self.proof_refs),
            "ary": self.metrics.ary(),
        })


def eligible_10x_runs(rows: Iterable[MeasuredResilienceRun]) -> tuple[ResilienceRun, ...]:
    validated = tuple(row.validate() for row in rows)
    return tuple(row.metrics for row in validated)


def default_shadow_scenarios() -> tuple[ShadowScenario, ...]:
    """Representative control-plane scenarios only; never market-performance evidence."""
    s = []
    # 1: healthy continuation
    s.append(ShadowScenario(
        "SHADOW-HEALTHY-001", "mission-health",
        MissionHomeostasisState(.96,.98,.97,.94,.12,.15,.12,.10,.10,.08,.72,.90),
        ("healthy service availability evidence owner value",),
        (SensingCandidate("sense-trace","h1",.12,.02,.02,.01,.01),), (),
        AutonomyContext("NO_EFFECT",True,True,.94,.12,.10,.08,True),
        HomeostasisAction.CONTINUE,
        ("EVIDENCE","OWNER_VALUE"),
    ))
    # 2: evidence gap
    s.append(ShadowScenario(
        "SHADOW-EVIDENCE-002", "evidence-gap",
        MissionHomeostasisState(.90,.96,.94,.35,.78,.20,.20,.10,.25,.15,.55,.72),
        ("proof evidence contradiction receipt missing",),
        (
            SensingCandidate("sense-provider-readback","h2",.85,.03,.04,.01,.02),
            SensingCandidate("sense-more-logs","h2",.30,.03,.08,.02,.03),
        ), (),
        AutonomyContext("READ",True,True,.35,.78,.25,.15,True),
        HomeostasisAction.ACTIVE_SENSE,
        ("EVIDENCE",),
    ))
    # 3: high blast radius -> simulate
    s.append(ShadowScenario(
        "SHADOW-BLAST-003", "blast-radius",
        MissionHomeostasisState(.88,.96,.92,.82,.34,.25,.28,.12,.82,.20,.48,.76),
        ("cloud gateway network route change latency",),
        (SensingCandidate("sense-topology","h3",.66,.03,.04,.01,.02),),
        (
            InterventionCandidate("sim-reroute","gateway",.70,.10,.05,.18,True,True,("shadow:h3",)),
            InterventionCandidate("sim-restart","gateway",.45,.03,.03,.55,True,True,("shadow:h3",)),
        ),
        AutonomyContext("A2",True,False,.82,.34,.82,.20,True),
        HomeostasisAction.SIMULATE_INTERVENTION,
        ("CLOUD_NETWORK","RELIABILITY"),
    ))
    # 4: adversarial security -> quarantine
    s.append(ShadowScenario(
        "SHADOW-SECURITY-004", "agent-security",
        MissionHomeostasisState(.82,.91,.90,.78,.40,.18,.20,.16,.45,.92,.40,.60),
        ("agent prompt injection compromise token identity exfiltration",),
        (SensingCandidate("sense-agent-trace","h4",.80,.04,.04,.02,.08),), (),
        AutonomyContext("A1",True,True,.78,.40,.45,.92,True),
        HomeostasisAction.QUARANTINE,
        ("AGENT_RUNTIME","SECURITY","IDENTITY","DATA_PRIVACY"),
    ))
    # 5: repeated failures -> rollback
    s.append(ShadowScenario(
        "SHADOW-ROLLBACK-005", "recovery",
        MissionHomeostasisState(.75,.94,.88,.80,.35,.45,.48,.15,.40,.20,.30,.62,repeated_failures=3),
        ("error failure rollback reliability route",),
        (SensingCandidate("sense-failure-receipt","h5",.55,.02,.03,.01,.01),), (),
        AutonomyContext("A1",True,True,.80,.35,.40,.20,True),
        HomeostasisAction.ROLLBACK,
        ("RELIABILITY",),
    ))
    # 6: owner-only decision
    s.append(ShadowScenario(
        "SHADOW-OWNER-006", "owner-boundary",
        MissionHomeostasisState(.95,.97,.96,.90,.20,.10,.10,.10,.10,.10,.60,.90,owner_only_decision=True),
        ("owner approval settlement publication authority",),
        (SensingCandidate("sense-owner-context","h6",.20,.01,.01,.01,.01),), (),
        AutonomyContext("A3",False,False,.90,.20,.10,.10,True,owner_approval_required=True),
        HomeostasisAction.HOLD_OWNER,
        ("OWNER_VALUE",),
    ))
    # 7: safety floor degrade autonomy
    s.append(ShadowScenario(
        "SHADOW-SAFETY-007", "safety-floor",
        MissionHomeostasisState(.84,.78,.93,.84,.28,.20,.20,.12,.20,.18,.50,.75),
        ("safety evidence model agent runtime",),
        (SensingCandidate("sense-safety","h7",.70,.03,.03,.01,.03),), (),
        AutonomyContext("A1",True,True,.84,.28,.20,.18,True),
        HomeostasisAction.DEGRADE_AUTONOMY,
        ("AGENT_RUNTIME","EVIDENCE"),
    ))
    # 8: low progress/high pressure -> replan
    s.append(ShadowScenario(
        "SHADOW-REPLAN-008", "resource-pressure",
        MissionHomeostasisState(.90,.96,.94,.80,.35,.82,.78,.20,.22,.20,.12,.72),
        ("cost compute latency performance budget",),
        (SensingCandidate("sense-cost-trace","h8",.50,.02,.02,.01,.01),), (),
        AutonomyContext("NO_EFFECT",True,True,.80,.35,.22,.20,True),
        HomeostasisAction.REPLAN,
        ("COST_PERFORMANCE",),
    ))
    return tuple(s)


__all__ = [
    "SCHEMA", "EXTERNAL_EFFECTS", "TEN_X_VERIFIED", "ShadowScenario", "ShadowScenarioReceipt",
    "HostedShadowHarness", "MeasuredResilienceRun", "eligible_10x_runs", "default_shadow_scenarios",
]
