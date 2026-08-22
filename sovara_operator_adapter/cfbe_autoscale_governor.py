from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class AutoscalePolicy:
    policy_id: str
    trigger_class: str
    direction: str
    action: str


POLICIES: tuple[AutoscalePolicy, ...] = (
    AutoscalePolicy("AS-001", "REFERENCE_SET", "UP", "ADMIT_CHALLENGER_AND_REFRESH"),
    AutoscalePolicy("AS-002", "REFERENCE_SET", "UP", "PROMOTE_STRATEGIC_COUNCIL"),
    AutoscalePolicy("AS-003", "REFERENCE_SET", "DOWN", "DEMOTE_TO_CHALLENGER_OR_WATCH"),
    AutoscalePolicy("AS-004", "SOURCE_DEPTH", "UP", "DEEPEN_OFFICIAL_SOURCE_DISCOVERY"),
    AutoscalePolicy("AS-005", "BENCHMARK_MODEL", "UP", "EXTEND_BOUNDED_BENCHMARK_MODEL"),
    AutoscalePolicy("AS-006", "TEST_EVAL", "UP", "EXPAND_TEST_EVAL_COVERAGE"),
    AutoscalePolicy("AS-007", "EXECUTION_MESH", "UP", "FORM_ADAPTER_CANDIDATE"),
    AutoscalePolicy("AS-008", "CADENCE_CAPACITY", "UP", "INCREASE_BOUNDED_CADENCE"),
    AutoscalePolicy("AS-009", "CADENCE_CAPACITY", "DOWN", "REDUCE_QUIET_SOURCE_CADENCE"),
    AutoscalePolicy("AS-010", "ARCHITECTURE_EVD", "HOLD", "HOLD_ARCHITECTURE_EXPANSION"),
    AutoscalePolicy("AS-011", "FAILOVER", "LATERAL", "REROUTE_EQUIVALENT_ADAPTER"),
    AutoscalePolicy("AS-012", "HIGH_SCALE_OPPORTUNITY", "UP_LATERAL", "EXPERIMENT_THEN_FANOUT"),
    AutoscalePolicy("AS-013", "COST_PERFORMANCE", "DOWN_LATERAL", "SHIFT_TO_CHEAPER_EQUIVALENT"),
    AutoscalePolicy("AS-014", "SELF_IMPROVEMENT", "UP", "FORM_SMALLEST_MISSING_CAPABILITY"),
)

_POLICY_INDEX = {policy.policy_id: policy for policy in POLICIES}
_ALLOWED_AUTONOMOUS_COSTS = {"ZERO", "INCLUDED"}
_HARD_EVD_HOLDS = {
    "HOLD_ARCHITECTURE_EXPANSION",
    "HOLD_CRITICAL_REGRESSION",
    "HOLD_STALE_PROOF",
    "HOLD_UNKNOWN_MATERIAL_COST",
}


