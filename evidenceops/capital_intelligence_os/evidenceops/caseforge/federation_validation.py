from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence


AUTHORITY_CEILING = "A1_INTERNAL"


class MaturityState(str, Enum):
    DESIGNED = "DESIGNED"
    DETERMINISTIC_TESTED = "DETERMINISTIC_TESTED"
    SHADOW_VALIDATED = "SHADOW_VALIDATED"
    ADVERSARIALLY_VALIDATED = "ADVERSARIALLY_VALIDATED"
    CANARY_VALIDATED = "CANARY_VALIDATED"
    LIMITED_WORKFLOW_VERIFIED = "LIMITED_WORKFLOW_VERIFIED"
    CROSS_DOMAIN_VERIFIED = "CROSS_DOMAIN_VERIFIED"
    OPERATIONAL_VERIFIED = "OPERATIONAL_VERIFIED"


MATURITY_ORDER = tuple(MaturityState)


@dataclass(frozen=True)
class FederationEvaluationContract:
    component_id: str
    mission: str
    hypothesis: str
    baseline_ref: str
    metrics: Mapping[str, float]
    failure_fingerprints: tuple[str, ...] = ()
    red_team_passed: bool = False
    regression_passed: bool = False
    proof_receipt: str = ""
    maturity: MaturityState = MaturityState.DESIGNED
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False

    def validate(self) -> "FederationEvaluationContract":
        if not self.component_id.strip():
            raise ValueError("component_id is required")
        if not self.mission.strip():
            raise ValueError("mission is required")
        if not self.hypothesis.strip():
            raise ValueError("hypothesis is required")
        if not self.baseline_ref.strip():
            raise ValueError("baseline_ref is required")
        if not self.metrics:
            raise ValueError("at least one metric is required")
        for name, value in self.metrics.items():
            if not name.strip():
                raise ValueError("metric names must be non-empty")
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"metric {name} must be in [0,1]")
        if self.external_effect:
            raise ValueError("CASEFORGE federation evaluation contracts are A1_INTERNAL only")
        if self.authority_ceiling != AUTHORITY_CEILING:
            raise ValueError("unsupported authority ceiling")
        if self.maturity != MaturityState.DESIGNED:
            if not self.regression_passed:
                raise ValueError("maturity above DESIGNED requires regression proof")
            if not self.proof_receipt.strip():
                raise ValueError("maturity above DESIGNED requires a proof receipt")
        if MATURITY_ORDER.index(self.maturity) >= MATURITY_ORDER.index(MaturityState.ADVERSARIALLY_VALIDATED):
            if not self.red_team_passed:
                raise ValueError("adversarial maturity requires red-team proof")
        return self

    @property
    def score(self) -> float:
        if not self.metrics:
            return 0.0
        return round(sum(float(v) for v in self.metrics.values()) / len(self.metrics), 8)


def _ratio(correct: int, total: int) -> float:
    return 1.0 if total <= 0 else max(0.0, min(1.0, correct / total))


def _bool_score(value: bool) -> float:
    return 1.0 if value else 0.0


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class ContinuityProbe:
    expected_state: Mapping[str, Any]
    recovered_state: Mapping[str, Any]
    expected_sources: Mapping[str, str]
    recovered_sources: Mapping[str, str]
    corrected_keys: frozenset[str] = frozenset()
    superseded_values: Mapping[str, Any] | None = None
    expected_routes: Mapping[str, str] | None = None
    recovered_routes: Mapping[str, str] | None = None
    expected_contradictions: frozenset[str] = frozenset()
    detected_contradictions: frozenset[str] = frozenset()


