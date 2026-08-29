"""CFBE-Ω v4 Capability Foundry readiness bridge.

This module composes existing Federation contracts instead of creating a second
foundry or a second opportunity-scoring system:

* Frontier Convergence OS supplies normalized experiment economics.
* CFBE supplies explicit confidence and repeated capability-gap observations.
* ProofOS/CFBE supplies a named regression baseline with provenance.
* SOVARA MCF v3.1 supplies the canonical OpportunityGradientEngine formula.

The bridge is provider-neutral and effect-free.  It cannot manufacture gap
observations, confidence, regression baselines, provider authority, or maturity.
Synthetic fixtures may test the algorithm but may not produce DATA_READY.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from frontier_convergence.os_core import ExperimentOption
from ops.sovara_mcf_v3_1.sovara_mcf_v3_1 import (
    OpportunityCandidate,
    OpportunityGradientEngine,
)


CAPABILITY_FOUNDRY_MODULE_ID = "V4_CAPABILITY_FOUNDRY"
OBSERVED_GAP_EVIDENCE = "OBSERVED_FEDERATION_GAP"
MIN_REPEATED_GAP_OBSERVATIONS = 2


@dataclass(frozen=True)
class GapObservation:
    """One independently provenance-bound observation of the same capability gap."""

    observation_id: str
    capability_gap: str
    evidence_refs: tuple[str, ...]
    evidence_class: str = OBSERVED_GAP_EVIDENCE


@dataclass(frozen=True)
class RegressionBaselineEvidence:
    """Named pre-change regression/benchmark baseline with exact evidence refs."""

    baseline_id: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class CapabilityFoundryInput:
    """Complete evidence packet required to form canonical v4 Foundry data."""

    experiment: ExperimentOption
    confidence: float
    gap_observations: tuple[GapObservation, ...]
    regression_baseline: RegressionBaselineEvidence


@dataclass(frozen=True)
class CapabilityFoundryReadinessReport:
    module_id: str
    state: str
    opportunity_gradient: float | None
    capability_gap: str
    regression_baseline: str
    qualifying_gap_observation_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    blockers: tuple[str, ...]
    truth_boundary: str


def _expected_gain(option: ExperimentOption) -> float:
    """Compile a positive expected-gain term without double-counting penalties.

    FC-OS already normalizes these three positive dimensions to [0,1].  Cost,
    risk and owner burden are deliberately excluded here because the canonical
    SOVARA OpportunityGradientEngine applies those as denominator penalties.
    """

    return round(
        (
            float(option.expected_information_gain)
            + float(option.mission_value)
            + float(option.proof_strength_gain)
        )
        / 3.0,
        9,
    )


def compile_opportunity_gradient(option: ExperimentOption, confidence: float) -> float:
    """Use the existing SOVARA MCF formula; do not define a competing gradient."""

    confidence = float(confidence)
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("FOUNDRY_CONFIDENCE_OUT_OF_RANGE")
    candidate = OpportunityCandidate(
        opportunity_id=option.option_key,
        expected_gain=_expected_gain(option),
        confidence=confidence,
        reversibility=float(option.reversibility),
        implementation_cost=float(option.estimated_cost),
        regression_risk=float(option.risk),
        owner_burden=float(option.owner_burden),
    )
    return float(OpportunityGradientEngine.score(candidate))


def _clean_refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def evaluate_capability_foundry_readiness(
    packet: CapabilityFoundryInput,
) -> CapabilityFoundryReadinessReport:
    """Evaluate whether v4 Capability Foundry has a complete data packet.

    DATA_READY requires:
    - a real FC-OS experiment option with provenance;
    - explicit CFBE confidence in [0,1];
    - at least two distinct observed Federation gap records describing the same
      non-empty capability gap, each with provenance;
    - a named regression baseline with provenance; and
    - a successfully computed canonical SOVARA opportunity gradient.

    The bridge stops at DATA_READY.  Incubation still requires the separate
    CFBE positive-expected-value gate and all downstream proof/authority gates.
    """

    blockers: set[str] = set()
    refs: set[str] = set(_clean_refs(packet.experiment.evidence_refs))

    if not packet.experiment.evidence_refs:
        blockers.add("EXPERIMENT_PROVENANCE_REQUIRED")

    confidence = float(packet.confidence)
    if not 0.0 <= confidence <= 1.0:
        blockers.add("CONFIDENCE_OUT_OF_RANGE")

    baseline_id = str(packet.regression_baseline.baseline_id).strip()
    baseline_refs = _clean_refs(packet.regression_baseline.evidence_refs)
    if not baseline_id:
        blockers.add("REGRESSION_BASELINE_ID_REQUIRED")
    if not baseline_refs:
        blockers.add("REGRESSION_BASELINE_PROVENANCE_REQUIRED")
    refs.update(baseline_refs)

    observed: list[GapObservation] = []
    capability_gaps: set[str] = set()
    seen_observation_ids: set[str] = set()
    for item in packet.gap_observations:
        observation_id = str(item.observation_id).strip()
        capability_gap = " ".join(str(item.capability_gap).split())
        evidence_refs = _clean_refs(item.evidence_refs)
        if item.evidence_class != OBSERVED_GAP_EVIDENCE:
            continue
        if not observation_id or not capability_gap or not evidence_refs:
            blockers.add("GAP_OBSERVATION_PROVENANCE_REQUIRED")
            continue
        if observation_id in seen_observation_ids:
            blockers.add("DUPLICATE_GAP_OBSERVATION_ID")
            continue
        seen_observation_ids.add(observation_id)
        capability_gaps.add(capability_gap)
        refs.update(evidence_refs)
        observed.append(item)

    if len(capability_gaps) > 1:
        blockers.add("CAPABILITY_GAP_MISMATCH")
    if len(observed) < MIN_REPEATED_GAP_OBSERVATIONS:
        blockers.add("REPEATED_GAP_EVIDENCE_REQUIRED")

    capability_gap = next(iter(capability_gaps), "") if len(capability_gaps) == 1 else ""

    gradient: float | None = None
    if "CONFIDENCE_OUT_OF_RANGE" not in blockers:
        try:
            gradient = compile_opportunity_gradient(packet.experiment, confidence)
        except (TypeError, ValueError, ZeroDivisionError):
            blockers.add("OPPORTUNITY_GRADIENT_UNRESOLVED")

    if blockers:
        if "CAPABILITY_GAP_MISMATCH" in blockers or "DUPLICATE_GAP_OBSERVATION_ID" in blockers:
            state = "HELD_GAP_EVIDENCE_CONFLICT"
        elif "REPEATED_GAP_EVIDENCE_REQUIRED" in blockers:
            state = "INSTRUMENTED_REPEATED_GAP_EVIDENCE_REQUIRED"
        elif any(blocker.startswith("REGRESSION_BASELINE") for blocker in blockers):
            state = "HELD_REGRESSION_BASELINE_REQUIRED"
        elif "EXPERIMENT_PROVENANCE_REQUIRED" in blockers:
            state = "HELD_EXPERIMENT_PROVENANCE_REQUIRED"
        else:
            state = "HELD_INCOMPLETE_FOUNDRY_DATA"
    else:
        state = "DATA_READY"

    return CapabilityFoundryReadinessReport(
        module_id=CAPABILITY_FOUNDRY_MODULE_ID,
        state=state,
        opportunity_gradient=gradient,
        capability_gap=capability_gap,
        regression_baseline=baseline_id,
        qualifying_gap_observation_ids=tuple(
            sorted(str(item.observation_id).strip() for item in observed)
        ),
        evidence_refs=tuple(sorted(refs)),
        blockers=tuple(sorted(blockers)),
        truth_boundary=(
            "DATA_READY proves only a complete provenance-bound Foundry evidence packet. "
            "It does not prove positive expected value, candidate construction, incubation, "
            "provider execution, regression safety, operational maturity, or promotion."
        ),
    )
