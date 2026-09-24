from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from federation.astra_max_algorithm_genome_v1 import (
    ASTRA_GENES,
    OFFICIAL_PUBLIC_SOURCES,
    select_astra_genes,
)
from sol_61_runtime.sol_62_frontier_primitives import digest

SCHEMA = "SOL62_ASTRA_MAX_COMPOSITE_V1"
VERSION = "1.0.0"

HARD_BOUNDARIES = (
    "AUTHORIZATION",
    "PRIVACY",
    "LEGAL",
    "SAFETY",
    "EFFECT_AUTHORITY",
    "SOURCE_FENCE",
    "BUDGET",
)


@dataclass(frozen=True, slots=True)
class AstraMissionProfile:
    schema: str
    version: str
    profile_id: str
    objective: str
    capability_mode: str
    reasoning_effort: str
    max_parallel_lanes: int
    continue_independent_work_while_waiting: bool
    ask_only_material_questions: bool
    preserve_goal_under_steering: bool
    relevant_context_only: bool
    computer_use_strategy: tuple[str, ...]
    artifact_quality_gates: tuple[str, ...]
    verification_gates: tuple[str, ...]
    selected_genes: tuple[Mapping[str, Any], ...]
    preferred_surfaces: tuple[str, ...]
    astra_provider_preferred_when_qualified: bool
    provider_neutral_fallback: bool
    no_artificial_goal_dilution: bool
    no_artificial_local_throttles: bool
    hard_boundaries: tuple[str, ...]
    authority_expansion: bool
    safety_bypass: bool
    external_effect: bool

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["selected_genes"] = [dict(item) for item in self.selected_genes]
        return row


def _complexity_score(
    objective: str,
    *,
    constraints: Sequence[str],
    risk_class: str,
    consequential: bool,
) -> float:
    score = 0.35
    score += min(0.25, len(objective) / 8000.0)
    score += min(0.20, len(tuple(constraints)) * 0.04)
    if risk_class.upper() in {"HIGH", "CRITICAL", "R4", "R5"}:
        score += 0.15
    if consequential:
        score += 0.10
    return min(1.0, score)


def _reasoning_effort(complexity: float, *, consequential: bool) -> str:
    if consequential or complexity >= 0.85:
        return "max"
    if complexity >= 0.68:
        return "xhigh"
    if complexity >= 0.50:
        return "high"
    return "medium"


def _parallelism(complexity: float, *, consequential: bool) -> int:
    if consequential:
        return 3
    if complexity >= 0.75:
        return 8
    if complexity >= 0.55:
        return 6
    return 4