class ContinuityForge:
    """Tests cross-chat/workstream state recovery without creating hidden memory claims."""

    component_id = "CASEFORGE-CONTINUITY"

    def evaluate(self, probe: ContinuityProbe, *, baseline_ref: str = "continuity-baseline") -> FederationEvaluationContract:
        expected = dict(probe.expected_state)
        recovered = dict(probe.recovered_state)
        matched = sum(1 for key, value in expected.items() if recovered.get(key) == value)
        present = sum(1 for key in expected if key in recovered)

        source_expected = dict(probe.expected_sources)
        source_recovered = dict(probe.recovered_sources)
        source_matches = sum(1 for key, value in source_expected.items() if source_recovered.get(key) == value)

        corrected = set(probe.corrected_keys)
        correction_matches = sum(1 for key in corrected if key in expected and recovered.get(key) == expected.get(key))

        superseded = dict(probe.superseded_values or {})
        stale_reintroduced = tuple(
            sorted(key for key, stale_value in superseded.items() if recovered.get(key) == stale_value and expected.get(key) != stale_value)
        )

        expected_routes = dict(probe.expected_routes or {})
        recovered_routes = dict(probe.recovered_routes or {})
        route_matches = sum(1 for key, route in expected_routes.items() if recovered_routes.get(key) == route)

        contradictions_expected = set(probe.expected_contradictions)
        contradictions_detected = set(probe.detected_contradictions)
        contradiction_matches = len(contradictions_expected & contradictions_detected)

        metrics = {
            "context_recovery": _ratio(present, len(expected)),
            "canonical_state_accuracy": _ratio(matched, len(expected)),
            "provenance_fidelity": _ratio(source_matches, len(source_expected)),
            "correction_retention": _ratio(correction_matches, len(corrected)),
            "stale_memory_rejection": 1.0 if not stale_reintroduced else 0.0,
            "route_separation": _ratio(route_matches, len(expected_routes)),
            "contradiction_detection": _ratio(contradiction_matches, len(contradictions_expected)),
        }
        failures: list[str] = []
        if stale_reintroduced:
            failures.append("CONTINUITY_STALE_STATE_REINTRODUCED:" + ",".join(stale_reintroduced))
        if metrics["canonical_state_accuracy"] < 1.0:
            failures.append("CONTINUITY_CANONICAL_STATE_DRIFT")
        if metrics["provenance_fidelity"] < 1.0:
            failures.append("CONTINUITY_PROVENANCE_DRIFT")
        if metrics["route_separation"] < 1.0:
            failures.append("CONTINUITY_ROUTE_COLLAPSE")

        return FederationEvaluationContract(
            component_id=self.component_id,
            mission="Recover the correct canonical workstream state across chat and memory boundaries without stale-state or provenance drift.",
            hypothesis="The continuity fabric reproduces current canonical state, corrections, route walls and provenance from explicit governed records.",
            baseline_ref=baseline_ref,
            metrics=metrics,
            failure_fingerprints=tuple(failures),
        ).validate()


@dataclass(frozen=True)
class CapabilityProbe:
    capability_id: str
    heartbeat_state: str
    ttl_seconds: int
    age_seconds: int
    semantic_ok: bool
    readback_ok: bool
    authority_verified: bool
    reliability: float = 1.0
    effectful: bool = False


@dataclass(frozen=True)
class CapabilityForgeResult:
    evaluation: FederationEvaluationContract
    eligible: tuple[str, ...]
    degraded: tuple[str, ...]
    ao_cra_builds: tuple[str, ...]


