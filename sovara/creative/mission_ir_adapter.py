from __future__ import annotations

from federation.mission_ir import ContextBudgetIR, MissionIR

from .genome import CreativeMissionGenome


def compile_creative_mission_ir(
    genome: CreativeMissionGenome,
    *,
    source_frontier: str,
    outcome_contract: str,
    proof_requirements: tuple[str, ...],
    authority_requirements: tuple[str, ...] = (),
    effect_class: str = "NO_EFFECT",
    provider_allowlist: tuple[str, ...] = (),
    provider_denylist: tuple[str, ...] = (),
    failure_domain_exclusions: tuple[str, ...] = (),
    value_metrics: tuple[str, ...] = (
        "owner_interventions",
        "owner_minutes",
        "latency_ms",
        "qa_result",
    ),
    context_budget: ContextBudgetIR | None = None,
    max_cost_microunits: int | None = None,
    latency_target_ms: int | None = None,
    rollback_required: bool = True,
) -> MissionIR:
    """Compile SOVARA's domain-rich genome into the shared execution contract.

    The genome remains canonical for creative semantics. The adapter adds no
    provider/effect authority. OWNER_RELEASE is carried as a requirement when
    the creative mission already requires owner approval.
    """

    authorities = set(authority_requirements)
    if genome.owner_approval_required:
        authorities.add("OWNER_RELEASE")

    ir = MissionIR(
        mission_id=genome.mission_id,
        objective=genome.objective,
        domain="SOVARA_CREATIVE",
        outcome_contract=outcome_contract,
        source_frontier=source_frontier,
        privacy_class=genome.privacy_class.value,
        rights_state=genome.rights_state.value,
        effect_class=effect_class,
        owner_approval_required=genome.owner_approval_required,
        rollback_required=rollback_required,
        authority_requirements=tuple(authorities),
        proof_requirements=proof_requirements,
        provider_allowlist=provider_allowlist,
        provider_denylist=provider_denylist,
        failure_domain_exclusions=failure_domain_exclusions,
        value_metrics=value_metrics,
        context_budget=context_budget or ContextBudgetIR(),
        max_cost_microunits=max_cost_microunits,
        latency_target_ms=latency_target_ms,
        metadata={
            "content_class": genome.content_class.value,
            "required_modalities": ",".join(genome.required_modalities),
            "target_channels": ",".join(genome.target_channels),
            "compiler": "SOVARA-CREATIVE-MISSION-IR-ADAPTER-V1",
        },
    ).normalized()
    ir.validate()
    return ir
