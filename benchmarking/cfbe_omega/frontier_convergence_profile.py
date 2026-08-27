from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .benchmark_engine import Dimension, EVIDENCE_FACTORS, weighted_score, leadership_state


PROFILE_ID = "CFBE-FRONTIER-CONVERGENCE-001"
CURRENT_SOURCE_MERGE = "723fccc904f2160bf325a289beab5e8139862e15"
CURRENT_RUNTIME_MERGE = "d889885071d2984816e67d9b553ecb4377fc3920"
CURRENT_EVIDENCE_STATE = "DETERMINISTIC_CI_BOUNDED_RUNTIME"
CURRENT_EVIDENCE_FACTOR = EVIDENCE_FACTORS[CURRENT_EVIDENCE_STATE]


@dataclass(frozen=True)
class FrontierProof:
    proof_id: str
    state: str
    receiver: str
    provider_native: bool = False
    independent_readback: bool = False


@dataclass(frozen=True)
class FrontierBindingReport:
    profile_id: str
    raw_architecture: float
    proof_adjusted: float
    leadership: str
    gemini_canary_verified: bool
    workspace_bidirectional_verified: bool
    production_qualified: bool
    source_merge: str
    runtime_merge: str


# The current raw architecture profile records implemented contracts only.
# Provider-live dimensions deliberately receive low raw scores until execution
# proof exists. Evidence factors are receiver-local and never inherited from a
# sibling SOVARA provider cell or aggregate status line.
_BASE_DIMENSIONS = (
    ("mission_sovereignty", "Mission sovereignty and exact-effect control", 15.0, 5.0),
    ("provider_neutrality", "Provider-neutral routing and capability leases", 12.0, 5.0),
    ("scenario_robustness", "Scenario branching and robustness court", 10.0, 5.0),
    ("continuity", "Durable execution continuity and payload governance", 12.0, 5.0),
    ("identity_gateway", "Agent identity and sovereign tool gateway contract", 12.0, 4.0),
    ("telemetry_control_tower", "Unified telemetry, control tower and provenance", 12.0, 4.0),
    ("gemini_provider", "Gemini provider-native semantic execution", 15.0, 1.0),
    ("workspace_bidirectional", "Bidirectional Workspace exact-effect proof", 12.0, 1.0),
)


def _proof_map(proofs: Iterable[FrontierProof]) -> Mapping[str, FrontierProof]:
    mapped: dict[str, FrontierProof] = {}
    for proof in proofs:
        if proof.receiver in mapped:
            raise ValueError(f"duplicate receiver proof: {proof.receiver}")
        mapped[proof.receiver] = proof
    return mapped


def compile_dimensions(proofs: Iterable[FrontierProof] = ()) -> list[Dimension]:
    proof_by_receiver = _proof_map(proofs)
    dims: list[Dimension] = []
    for dimension_id, name, weight, raw_score in _BASE_DIMENSIONS:
        factor = CURRENT_EVIDENCE_FACTOR
        receiver_proof = proof_by_receiver.get(dimension_id)
        if dimension_id in {"gemini_provider", "workspace_bidirectional"}:
            # Source/runtime controls do not prove provider execution.
            factor = EVIDENCE_FACTORS["PLANNED_OR_CLAIMED"]
            if receiver_proof:
                if receiver_proof.state not in EVIDENCE_FACTORS:
                    raise ValueError(f"unknown evidence state: {receiver_proof.state}")
                if receiver_proof.state == "PROVIDER_LIVE_INDEPENDENT_READBACK":
                    if not receiver_proof.provider_native or not receiver_proof.independent_readback:
                        raise ValueError("provider-live evidence requires provider-native independent readback")
                factor = EVIDENCE_FACTORS[receiver_proof.state]
        dims.append(
            Dimension(
                dimension_id=dimension_id,
                name=name,
                weight=weight,
                raw_score=raw_score,
                evidence_factor=factor,
            )
        )
    return dims


def evaluate(proofs: Iterable[FrontierProof] = ()) -> FrontierBindingReport:
    proof_list = list(proofs)
    proof_by_receiver = _proof_map(proof_list)
    score = weighted_score(compile_dimensions(proof_list))

    gemini = proof_by_receiver.get("gemini_provider")
    workspace = proof_by_receiver.get("workspace_bidirectional")
    gemini_verified = bool(
        gemini
        and gemini.state == "PROVIDER_LIVE_INDEPENDENT_READBACK"
        and gemini.provider_native
        and gemini.independent_readback
    )
    workspace_verified = bool(
        workspace
        and workspace.state == "PROVIDER_LIVE_INDEPENDENT_READBACK"
        and workspace.provider_native
        and workspace.independent_readback
    )
    production_qualified = gemini_verified and workspace_verified

    leadership = leadership_state(
        score.proof_adjusted,
        85.0,
        provider_live=production_qualified,
        independently_replicated=False,
        no_critical_regression=True,
        externally_distinguishable_advantage=False,
    )

    return FrontierBindingReport(
        profile_id=PROFILE_ID,
        raw_architecture=score.raw_architecture,
        proof_adjusted=score.proof_adjusted,
        leadership=leadership,
        gemini_canary_verified=gemini_verified,
        workspace_bidirectional_verified=workspace_verified,
        production_qualified=production_qualified,
        source_merge=CURRENT_SOURCE_MERGE,
        runtime_merge=CURRENT_RUNTIME_MERGE,
    )