class CapabilityForge:
    """Empirically ranks current Federation capabilities; architecture or subscription alone is not availability."""

    component_id = "CASEFORGE-CAPABILITY"
    eligible_states = {
        "SESSION_CONNECTOR_AVAILABLE",
        "TURN_TRANSACTION_VERIFIED_LOCAL",
        "PROVIDER_VERIFIED",
        "LIVE_ORCHESTRATION_VERIFIED",
        "CONNECTED_READ",
        "CONNECTED_READ_WRITE",
    }

    def _freshness(self, probe: CapabilityProbe) -> float:
        ttl = max(1, int(probe.ttl_seconds))
        age = max(0, int(probe.age_seconds))
        if age <= ttl:
            return 1.0
        return _clamp(ttl / age)

    def evaluate(self, probes: Sequence[CapabilityProbe], *, baseline_ref: str = "capability-heartbeat") -> CapabilityForgeResult:
        if not probes:
            raise ValueError("at least one capability probe is required")
        semantic = sum(_bool_score(item.semantic_ok) for item in probes) / len(probes)
        readback = sum(_bool_score(item.readback_ok) for item in probes) / len(probes)
        authority = sum(_bool_score(item.authority_verified) for item in probes) / len(probes)
        freshness = sum(self._freshness(item) for item in probes) / len(probes)
        reliability = sum(_clamp(item.reliability) for item in probes) / len(probes)
        state_validity = sum(_bool_score(item.heartbeat_state in self.eligible_states) for item in probes) / len(probes)

        eligible: list[str] = []
        degraded: list[str] = []
        builds: list[str] = []
        failures: list[str] = []
        for item in probes:
            fresh = self._freshness(item) == 1.0
            usable = (
                item.heartbeat_state in self.eligible_states
                and fresh
                and item.semantic_ok
                and item.readback_ok
                and item.authority_verified
            )
            if usable:
                eligible.append(item.capability_id)
                continue
            degraded.append(item.capability_id)
            reasons: list[str] = []
            if item.heartbeat_state not in self.eligible_states:
                reasons.append("STATE")
            if not fresh:
                reasons.append("STALE")
            if not item.semantic_ok:
                reasons.append("SEMANTIC")
            if not item.readback_ok:
                reasons.append("READBACK")
            if not item.authority_verified:
                reasons.append("AUTHORITY")
            failures.append(f"CAPABILITY_DEGRADED:{item.capability_id}:" + "+".join(reasons))
            builds.append(f"AO-CRA:CAPABILITY:{item.capability_id}")

        evaluation = FederationEvaluationContract(
            component_id=self.component_id,
            mission="Route Federation work through capabilities whose current semantic behaviour, freshness, authority and readback are actually verified.",
            hypothesis="Heartbeat and provider probes can distinguish usable capability from stale, architectural or subscription-only capability.",
            baseline_ref=baseline_ref,
            metrics={
                "state_validity": round(state_validity, 8),
                "freshness": round(freshness, 8),
                "semantic_correctness": round(semantic, 8),
                "provider_readback": round(readback, 8),
                "authority_integrity": round(authority, 8),
                "observed_reliability": round(reliability, 8),
            },
            failure_fingerprints=tuple(failures),
        ).validate()
        return CapabilityForgeResult(
            evaluation=evaluation,
            eligible=tuple(sorted(eligible)),
            degraded=tuple(sorted(degraded)),
            ao_cra_builds=tuple(sorted(set(builds))),
        )

    def select_minimum_sufficient(
        self,
        required: Iterable[str],
        capability_roles: Mapping[str, Iterable[str]],
        result: CapabilityForgeResult,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        uncovered = set(required)
        chosen: list[str] = []
        eligible = set(result.eligible)
        while uncovered:
            best_id = ""
            best_cover: set[str] = set()
            for capability_id, roles in capability_roles.items():
                if capability_id not in eligible or capability_id in chosen:
                    continue
                cover = uncovered & set(roles)
                if len(cover) > len(best_cover):
                    best_id, best_cover = capability_id, cover
            if not best_id:
                break
            chosen.append(best_id)
            uncovered -= best_cover
        return tuple(chosen), tuple(sorted(uncovered))


@dataclass(frozen=True)
class RecoveryTrace:
    failure_fingerprint: str
    original_failure_preserved: bool
    deterministic_classification: bool
    circuit_opened_on_repeat: bool
    unchanged_broken_lane_retried: bool
    unaffected_lanes_continued: bool
    reversible_repair: bool
    state_integrity_ok: bool
    independent_readback_ok: bool
    rollback_available: bool
    recovery_completed: bool


class AutoFixLaboratory:
    """Stress-tests RESOLVE/AutoFIX recovery traces without weakening failure or proof gates."""

    component_id = "CASEFORGE-AUTOFIX-LAB"

    def evaluate(self, traces: Sequence[RecoveryTrace], *, baseline_ref: str = "resolve-autofix-baseline") -> FederationEvaluationContract:
        if not traces:
            raise ValueError("at least one recovery trace is required")
        n = len(traces)
        metrics = {
            "failure_preservation": sum(_bool_score(t.original_failure_preserved) for t in traces) / n,
            "failure_classification": sum(_bool_score(t.deterministic_classification) for t in traces) / n,
            "circuit_breaking": sum(_bool_score(t.circuit_opened_on_repeat and not t.unchanged_broken_lane_retried) for t in traces) / n,
            "unaffected_lane_continuity": sum(_bool_score(t.unaffected_lanes_continued) for t in traces) / n,
            "repair_reversibility": sum(_bool_score(t.reversible_repair and t.rollback_available) for t in traces) / n,
            "state_integrity": sum(_bool_score(t.state_integrity_ok) for t in traces) / n,
            "independent_readback": sum(_bool_score(t.independent_readback_ok) for t in traces) / n,
            "recovery_completion": sum(_bool_score(t.recovery_completed) for t in traces) / n,
        }
        failures: list[str] = []
        for trace in traces:
            prefix = trace.failure_fingerprint or "UNKNOWN"
            if not trace.original_failure_preserved:
                failures.append(f"AUTOFIX_FAILURE_EVIDENCE_LOST:{prefix}")
            if trace.unchanged_broken_lane_retried:
                failures.append(f"AUTOFIX_REPEAT_ROUTE_VIOLATION:{prefix}")
            if not trace.state_integrity_ok:
                failures.append(f"AUTOFIX_STATE_CORRUPTION:{prefix}")
            if trace.recovery_completed and not trace.independent_readback_ok:
                failures.append(f"AUTOFIX_FALSE_COMPLETION:{prefix}")
            if not trace.rollback_available:
                failures.append(f"AUTOFIX_ROLLBACK_MISSING:{prefix}")

        return FederationEvaluationContract(
            component_id=self.component_id,
            mission="Prove that recovery logic isolates failures, preserves evidence, continues independent work and repairs safely without false completion.",
            hypothesis="RESOLVE/AutoFIX can recover from injected failure classes through circuit breaking, reversible repair and independent readback without corrupting unaffected state.",
            baseline_ref=baseline_ref,
            metrics={key: round(value, 8) for key, value in metrics.items()},
            failure_fingerprints=tuple(failures),
        ).validate()


def promote_contract(
    contract: FederationEvaluationContract,
    *,
    target: MaturityState,
    regression_passed: bool,
    red_team_passed: bool,
    proof_receipt: str,
) -> FederationEvaluationContract:
    current_index = MATURITY_ORDER.index(contract.maturity)
    target_index = MATURITY_ORDER.index(target)
    if target_index != current_index + 1:
        raise ValueError("maturity promotion must be sequential")
    promoted = FederationEvaluationContract(
        component_id=contract.component_id,
        mission=contract.mission,
        hypothesis=contract.hypothesis,
        baseline_ref=contract.baseline_ref,
        metrics=dict(contract.metrics),
        failure_fingerprints=contract.failure_fingerprints,
        red_team_passed=red_team_passed,
        regression_passed=regression_passed,
        proof_receipt=proof_receipt,
        maturity=target,
        authority_ceiling=contract.authority_ceiling,
        external_effect=False,
    )
    return promoted.validate()


__all__ = [
    "AUTHORITY_CEILING",
    "AutoFixLaboratory",
    "CapabilityForge",
    "CapabilityForgeResult",
    "CapabilityProbe",
    "ContinuityForge",
    "ContinuityProbe",
    "FederationEvaluationContract",
    "MATURITY_ORDER",
    "MaturityState",
    "RecoveryTrace",
    "promote_contract",
]
