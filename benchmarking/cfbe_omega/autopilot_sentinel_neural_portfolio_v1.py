from __future__ import annotations

"""Effect-free neural substrate portfolio for FASCG.

This is a capability passport/search-space description. It does not train, mutate,
download, fine-tune, or serve model weights. Neural/weight-level changes remain
separately provider/compute/authority gated.
"""

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence

SCHEMA = "FASCG-NEURAL-SUBSTRATE-PORTFOLIO-V1"
MODEL_TRAINING_AUTHORIZED = False
WEIGHT_MUTATION_AUTHORIZED = False


def _hash(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class NeuralSubstrate(StrEnum):
    ATTENTION = "ATTENTION"
    EXTERNAL_MEMORY = "EXTERNAL_MEMORY"
    TEST_TIME_NEURAL_MEMORY = "TEST_TIME_NEURAL_MEMORY"
    STATE_SPACE = "STATE_SPACE"
    SPARSE_MOE = "SPARSE_MOE"
    JEPA_WORLD_MODEL = "JEPA_WORLD_MODEL"
    TEMPORAL_SYNCHRONY = "TEMPORAL_SYNCHRONY"
    MULTI_TOKEN_PREDICTION = "MULTI_TOKEN_PREDICTION"
    DISTILLATION = "DISTILLATION"


class NeuralMaturity(StrEnum):
    REUSE_RUNTIME = "REUSE_RUNTIME"
    PROVIDER_CAPABILITY = "PROVIDER_CAPABILITY"
    RESEARCH_OPTION = "RESEARCH_OPTION"
    TRAINING_GATED = "TRAINING_GATED"


@dataclass(frozen=True, slots=True)
class NeuralGene:
    substrate: NeuralSubstrate
    role: str
    maturity: NeuralMaturity
    proof_refs: tuple[str, ...]
    weight_change_required: bool

    def validate(self) -> "NeuralGene":
        if not self.role.strip() or not self.proof_refs:
            raise ValueError("FASCG_NEURAL_GENE_PROOF_REQUIRED")
        if self.weight_change_required and self.maturity not in {NeuralMaturity.TRAINING_GATED, NeuralMaturity.RESEARCH_OPTION}:
            raise ValueError("FASCG_NEURAL_WEIGHT_CHANGE_MATURITY_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class NeuralPortfolio:
    genes: tuple[NeuralGene, ...]
    portfolio_sha256: str


def default_portfolio() -> NeuralPortfolio:
    genes = (
        NeuralGene(NeuralSubstrate.ATTENTION, "precise working context", NeuralMaturity.REUSE_RUNTIME, ("frontier-transformer-runtime",), False),
        NeuralGene(NeuralSubstrate.EXTERNAL_MEMORY, "durable episodic/semantic memory", NeuralMaturity.REUSE_RUNTIME, ("BMF", "AgentCore-memory",), False),
        NeuralGene(NeuralSubstrate.TEST_TIME_NEURAL_MEMORY, "surprise-gated learned memory", NeuralMaturity.RESEARCH_OPTION, ("Titans-research",), True),
        NeuralGene(NeuralSubstrate.STATE_SPACE, "efficient long-sequence recurrence", NeuralMaturity.PROVIDER_CAPABILITY, ("Nemotron3-Mamba",), False),
        NeuralGene(NeuralSubstrate.SPARSE_MOE, "specialist expert routing", NeuralMaturity.PROVIDER_CAPABILITY, ("Nemotron3-LatentMoE",), False),
        NeuralGene(NeuralSubstrate.JEPA_WORLD_MODEL, "predictive latent world representation", NeuralMaturity.RESEARCH_OPTION, ("V-JEPA2",), True),
        NeuralGene(NeuralSubstrate.TEMPORAL_SYNCHRONY, "timing-sensitive cognition", NeuralMaturity.RESEARCH_OPTION, ("Sakana-CTM",), True),
        NeuralGene(NeuralSubstrate.MULTI_TOKEN_PREDICTION, "agent throughput acceleration", NeuralMaturity.PROVIDER_CAPABILITY, ("Nemotron3-MTP",), False),
        NeuralGene(NeuralSubstrate.DISTILLATION, "cross-model capability transfer", NeuralMaturity.TRAINING_GATED, ("multi-teacher-distillation",), True),
    )
    for gene in genes:
        gene.validate()
    body = [(g.substrate.value, g.role, g.maturity.value, g.proof_refs, g.weight_change_required) for g in genes]
    return NeuralPortfolio(genes, _hash(body))


@dataclass(frozen=True, slots=True)
class NeuralRequirement:
    required_roles: tuple[str, ...]
    allow_training: bool = False


@dataclass(frozen=True, slots=True)
class NeuralSelection:
    selected_substrates: tuple[str, ...]
    blocked_roles: tuple[str, ...]
    selection_sha256: str


def select_portfolio(requirement: NeuralRequirement, portfolio: NeuralPortfolio | None = None) -> NeuralSelection:
    p = portfolio or default_portfolio()
    wanted = {r.casefold() for r in requirement.required_roles}
    selected = []
    blocked = []
    for role in requirement.required_roles:
        matches = [g for g in p.genes if role.casefold() in g.role.casefold()]
        if not matches:
            blocked.append(role)
            continue
        eligible = [g for g in matches if requirement.allow_training or not g.weight_change_required]
        if not eligible:
            blocked.append(role)
            continue
        selected.append(eligible[0].substrate.value)
    body = {"selected": sorted(set(selected)), "blocked": sorted(set(blocked)), "allow_training": requirement.allow_training}
    return NeuralSelection(tuple(body["selected"]), tuple(body["blocked"]), _hash(body))


__all__ = ["NeuralSubstrate", "NeuralMaturity", "NeuralGene", "NeuralPortfolio", "default_portfolio", "NeuralRequirement", "NeuralSelection", "select_portfolio"]
