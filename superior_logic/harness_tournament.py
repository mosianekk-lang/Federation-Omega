from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Iterable, Sequence

from frontier_convergence.core import ExperimentIdentity, ExperimentIdentityCompiler, FinOpsParetoRouter, ValueReceipt


def _sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(x).strip() for x in values if str(x).strip()}))


@dataclass(frozen=True, slots=True)
class HarnessGenome:
    genome_id: str
    model_ref: str
    aci_profile: str
    context_policy: str
    skills: tuple[str, ...]
    tools: tuple[str, ...]
    workspace_policy: str
    fleet_shape: str
    verifier_profile: str

    @classmethod
    def create(cls, *, model_ref: str, aci_profile: str, context_policy: str,
               skills: Iterable[str] = (), tools: Iterable[str] = (),
               workspace_policy: str, fleet_shape: str, verifier_profile: str):
        body = {
            "model_ref": model_ref.strip(), "aci_profile": aci_profile.strip(),
            "context_policy": context_policy.strip(), "skills": _clean(skills),
            "tools": _clean(tools), "workspace_policy": workspace_policy.strip(),
            "fleet_shape": fleet_shape.strip(), "verifier_profile": verifier_profile.strip(),
        }
        if any(not body[k] for k in ("model_ref", "aci_profile", "context_policy", "workspace_policy", "fleet_shape", "verifier_profile")):
            raise ValueError("HARNESS_GENOME_FIELDS_REQUIRED")
        return cls(genome_id=f"SLOS-HARNESS-{_sha(body)[:24].upper()}", **body)


@dataclass(frozen=True, slots=True)
class HarnessExperiment:
    genome_id: str
    experiment: ExperimentIdentity
    comparison_fingerprint: str

    @property
    def fingerprint(self) -> str:
        return self.experiment.fingerprint


@dataclass(frozen=True, slots=True)
class HarnessOutcome:
    genome_id: str
    task_set_id: str
    acceptance_hash: str
    comparison_fingerprint: str
    sample_size: int
    accepted_task_rate: float
    verified_readback_rate: float
    regression_escape_rate: float
    median_wall_seconds: float
    median_cost: float
    owner_interventions: float
    tool_round_trips: float
    outcome_value: float
    evidence_refs: tuple[str, ...]

    def validate(self):
        if (
            not self.genome_id
            or not self.task_set_id
            or not self.acceptance_hash
            or not self.comparison_fingerprint
            or self.sample_size < 1
            or self.median_wall_seconds <= 0
        ):
            raise ValueError("HARNESS_OUTCOME_IDENTITY_OR_SAMPLE_INVALID")
        if min(self.median_cost, self.owner_interventions, self.tool_round_trips, self.outcome_value) < 0:
            raise ValueError("HARNESS_OUTCOME_NEGATIVE_BURDEN_OR_VALUE")
        for name in ("accepted_task_rate", "verified_readback_rate", "regression_escape_rate"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name.upper()}_OUTSIDE_UNIT_INTERVAL")
        if not self.evidence_refs:
            raise ValueError("HARNESS_OUTCOME_EVIDENCE_REQUIRED")

    def value_receipt(self) -> ValueReceipt:
        self.validate()
        quality = self.accepted_task_rate * self.verified_readback_rate * (1 - self.regression_escape_rate)
        reliability = min(self.accepted_task_rate, self.verified_readback_rate) * (1 - self.regression_escape_rate)
        return ValueReceipt.create(
            candidate_id=self.genome_id,
            quality=quality,
            reliability=reliability,
            latency_ms=self.median_wall_seconds * 1000,
            cost=self.median_cost,
            owner_burden=self.owner_interventions + 0.1 * self.tool_round_trips,
            outcome_value=self.outcome_value,
            evidence_refs=self.evidence_refs,
            measured=True,
        )


class HarnessExperimentCompiler:
    """Bind candidate-specific experiment identity plus a treatment-independent comparison cohort."""

    @staticmethod
    def compile(genome: HarnessGenome, *, implementation_sha256: str, source_sha256: str,
                inputs, environment, observation_window: str, cost_latency_context, controls, authority) -> HarnessExperiment:
        experiment = ExperimentIdentityCompiler.compile(
            implementation_sha256=implementation_sha256,
            source_sha256=source_sha256,
            inputs=inputs,
            environment=environment,
            observation_window=observation_window,
            parameters={"harness_genome": asdict(genome)},
            cost_latency_context=cost_latency_context,
            controls=controls,
            authority=authority,
        )
        cohort = {
            "source_sha256": source_sha256.strip(),
            "inputs": inputs,
            "environment": environment,
            "observation_window": observation_window.strip(),
            "cost_latency_context": cost_latency_context,
            "controls": controls,
            "authority": authority,
        }
        return HarnessExperiment(
            genome_id=genome.genome_id,
            experiment=experiment,
            comparison_fingerprint=_sha(cohort),
        )


@dataclass(frozen=True, slots=True)
class HarnessVerdict:
    comparable: bool
    pareto_ids: tuple[str, ...]
    hard_regressions: tuple[str, ...]
    reason: str
    verdict_sha256: str


class HarnessTournament:
    """Compare full coding harnesses; Frontier Convergence remains value-selection authority."""

    def compare(self, outcomes: Sequence[HarnessOutcome], *, incumbent_genome_id: str,
                minimum_quality: float, minimum_reliability: float, minimum_sample: int = 10) -> HarnessVerdict:
        if len(outcomes) < 2:
            raise ValueError("HARNESS_TOURNAMENT_NEEDS_TWO_OUTCOMES")
        for row in outcomes:
            row.validate()
        identities = {
            (x.task_set_id, x.acceptance_hash, x.comparison_fingerprint)
            for x in outcomes
        }
        if len(identities) != 1:
            return HarnessVerdict(False, (), (), "EXPERIMENT_IDENTITY_MISMATCH", _sha(sorted(identities)))
        if any(x.sample_size < minimum_sample for x in outcomes):
            samples = tuple(sorted((x.genome_id, x.sample_size) for x in outcomes))
            return HarnessVerdict(True, (), (), "INSUFFICIENT_PAIRED_SAMPLE", _sha(samples))
        by_id = {x.genome_id: x for x in outcomes}
        if incumbent_genome_id not in by_id:
            raise ValueError("INCUMBENT_HARNESS_MISSING")
        incumbent = by_id[incumbent_genome_id]
        regressions = tuple(sorted(
            x.genome_id for x in outcomes if x.genome_id != incumbent_genome_id and (
                x.accepted_task_rate < incumbent.accepted_task_rate
                or x.verified_readback_rate < incumbent.verified_readback_rate
                or x.regression_escape_rate > incumbent.regression_escape_rate
            )
        ))
        receipts = [x.value_receipt() for x in outcomes if x.genome_id not in set(regressions)]
        front = FinOpsParetoRouter.pareto_front(receipts, minimum_quality=minimum_quality, minimum_reliability=minimum_reliability)
        pareto_ids = tuple(x.candidate_id for x in front)
        reason = "UNIQUE_PARETO_WINNER" if len(pareto_ids) == 1 else "PARETO_FRONT" if pareto_ids else "NO_ELIGIBLE_HARNESS"
        body = (next(iter(identities)), incumbent_genome_id, pareto_ids, regressions, reason)
        return HarnessVerdict(True, pareto_ids, regressions, reason, _sha(body))


__all__ = [
    "HarnessExperiment",
    "HarnessExperimentCompiler",
    "HarnessGenome",
    "HarnessOutcome",
    "HarnessTournament",
    "HarnessVerdict",
]