def compile_astra_max_profile(
    *,
    objective: str,
    constraints: Sequence[str] = (),
    preferred_surfaces: Sequence[str] = (),
    risk_class: str = "LOW",
    consequential: bool = False,
    astra_provider_available: bool = False,
    code_execution_available: bool = False,
    browser_control_available: bool = False,
    max_gene_count: int = 16,
) -> AstraMissionProfile:
    """Compile Astra-like public capability mechanisms into FUSE execution policy.

    This does not claim the current model is GPT-6 Astra. If Astra is actually
    callable, it becomes a preferred provider cell for task classes where it is
    qualified. Otherwise, the public mechanisms remain provider-neutral FUSE
    behavior and route through available models/tools.
    """
    objective = objective.strip()
    if not objective:
        raise ValueError("objective required")

    complexity = _complexity_score(
        objective,
        constraints=constraints,
        risk_class=risk_class,
        consequential=consequential,
    )
    effort = _reasoning_effort(complexity, consequential=consequential)
    parallel = _parallelism(complexity, consequential=consequential)

    gene_query = " ".join(
        [
            objective,
            " ".join(constraints),
            " ".join(preferred_surfaces),
            risk_class,
            "computer browser research coding professional artifact verify parallel",
        ]
    )
    genes = select_astra_genes(gene_query, limit=max_gene_count)

    computer_strategy: list[str] = []
    if code_execution_available:
        computer_strategy.append("CODE_EXECUTION_FIRST")
    if browser_control_available:
        computer_strategy.append("FUSE_BROWSER_CONTROL_PLANE")
    computer_strategy.extend(
        [
            "STRUCTURED_COMPUTER_TOOL_FALLBACK",
            "SEMANTIC_READBACK_REQUIRED",
            "UNKNOWN_EFFECT_READBACK_BEFORE_RETRY",
        ]
    )

    artifact_gates = (
        "TEMPLATE_AND_STYLE_MATCH",
        "STRUCTURE_AND_COMPLETENESS",
        "VISUAL_JUDGMENT_QA",
        "PROFESSIONAL_USABILITY",
        "DELIVERY_RECEIPT",
    )

    verification_gates = (
        "CURRENTNESS_CHECK",
        "UNSUPPORTED_ASSUMPTION_SCAN",
        "CONTRADICTION_SCAN",
        "SECOND_VERIFICATION_PASS",
        "SEMANTIC_RESULT_READBACK",
        "FALSE_GREEN_FALSIFIER",
    )

    preferred = list(dict.fromkeys(str(x) for x in preferred_surfaces if str(x)))
    if astra_provider_available:
        preferred.insert(0, "OPENAI_GPT_6_ASTRA")

    material = {
        "objective": objective,
        "constraints": list(constraints),
        "risk_class": risk_class,
        "consequential": consequential,
        "complexity": complexity,
        "reasoning_effort": effort,
        "parallel": parallel,
        "genes": [g.gene_id for g in genes],
        "preferred": preferred,
        "astra_provider_available": astra_provider_available,
    }
    profile_id = "ASTRA-MAX-" + digest(material)[:24].upper()

    return AstraMissionProfile(
        schema=SCHEMA,
        version=VERSION,
        profile_id=profile_id,
        objective=objective,
        capability_mode="MAXIMUM_AUTHORIZED_CAPABILITY",
        reasoning_effort=effort,
        max_parallel_lanes=parallel,
        continue_independent_work_while_waiting=True,
        ask_only_material_questions=True,
        preserve_goal_under_steering=True,
        relevant_context_only=True,
        computer_use_strategy=tuple(computer_strategy),
        artifact_quality_gates=artifact_gates,
        verification_gates=verification_gates,
        selected_genes=tuple(g.to_dict() for g in genes),
        preferred_surfaces=tuple(preferred),
        astra_provider_preferred_when_qualified=astra_provider_available,
        provider_neutral_fallback=True,
        no_artificial_goal_dilution=True,
        no_artificial_local_throttles=True,
        hard_boundaries=HARD_BOUNDARIES,
        authority_expansion=False,
        safety_bypass=False,
        external_effect=False,
    )


def runtime_contract() -> Mapping[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "capability_mode": "MAXIMUM_AUTHORIZED_CAPABILITY",
        "reasoning_effort_ceiling": "max",
        "computer_use_default_for_astra": "CODE_EXECUTION_FIRST",
        "provider_neutral_fallback": True,
        "continue_independent_work_while_waiting": True,
        "preserve_goal_under_steering": True,
        "relevant_context_only": True,
        "hard_boundaries": list(HARD_BOUNDARIES),
        "authority_expansion": False,
        "safety_bypass": False,
        "model_identity_claim": "NONE",
        "truth_boundary": (
            "ASTRA_PUBLIC_MECHANISM_BOUND_NE_ASTRA_MODEL_CALLABLE; "
            "ASTRA_MODEL_CALLABLE_NE_PROVIDER_EFFECT_AUTHORIZED; "
            "SOURCE_PROFILE_NE_RUNTIME_VERIFIED"
        ),
        "official_public_sources": list(OFFICIAL_PUBLIC_SOURCES),
        "gene_count": len(ASTRA_GENES),
    }
