from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Iterable, Sequence


class ValueClass(str, Enum):
    COMMERCIAL = "COMMERCIAL"
    OPERATIONAL = "OPERATIONAL"
    USABILITY = "USABILITY"


class MetricDirection(str, Enum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


class ValueGateState(str, Enum):
    HOLD_NO_METRICS = "HOLD_NO_METRICS"
    HOLD_UNVERIFIED_METRICS = "HOLD_UNVERIFIED_METRICS"
    HOLD_CRITICAL_REGRESSION = "HOLD_CRITICAL_REGRESSION"
    HOLD_RUNTIME_PROOF = "HOLD_RUNTIME_PROOF"
    HOLD_REPEATED_SUCCESS = "HOLD_REPEATED_SUCCESS"
    HOLD_OPERATIONAL_VALUE = "HOLD_OPERATIONAL_VALUE"
    HOLD_USABILITY_VALUE = "HOLD_USABILITY_VALUE"
    HOLD_COMMERCIAL_VALUE = "HOLD_COMMERCIAL_VALUE"
    PRODUCTION_VALUE_CANDIDATE = "PRODUCTION_VALUE_CANDIDATE"


@dataclass(frozen=True, slots=True)
class MissionEconomics:
    """Direct mission economics supplied by trusted measurement, not by a model."""

    currency: str
    attributed_revenue: float = 0.0
    direct_provider_cost: float = 0.0
    external_tool_cost: float = 0.0
    owner_labor_cost: float = 0.0
    other_direct_cost: float = 0.0
    approved_assets: int = 0
    published_assets: int = 0

    def __post_init__(self) -> None:
        if not self.currency.strip():
            raise ValueError("currency is required")
        for name in (
            "attributed_revenue",
            "direct_provider_cost",
            "external_tool_cost",
            "owner_labor_cost",
            "other_direct_cost",
        ):
            value = float(getattr(self, name))
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.approved_assets < 0 or self.published_assets < 0:
            raise ValueError("asset counts cannot be negative")
        if self.published_assets > self.approved_assets and self.approved_assets > 0:
            raise ValueError("published_assets cannot exceed approved_assets")

    @property
    def total_cost(self) -> float:
        return (
            float(self.direct_provider_cost)
            + float(self.external_tool_cost)
            + float(self.owner_labor_cost)
            + float(self.other_direct_cost)
        )

    @property
    def contribution_margin(self) -> float:
        return float(self.attributed_revenue) - self.total_cost

    @property
    def margin_rate(self) -> float | None:
        if self.attributed_revenue <= 0:
            return None
        return self.contribution_margin / float(self.attributed_revenue)

    @property
    def cost_per_approved_asset(self) -> float | None:
        if self.approved_assets <= 0:
            return None
        return self.total_cost / self.approved_assets

    @property
    def revenue_per_published_asset(self) -> float | None:
        if self.published_assets <= 0:
            return None
        return float(self.attributed_revenue) / self.published_assets


@dataclass(frozen=True, slots=True)
class ValueMetricSpec:
    metric: str
    value_class: ValueClass
    direction: MetricDirection
    weight: float = 1.0
    minimum_gain: float = 1.0
    minimum_candidate: float | None = None
    required: bool = True
    hard_gate: bool = False

    def __post_init__(self) -> None:
        if not self.metric.strip():
            raise ValueError("metric is required")
        if not isfinite(float(self.weight)) or float(self.weight) <= 0:
            raise ValueError("weight must be finite and positive")
        if not isfinite(float(self.minimum_gain)) or float(self.minimum_gain) < 1.0:
            raise ValueError("minimum_gain must be finite and cannot be below 1.0")
        if self.minimum_candidate is not None and not isfinite(float(self.minimum_candidate)):
            raise ValueError("minimum_candidate must be finite")


@dataclass(frozen=True, slots=True)
class MetricObservation:
    metric: str
    baseline: float
    candidate: float
    evidence_ref: str
    verified: bool = True

    def __post_init__(self) -> None:
        if not self.metric.strip():
            raise ValueError("metric is required")
        if not isfinite(float(self.baseline)) or not isfinite(float(self.candidate)):
            raise ValueError("metric observations must be finite")
        if not self.evidence_ref.strip():
            raise ValueError("evidence_ref is required")


@dataclass(frozen=True, slots=True)
class MetricComparison:
    metric: str
    value_class: ValueClass
    baseline: float
    candidate: float
    target_value: float
    minimum_gain: float
    minimum_candidate: float | None
    target_met: bool
    hard_gate_pass: bool
    relative_gain: float | None
    evidence_ref: str


@dataclass(frozen=True, slots=True)
class ValueEvidence:
    provider_native_readback: bool
    repeated_success: bool
    critical_regression: bool = False


@dataclass(frozen=True, slots=True)
class ValueGateDecision:
    state: ValueGateState
    promotion_ready: bool
    commercial_target_rate: float
    operational_target_rate: float
    usability_target_rate: float
    comparisons: tuple[MetricComparison, ...]
    reasons: tuple[str, ...]


def economics_snapshot(economics: MissionEconomics) -> dict[str, float]:
    """Return only economics metrics that have a meaningful denominator."""

    out: dict[str, float] = {
        "attributed_revenue": float(economics.attributed_revenue),
        "total_cost": economics.total_cost,
        "contribution_margin": economics.contribution_margin,
        "approved_assets": float(economics.approved_assets),
        "published_assets": float(economics.published_assets),
    }
    if economics.margin_rate is not None:
        out["margin_rate"] = economics.margin_rate
    if economics.cost_per_approved_asset is not None:
        out["cost_per_approved_asset"] = economics.cost_per_approved_asset
    if economics.revenue_per_published_asset is not None:
        out["revenue_per_published_asset"] = economics.revenue_per_published_asset
    return out


def _target_value(spec: ValueMetricSpec, baseline: float) -> float:
    if spec.direction is MetricDirection.HIGHER_IS_BETTER:
        if baseline > 0:
            return baseline * float(spec.minimum_gain)
        # A zero/negative baseline does not define multiplicative commercial growth.
        # The optional minimum_candidate provides the absolute crossing threshold.
        return baseline
    if baseline > 0:
        return baseline / float(spec.minimum_gain)
    return baseline


def _relative_gain(spec: ValueMetricSpec, baseline: float, candidate: float) -> float | None:
    """Return a ratio only when mathematically meaningful; never fabricate 10x."""

    if baseline <= 0:
        return None
    if spec.direction is MetricDirection.HIGHER_IS_BETTER:
        return candidate / baseline
    if candidate <= 0:
        return None
    return baseline / candidate


def _target_met(spec: ValueMetricSpec, baseline: float, candidate: float, target: float) -> bool:
    if spec.direction is MetricDirection.HIGHER_IS_BETTER:
        directional = candidate >= target
    else:
        directional = candidate <= target
    if spec.minimum_candidate is None:
        return directional
    if spec.direction is MetricDirection.HIGHER_IS_BETTER:
        return directional and candidate >= float(spec.minimum_candidate)
    return directional and candidate <= float(spec.minimum_candidate)


def compare_value_metrics(
    *,
    specs: Sequence[ValueMetricSpec],
    observations: Iterable[MetricObservation],
) -> tuple[MetricComparison, ...]:
    if not specs:
        raise ValueError("at least one value metric specification is required")

    observed = {item.metric: item for item in observations}
    comparisons: list[MetricComparison] = []
    for spec in specs:
        observation = observed.get(spec.metric)
        if observation is None:
            if spec.required:
                raise ValueError(f"missing required metric observation: {spec.metric}")
            continue
        if not observation.verified:
            raise ValueError(f"metric observation is not verified: {spec.metric}")

        baseline = float(observation.baseline)
        candidate = float(observation.candidate)
        target = _target_value(spec, baseline)
        target_met = _target_met(spec, baseline, candidate, target)
        hard_gate_pass = target_met if spec.hard_gate else True
        comparisons.append(
            MetricComparison(
                metric=spec.metric,
                value_class=spec.value_class,
                baseline=baseline,
                candidate=candidate,
                target_value=target,
                minimum_gain=float(spec.minimum_gain),
                minimum_candidate=spec.minimum_candidate,
                target_met=target_met,
                hard_gate_pass=hard_gate_pass,
                relative_gain=_relative_gain(spec, baseline, candidate),
                evidence_ref=observation.evidence_ref,
            )
        )
    return tuple(comparisons)


def _class_target_rate(
    *,
    value_class: ValueClass,
    specs: Sequence[ValueMetricSpec],
    comparisons: Sequence[MetricComparison],
) -> float:
    spec_map = {spec.metric: spec for spec in specs if spec.value_class is value_class}
    rows = [row for row in comparisons if row.value_class is value_class]
    if not spec_map:
        return 0.0
    weighted_total = sum(float(spec.weight) for spec in spec_map.values())
    if weighted_total <= 0:
        return 0.0
    weighted_met = 0.0
    by_metric = {row.metric: row for row in rows}
    for metric, spec in spec_map.items():
        row = by_metric.get(metric)
        if row is not None and row.target_met:
            weighted_met += float(spec.weight)
    return weighted_met / weighted_total


def evaluate_value_gate(
    *,
    specs: Sequence[ValueMetricSpec],
    observations: Iterable[MetricObservation],
    evidence: ValueEvidence,
) -> ValueGateDecision:
    """Require commercial, operational and usability value before production promotion."""

    rows = tuple(observations)
    reasons: list[str] = []
    if not specs or not rows:
        return ValueGateDecision(
            ValueGateState.HOLD_NO_METRICS, False, 0.0, 0.0, 0.0, (), ("NO_VALUE_METRICS",)
        )

    required = {spec.metric for spec in specs if spec.required}
    by_metric = {row.metric: row for row in rows}
    missing = tuple(sorted(required - set(by_metric)))
    if missing:
        return ValueGateDecision(
            ValueGateState.HOLD_NO_METRICS,
            False,
            0.0,
            0.0,
            0.0,
            (),
            tuple(f"MISSING:{metric}" for metric in missing),
        )

    unverified = tuple(sorted(metric for metric in required if not by_metric[metric].verified))
    if unverified:
        return ValueGateDecision(
            ValueGateState.HOLD_UNVERIFIED_METRICS,
            False,
            0.0,
            0.0,
            0.0,
            (),
            tuple(f"UNVERIFIED:{metric}" for metric in unverified),
        )

    comparisons = compare_value_metrics(specs=specs, observations=rows)
    commercial_rate = _class_target_rate(
        value_class=ValueClass.COMMERCIAL, specs=specs, comparisons=comparisons
    )
    operational_rate = _class_target_rate(
        value_class=ValueClass.OPERATIONAL, specs=specs, comparisons=comparisons
    )
    usability_rate = _class_target_rate(
        value_class=ValueClass.USABILITY, specs=specs, comparisons=comparisons
    )

    hard_failures = tuple(row.metric for row in comparisons if not row.hard_gate_pass)
    if evidence.critical_regression or hard_failures:
        reasons.extend(f"HARD_REGRESSION:{metric}" for metric in hard_failures)
        if evidence.critical_regression:
            reasons.append("CRITICAL_REGRESSION")
        return ValueGateDecision(
            ValueGateState.HOLD_CRITICAL_REGRESSION,
            False,
            commercial_rate,
            operational_rate,
            usability_rate,
            comparisons,
            tuple(reasons),
        )

    if not evidence.provider_native_readback:
        return ValueGateDecision(
            ValueGateState.HOLD_RUNTIME_PROOF,
            False,
            commercial_rate,
            operational_rate,
            usability_rate,
            comparisons,
            ("PROVIDER_NATIVE_READBACK_REQUIRED",),
        )
    if not evidence.repeated_success:
        return ValueGateDecision(
            ValueGateState.HOLD_REPEATED_SUCCESS,
            False,
            commercial_rate,
            operational_rate,
            usability_rate,
            comparisons,
            ("REPEATED_SUCCESS_REQUIRED",),
        )
    if operational_rate < 1.0:
        return ValueGateDecision(
            ValueGateState.HOLD_OPERATIONAL_VALUE,
            False,
            commercial_rate,
            operational_rate,
            usability_rate,
            comparisons,
            ("OPERATIONAL_VALUE_TARGETS_NOT_MET",),
        )
    if usability_rate < 1.0:
        return ValueGateDecision(
            ValueGateState.HOLD_USABILITY_VALUE,
            False,
            commercial_rate,
            operational_rate,
            usability_rate,
            comparisons,
            ("USABILITY_VALUE_TARGETS_NOT_MET",),
        )
    if commercial_rate < 1.0:
        return ValueGateDecision(
            ValueGateState.HOLD_COMMERCIAL_VALUE,
            False,
            commercial_rate,
            operational_rate,
            usability_rate,
            comparisons,
            ("COMMERCIAL_VALUE_TARGETS_NOT_MET",),
        )

    return ValueGateDecision(
        ValueGateState.PRODUCTION_VALUE_CANDIDATE,
        True,
        commercial_rate,
        operational_rate,
        usability_rate,
        comparisons,
        ("ALL_VALUE_CLASSES_VERIFIED",),
    )


def default_production_value_specs() -> tuple[ValueMetricSpec, ...]:
    """Conservative repeated-mission scorecard.

    Revenue/margin can be replaced by verified channel-specific commercial metrics
    (for example ROAS, CPA or conversion) in a mission-specific scorecard, but the
    COMMERCIAL class may not be silently omitted from production promotion.
    """

    return (
        ValueMetricSpec(
            "contribution_margin",
            ValueClass.COMMERCIAL,
            MetricDirection.HIGHER_IS_BETTER,
            weight=2.0,
            minimum_gain=1.0,
            minimum_candidate=0.01,
            required=True,
            hard_gate=True,
        ),
        ValueMetricSpec(
            "attributed_revenue",
            ValueClass.COMMERCIAL,
            MetricDirection.HIGHER_IS_BETTER,
            weight=1.5,
            minimum_gain=1.0,
            minimum_candidate=0.01,
            required=True,
        ),
        ValueMetricSpec(
            "time_to_deliverable_seconds",
            ValueClass.OPERATIONAL,
            MetricDirection.LOWER_IS_BETTER,
            weight=1.5,
            minimum_gain=1.0,
            required=True,
        ),
        ValueMetricSpec(
            "publication_success_rate",
            ValueClass.OPERATIONAL,
            MetricDirection.HIGHER_IS_BETTER,
            weight=1.0,
            minimum_gain=1.0,
            required=True,
            hard_gate=True,
        ),
        ValueMetricSpec(
            "owner_interventions",
            ValueClass.USABILITY,
            MetricDirection.LOWER_IS_BETTER,
            weight=1.5,
            minimum_gain=1.0,
            required=True,
        ),
        ValueMetricSpec(
            "owner_minutes",
            ValueClass.USABILITY,
            MetricDirection.LOWER_IS_BETTER,
            weight=1.0,
            minimum_gain=1.0,
            required=True,
        ),
    )