@dataclass(frozen=True)
class AutoscaleSignal:
    signal_id: str
    policy_id: str
    mission_value: float
    information_gain: float
    evidence_current: bool = True
    reversible: bool = True
    cost_class: str = "INCLUDED"
    existing_authority: bool = True
    independent_readback_available: bool = True
    consequential: bool = False
    iam_or_secret_change: bool = False
    destructive_change: bool = False
    external_effect: bool = False
    evd_verdict: str = "VALUE_DENSITY_STABLE_OR_IMPROVING"
    permanent_anchor_target: bool = False

    def validate(self) -> None:
        if not self.signal_id:
            raise ValueError("signal_id is required")
        if self.policy_id not in _POLICY_INDEX:
            raise ValueError(f"unknown policy_id: {self.policy_id}")
        for name, value in (
            ("mission_value", self.mission_value),
            ("information_gain", self.information_gain),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.cost_class not in {"ZERO", "INCLUDED", "UNKNOWN", "PAID"}:
            raise ValueError("cost_class must be ZERO, INCLUDED, UNKNOWN, or PAID")


@dataclass(frozen=True)
class AutoscaleDecision:
    signal_id: str
    policy_id: str
    direction: str
    action: str
    status: str
    reason: str
    autonomous: bool
    owner_trigger_required: bool
    continue_unaffected_lanes: bool
    self_certifies_improvement: bool = False
    authorizes_destructive_retirement: bool = False
    authorizes_authority_expansion: bool = False


def decide_autoscale(signal: AutoscaleSignal) -> AutoscaleDecision:
    """Return a deterministic CFBE autoscale decision without inheriting authority.

    This governor can right-size CFBE's internal benchmark capability within an
    already-authorised, reversible, zero/included-cost A0/A1 envelope. It does
    not execute provider mutations and cannot certify its own improvement.
    """
    signal.validate()
    policy = _POLICY_INDEX[signal.policy_id]

    if not signal.evidence_current:
        return _hold(signal, policy, "HOLD_STALE_PROOF", "source or control evidence is stale")

    if signal.evd_verdict in _HARD_EVD_HOLDS:
        return _hold(signal, policy, signal.evd_verdict, "engineering value-density gate is holding expansion")

    if signal.permanent_anchor_target and policy.policy_id == "AS-003":
        return _hold(signal, policy, "HOLD_PERMANENT_ANCHOR", "permanent benchmark anchors cannot be auto-demoted")

    if signal.consequential or signal.iam_or_secret_change or signal.destructive_change or signal.external_effect:
        return _owner_gate(signal, policy, "consequential, authority-changing, destructive, secret-related, or external effect")

    if signal.cost_class not in _ALLOWED_AUTONOMOUS_COSTS:
        return _owner_gate(signal, policy, "incremental cost is paid or unknown")

    if not signal.existing_authority:
        return _owner_gate(signal, policy, "required authority is not already present")

    if not signal.reversible:
        return _owner_gate(signal, policy, "autonomous autoscale requires reversibility")

    if not signal.independent_readback_available:
        return _hold(signal, policy, "HOLD_PROOF_GATE", "independent readback is unavailable")

    if signal.mission_value < 0.25 and signal.information_gain < 0.25:
        return AutoscaleDecision(
            signal_id=signal.signal_id,
            policy_id=policy.policy_id,
            direction="NONE",
            action="NO_SCALE",
            status="NO_SCALE_LOW_VALUE",
            reason="mission value and information gain are both below the autoscale floor",
            autonomous=True,
            owner_trigger_required=False,
            continue_unaffected_lanes=True,
        )

    if policy.policy_id == "AS-010":
        return _hold(signal, policy, "HOLD_ARCHITECTURE_EXPANSION", "explicit EVD autoscale policy requests an architecture hold")

    return AutoscaleDecision(
        signal_id=signal.signal_id,
        policy_id=policy.policy_id,
        direction=policy.direction,
        action=policy.action,
        status="AUTONOMOUS_ADMISSIBLE",
        reason="evidence, authority, reversibility, cost, proof, and EVD gates are satisfied",
        autonomous=True,
        owner_trigger_required=False,
        continue_unaffected_lanes=True,
    )


def rank_admissible_signals(signals: Iterable[AutoscaleSignal]) -> list[AutoscaleDecision]:
    """Rank currently admissible autoscale actions by value and information gain.

    Gated/held signals are omitted from execution ranking but remain available to
    callers through direct `decide_autoscale` evaluation and durable ledgers.
    """
    prepared: list[tuple[float, str, AutoscaleDecision]] = []
    for signal in signals:
        decision = decide_autoscale(signal)
        if decision.status != "AUTONOMOUS_ADMISSIBLE":
            continue
        score = (0.65 * signal.mission_value) + (0.35 * signal.information_gain)
        prepared.append((score, signal.signal_id, decision))
    prepared.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in prepared]


def _hold(signal: AutoscaleSignal, policy: AutoscalePolicy, status: str, reason: str) -> AutoscaleDecision:
    return AutoscaleDecision(
        signal_id=signal.signal_id,
        policy_id=policy.policy_id,
        direction="HOLD",
        action="HOLD_AND_REEVALUATE",
        status=status,
        reason=reason,
        autonomous=True,
        owner_trigger_required=False,
        continue_unaffected_lanes=True,
    )


def _owner_gate(signal: AutoscaleSignal, policy: AutoscalePolicy, reason: str) -> AutoscaleDecision:
    return AutoscaleDecision(
        signal_id=signal.signal_id,
        policy_id=policy.policy_id,
        direction="GATED",
        action="OWNER_OR_PROVIDER_TRIGGER_REQUIRED",
        status="OWNER_TRIGGER_REQUIRED",
        reason=reason,
        autonomous=False,
        owner_trigger_required=True,
        continue_unaffected_lanes=True,
    )
