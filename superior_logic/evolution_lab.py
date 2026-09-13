from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from itertools import combinations, product
from typing import Any, Mapping, Sequence

from .harness_tournament import HarnessGenome


def _sha(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class EvolutionVariant:
    variant_id: str
    parent_genome_id: str
    genome: HarnessGenome
    changed_dimensions: tuple[str, ...]
    change_fingerprint: str


@dataclass(frozen=True, slots=True)
class EvolutionBatch:
    parent_genome_id: str
    variant_ids: tuple[str, ...]
    proof_obligations: tuple[str, ...]
    batch_sha256: str


class EvolutionLab:
    """Forms bounded harness challengers; it never promotes or executes them.

    Promotion remains owned by HarnessTournament / Frontier Convergence and final
    acceptance remains independent. The lab only generates deterministic challenger
    genomes from explicitly supplied substitutions.
    """

    MUTABLE_DIMENSIONS = frozenset(
        {
            "model_ref",
            "aci_profile",
            "context_policy",
            "skills",
            "tools",
            "workspace_policy",
            "fleet_shape",
            "verifier_profile",
        }
    )

    @staticmethod
    def _base_kwargs(genome: HarnessGenome) -> dict[str, Any]:
        body = asdict(genome)
        body.pop("genome_id", None)
        return body

    def generate(
        self,
        baseline: HarnessGenome,
        *,
        substitutions: Mapping[str, Sequence[Any]],
        max_variants: int = 12,
        max_changed_dimensions: int = 2,
    ) -> tuple[EvolutionVariant, ...]:
        if max_variants < 1:
            raise ValueError("EVOLUTION_MAX_VARIANTS_INVALID")
        if max_changed_dimensions not in {1, 2}:
            raise ValueError("EVOLUTION_DIMENSION_BOUND_INVALID")
        unknown = tuple(sorted(set(substitutions) - self.MUTABLE_DIMENSIONS))
        if unknown:
            raise ValueError(f"EVOLUTION_UNKNOWN_DIMENSION:{','.join(unknown)}")

        dimensions = tuple(sorted(key for key, values in substitutions.items() if tuple(values)))
        base = self._base_kwargs(baseline)
        seen = {baseline.genome_id}
        rows: list[EvolutionVariant] = []

        for width in range(1, min(max_changed_dimensions, len(dimensions)) + 1):
            for dims in combinations(dimensions, width):
                value_sets = [tuple(substitutions[d]) for d in dims]
                for replacement_values in product(*value_sets):
                    candidate = dict(base)
                    for dim, replacement in zip(dims, replacement_values):
                        candidate[dim] = replacement
                    genome = HarnessGenome.create(**candidate)
                    if genome.genome_id in seen:
                        continue
                    seen.add(genome.genome_id)
                    fingerprint = _sha(
                        {
                            "parent": baseline.genome_id,
                            "dimensions": dims,
                            "values": replacement_values,
                            "candidate": genome.genome_id,
                        }
                    )
                    rows.append(
                        EvolutionVariant(
                            variant_id=f"SLOS-EVO-{fingerprint[:24].upper()}",
                            parent_genome_id=baseline.genome_id,
                            genome=genome,
                            changed_dimensions=tuple(dims),
                            change_fingerprint=fingerprint,
                        )
                    )
                    if len(rows) >= max_variants:
                        return tuple(rows)
        return tuple(rows)

    def plan(self, baseline: HarnessGenome, variants: Sequence[EvolutionVariant]) -> EvolutionBatch:
        if any(row.parent_genome_id != baseline.genome_id for row in variants):
            raise ValueError("EVOLUTION_PARENT_MISMATCH")
        variant_ids = tuple(sorted(row.variant_id for row in variants))
        obligations = (
            "EXPERIMENT_IDENTITY",
            "MATCHED_TASK_SET",
            "HARD_REGRESSION_FENCE",
            "PARETO_HARNESS_COURT",
            "INDEPENDENT_ACCEPTANCE",
        )
        body = {
            "parent": baseline.genome_id,
            "variants": tuple(
                sorted(
                    (
                        row.variant_id,
                        row.genome.genome_id,
                        row.changed_dimensions,
                        row.change_fingerprint,
                    )
                    for row in variants
                )
            ),
            "proof_obligations": obligations,
        }
        return EvolutionBatch(
            parent_genome_id=baseline.genome_id,
            variant_ids=variant_ids,
            proof_obligations=obligations,
            batch_sha256=_sha(body),
        )


__all__ = ["EvolutionBatch", "EvolutionLab", "EvolutionVariant"]
