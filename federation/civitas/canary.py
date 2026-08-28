from __future__ import annotations

"""Deterministic integrated canary for Federation Ω CIVITAS."""

from dataclasses import asdict
from typing import Any

from .adapters import ProviderReadbackAdapter, RawObservation, SourceReadbackAdapter
from .causal import CausalClaim, CausalFederationTwin, CausalObservation, ExperimentCandidate
from .civilization import CompoundingStage, CivilizationFabric, SuccessionPlan
from .civitas import InstitutionalConstitution, MissionRole, CivitasInstitution
from .contracts import (
    AssuranceVote,
    AuthorityClass,
    CapabilityDescriptor,
    CivitasError,
    FitnessVector,
    MaturityEvidence,
    MaturityStage,
    ObjectiveVector,
    ProofLevel,
    ProofRef,
    ResourceBudget,
    ResourceDemand,
    VoteState,
    digest,
)
from .ecology import CapabilityGenePacket, CognitiveEcologyMarket, CognitiveInstitution, RouteBid
from .genesis import ArchitectureGenomeRegistry, CapabilityFoundry, EngineeringGene, GenesisStage, ProductGenome
from .metabolism import FeatureRent, FederationMetabolism, MissionCandidate, StrategicPortfolioBrain
from .service import FederationCivitasService
from .suite import FederationCivitasSuite


def _proof(
    proof_ref: str,
    *,
    level: ProofLevel = ProofLevel.DETERMINISTIC_TESTED,
    source: str = "CANARY",
    independent: str | None = None,
) -> ProofRef:
    return ProofRef(
        source_ref=source,
        proof_ref=proof_ref,
        observed_at="2026-08-28T06:00:00+00:00",
        level=level,
        confidence=0.95,
        ttl_seconds=7200,
        independent_source=independent or source,
    )


def _fitness(*, quality: float, learning: float, resilience: float, complexity: float, owner_load: float) -> FitnessVector:
    return FitnessVector(
        truth=0.95,
        proof=0.92,
        safety=0.96,
        privacy=0.96,
        owner_control=0.95,
        continuity=0.90,
        quality=quality,
        resilience=resilience,
        cost_efficiency=0.80,
        latency_efficiency=0.80,
        owner_load=owner_load,
        learning=learning,
        complexity=complexity,
    )


def run_civitas_canary() -> dict[str, Any]:
    checks: dict[str, bool] = {}

    # Causal Twin
    twin = CausalFederationTwin()
    twin.register_claim(CausalClaim("CLAIM:1", "PROOF_DECAY", "ROUTE_FAILURE", "stale proof causes invalid route selection", "refresh proof without changing route"))
    twin.observe(CausalObservation("OBS:1", "CLAIM:1", _proof("p1", source="SENTINEL", independent="SENTINEL"), True, True, True, True, True, 0.7))
    twin.observe(CausalObservation("OBS:2", "CLAIM:1", _proof("p2", source="JARVIS", independent="JARVIS"), True, True, False, True, True, 0.6))
    causal = twin.assess("CLAIM:1")
    checks["causal_requires_independent_replication"] = causal.causal_write_permitted and len(causal.independent_sources) == 2
    checks["causal_state_replicated"] = causal.state.value == "REPLICATED"
    checks["causal_event_chain_verified"] = twin.verify_event_chain()
    twin.add_dependency("MISSION:1", "ROUTE:1")
    twin.add_dependency("ROUTE:1", "PROVIDER:1")
    impact = twin.counterfactual_impact(("PROVIDER:1",))
    checks["counterfactual_detects_blast_radius"] = impact.blast_radius == 2
    checks["counterfactual_is_not_causal_claim"] = impact.topology_only and not impact.causal_claim
    experiment = twin.design_experiment((
        ExperimentCandidate("EXP:SAFE", "CLAIM:1", "refresh proof in shadow", 0.9, 0.9, 1.0, 0.8, 0.1, 0.1, "exp-proof"),
        ExperimentCandidate("EXP:EFFECT", "CLAIM:1", "change provider", 1.0, 1.0, 0.3, 0.8, 0.5, 0.5, "effect-proof", True),
    ))
    checks["experiment_prefers_reversible_internal"] = experiment.selected_experiment_id == "EXP:SAFE"
    checks["effectful_experiment_rejected"] = "EXP:EFFECT" in experiment.rejected_ids
    checks["experiment_does_not_promote_causation"] = not experiment.causal_promotion
    precursor = twin.precursor_signals("ROUTE:1", (
        CausalObservation("OBS:P1", "CLAIM:1", _proof("pr1", source="A", independent="A")),
        CausalObservation("OBS:P2", "CLAIM:1", _proof("pr2", source="B", independent="B")),
    ))
    checks["precursor_signal_requires_distinct_sources"] = len(precursor) == 1 and not precursor[0].causal_claim

    # Strategic metabolism and portfolio
    metabolism = FederationMetabolism(ResourceBudget(10, 100, 10, 100, 10, 10, 100, 0.10))
    brain = StrategicPortfolioBrain(metabolism)
    shared = ("CAPABILITY:IDENTITY",)
    mission_a = MissionCandidate(
        "MISSION:A", "build shared identity verifier",
        ObjectiveVector(0.9, 0.8, 1.0, 0.8, 1.0, 0.9, 0.2, 0.2, 0.1, 1.0, "STRATEGIC"),
        ResourceDemand(2, 10, 1, 10, 1, 2, 5), _proof("mission-a"), unlocks=shared,
    )
    mission_b = MissionCandidate(
        "MISSION:B", "use shared identity verifier",
        ObjectiveVector(0.8, 0.6, 0.8, 0.6, 0.8, 0.8, 0.2, 0.2, 0.1, 1.0),
        ResourceDemand(1, 5, 0, 5, 0.5, 1, 2), _proof("mission-b"), unlocks=shared,
    )
    mission_c = MissionCandidate(
        "MISSION:C", "unproven provider mutation",
        ObjectiveVector(1.0, 1.0, 0.2, 0.2, 0.1, 0.3, 0.9, 0.9, 0.9, 0.1),
        ResourceDemand(20, 200, 20, 200, 20, 20, 200), _proof("mission-c", level=ProofLevel.DECLARED), hard_blockers=("PROVIDER_AUTHORITY",),
    )
    portfolio = brain.compile((mission_a, mission_b, mission_c))
    checks["strategic_portfolio_selects_admissible"] = {item.mission_id for item in portfolio.selected} == {"MISSION:A", "MISSION:B"}
    checks["strategic_portfolio_holds_unproven"] = {item.mission_id for item in portfolio.held} == {"MISSION:C"}
    checks["shared_dependency_unlock_detected"] = portfolio.shared_unlocks == shared
    checks["reserve_is_protected"] = portfolio.reserve.compute == 1.0 and portfolio.reserve.owner_attention == 1.0
    checks["owner_attention_is_resource"] = metabolism.remaining.owner_attention < 9.0
    rent = FeatureRent("FEATURE:1", 0.9, 0.8, 0.8, 0.7, 0.2, 0.1, 0.1, 0.1, ("rent-proof",))
    checks["feature_pays_rent"] = FederationMetabolism.feature_rent(rent).disposition == "KEEP_AND_MEASURE"

    # Capability genesis and product genome
    genomes = ArchitectureGenomeRegistry()
    genomes.register_gene(EngineeringGene("GENE:PROOF", "proof integrity", "independent readback", ("receipt",), (), ("truth",), ("cost",), ("self-attestation",), "restore incumbent", ("gene-proof",)))
    genomes.register_genome(ProductGenome("GENOME:ASSURANCE", "assurance service", ("GENE:PROOF",), ("query",), ("independent receipt",), ("rollback",), ("proof-before-claim",), ("genome-proof",)))
    foundry = CapabilityFoundry(genomes)
    existing_capability = CapabilityDescriptor("CAP:EXISTING", "assurance", ("proof", "readback"), _proof("cap-proof"), reliability=0.9)
    candidate, foundry_decision = foundry.open_candidate(
        candidate_id="CANDIDATE:1", capability_name="assurance service", objective="independent assurance",
        required_tags=("proof", "readback"), available_capabilities=(existing_capability,), proof_ref="reuse-proof",
    )
    checks["foundry_reuses_before_build"] = candidate.reused_capability_id == "CAP:EXISTING" and foundry_decision.disposition == "REUSE_EXTEND_FIRST"
    foundry.advance("CANDIDATE:1", GenesisStage.REQUIREMENTS, evidence_refs=("requirements",))
    foundry.advance("CANDIDATE:1", GenesisStage.ARCHITECTURE, evidence_refs=("architecture",), architecture_genome_id="GENOME:ASSURANCE")
    foundry.advance("CANDIDATE:1", GenesisStage.IMPLEMENTED, evidence_refs=("implementation",))
    foundry.advance("CANDIDATE:1", GenesisStage.TESTED, evidence_refs=("tests",), regression_passed=True)
    foundry.advance("CANDIDATE:1", GenesisStage.RED_TEAMED, evidence_refs=("red-team",), independent_verifier=True)
    foundry.advance("CANDIDATE:1", GenesisStage.SHADOW, evidence_refs=("shadow",), rollback_ready=True)
    foundry.advance("CANDIDATE:1", GenesisStage.VALUE_VERIFIED, evidence_refs=("value",), value_delta=0.25)
    promoted = foundry.advance("CANDIDATE:1", GenesisStage.PROMOTION_ELIGIBLE, evidence_refs=("promotion",))
    checks["genesis_strict_lifecycle_reaches_eligibility"] = promoted.stage == GenesisStage.PROMOTION_ELIGIBLE
    checks["genesis_promotion_has_positive_value"] = promoted.value_delta == 0.25
    checks["genesis_promotion_receipt_effect_free"] = foundry.promotion_receipt("CANDIDATE:1")["external_effects"] == 0
    stage_skip_blocked = False
    second, _ = foundry.open_candidate(candidate_id="CANDIDATE:2", capability_name="new", objective="new", required_tags=("x",), available_capabilities=(), proof_ref="open")
    try:
        foundry.advance(second.candidate_id, GenesisStage.IMPLEMENTED, evidence_refs=("bad",))
    except CivitasError:
        stage_skip_blocked = True
    checks["genesis_stage_skipping_blocked"] = stage_skip_blocked

    # CIVITAS organization and court
    institution = CivitasInstitution(InstitutionalConstitution("CONST:1", "OWNER", "mission institution"))
    capabilities = (
        CapabilityDescriptor("CAP:RESEARCH", "research", ("research", "evidence"), _proof("research-proof", source="RESEARCH"), failure_domains=("FD:R",), reliability=0.9),
        CapabilityDescriptor("CAP:VERIFY", "verify", ("verification", "assurance"), _proof("verify-proof", source="VERIFY"), failure_domains=("FD:V",), reliability=0.9),
    )
    roles = (
        MissionRole("ROLE:RESEARCH", "research", ("research",)),
        MissionRole("ROLE:VERIFY", "verify", ("verification",), independent_from=("ROLE:RESEARCH",)),
    )
    votes = tuple(AssuranceVote(role, role, VoteState.PASS, (f"{role}-proof",), "pass", True, False) for role in ("JARVIS", "CFBE", "SENTINEL", "REALITYGUARD"))
    institution_receipt = institution.prepare_mission(mission_id="MISSION:INST", organization_id="ORG:1", roles=roles, capabilities=capabilities, votes=votes)
    checks["temporary_organization_compiled"] = set(institution_receipt.selected_ids) == {"CAP:RESEARCH", "CAP:VERIFY"}
    checks["constitutional_court_passes_four_roles"] = institution_receipt.disposition.value == "SELECT"
    executor_vote = list(votes)
    executor_vote[0] = AssuranceVote("EXECUTOR", "JARVIS", VoteState.PASS, ("self",), "self", True, True)
    self_receipt = institution.prepare_mission(mission_id="MISSION:SELF", organization_id="ORG:SELF", roles=roles, capabilities=capabilities, votes=tuple(executor_vote))
    checks["executor_self_certification_blocked"] = self_receipt.disposition.value == "HOLD"

    # Ω-ECOLOGY market and gene exchange
    institutions = (
        CognitiveInstitution("INST:A", "research", _proof("inst-a", source="A"), failure_domains=("FD:A",), health=0.9),
        CognitiveInstitution("INST:B", "verification", _proof("inst-b", source="B"), failure_domains=("FD:B",), health=0.9),
        CognitiveInstitution("INST:C", "unproven", _proof("inst-c", level=ProofLevel.DECLARED, source="C"), failure_domains=("FD:C",), health=0.9),
    )
    market = CognitiveEcologyMarket(institutions)
    bids = (
        RouteBid("BID:A", "INST:A", "MISSION:MARKET", 0.9, 0.9, 0.9, 0.9, 0.8, 0.8, 0.9, 0.2, 0.2, 0.2, 0.1, "bid-a", True, ("FD:A",)),
        RouteBid("BID:B", "INST:B", "MISSION:MARKET", 0.8, 0.8, 0.8, 0.85, 0.9, 1.0, 0.9, 0.2, 0.2, 0.2, 0.1, "bid-b", True, ("FD:B",)),
        RouteBid("BID:C", "INST:C", "MISSION:MARKET", 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0, 0, 0, 0, "bid-c", True, ("FD:C",)),
    )
    award = market.award("MISSION:MARKET", bids)
    checks["eligibility_beats_raw_score"] = award.champion_bid_id == "BID:A" and "BID:C" in award.rejected_bid_ids
    checks["diverse_shadow_selected"] = award.shadow_bid_ids == ("BID:B",)
    checks["market_has_no_hidden_spof"] = award.hidden_spofs == ()
    packet = CapabilityGenePacket("PACKET:1", "INST:A", "proof integrity", "independent readback", ("receipt",), (), ("quality",), ("cost",), ("self-attestation",), "rollback", ("packet-proof",), 0.9)
    adoption = market.adoption_decision(packet, "INST:B", receiver_compatible=True, receiver_current_proof=_proof("receiver-proof", source="B"))
    checks["gene_exchange_is_sanitized"] = not packet.private_payload_included and not packet.provider_credentials_included and not packet.maturity_transferred
    checks["receiver_local_shadow_required"] = adoption.disposition == "ADAPT_IN_LOCAL_SHADOW" and adoption.local_proof_required and adoption.rollback_required

    # Ω-CIVILIZATION compounding and succession
    civilization = CivilizationFabric()
    civilization.open_cycle("CYCLE:1", "reduce owner burden", ("need-proof",))
    civilization.advance("CYCLE:1", CompoundingStage.DISCOVER, proof_refs=("discover",))
    civilization.advance("CYCLE:1", CompoundingStage.COMPOSE, proof_refs=("compose",), capability_ids=("CAP:A", "CAP:B"))
    civilization.advance("CYCLE:1", CompoundingStage.BUILD, proof_refs=("build",))
    civilization.advance("CYCLE:1", CompoundingStage.TEST, proof_refs=("test",), regression_passed=True)
    civilization.advance("CYCLE:1", CompoundingStage.SHADOW, proof_refs=("shadow",), rollback_ready=True)
    civilization.advance("CYCLE:1", CompoundingStage.MEASURE, proof_refs=("measure",), independent_assurance=True, measured_value=0.3)
    civilization.advance("CYCLE:1", CompoundingStage.GENERALIZE, proof_refs=("generalize",), generalized_gene_ref="GENE:1")
    civilization.advance("CYCLE:1", CompoundingStage.DIFFUSE, proof_refs=("diffuse",), receiver_proof_refs=("receiver-a",))
    civilization.advance("CYCLE:1", CompoundingStage.IMPROVE_IMPROVEMENT, proof_refs=("meta",), improvement_mechanism_proof="meta-proof")
    closed = civilization.advance("CYCLE:1", CompoundingStage.CLOSED_VERIFIED, proof_refs=("closure",))
    checks["capability_compounding_loop_closed"] = closed.stage == CompoundingStage.CLOSED_VERIFIED
    checks["compounding_closure_effect_free"] = civilization.closure_receipt("CYCLE:1")["external_effects"] == 0
    anti_entropy = civilization.anti_entropy_gate(
        "CYCLE:1",
        _fitness(quality=0.70, learning=0.70, resilience=0.70, complexity=0.40, owner_load=0.70),
        _fitness(quality=0.85, learning=0.88, resilience=0.82, complexity=0.42, owner_load=0.82),
    )
    checks["anti_entropy_gate_passes_compounding_gain"] = anti_entropy.disposition == "PASS_ANTI_ENTROPY"
    checks["anti_entropy_preserves_hard_vetoes"] = anti_entropy.hard_veto_pass and not anti_entropy.material_regressions
    succession = civilization.succession(SuccessionPlan("PLAN:1", "OLD", "NEW", ("archive",), ("rollback",), ("successor",), True, True, True, True, True))
    checks["succession_is_archive_first"] = succession.archive_first and succession.predecessor_retirement_eligible
    checks["succession_never_deletes"] = not succession.deletion_permitted

    # Proof-preserving adapters
    source_raw = RawObservation("EVENT:SOURCE", "github", "source-proof", "2026-08-28T06:00:00+00:00", ProofLevel.SOURCE_READBACK, "NODE_STATE", "SYSTEM:X", "SYSTEM", "READY", {"label": "X"})
    normalized, adapter_receipt = SourceReadbackAdapter().normalize(source_raw)
    checks["adapter_preserves_source_proof"] = normalized.proof_level == ProofLevel.SOURCE_READBACK and adapter_receipt.proof_preserved
    provider_raw = RawObservation("EVENT:PROVIDER", "provider", "provider-proof", "2026-08-28T06:00:00+00:00", ProofLevel.PROVIDER_READBACK, "NODE_STATE", "PROVIDER:X", "PROVIDER", "READY", {"label": "P"}, provider_native=True)
    provider_normalized, _ = ProviderReadbackAdapter().normalize(provider_raw)
    checks["provider_adapter_requires_provider_proof"] = provider_normalized.provider_native and provider_normalized.proof_level == ProofLevel.PROVIDER_READBACK
    mismatch_blocked = False
    try:
        ProviderReadbackAdapter().normalize(RawObservation("EVENT:MISMATCH", "p", "p", "2026-08-28T06:00:00+00:00", ProofLevel.DECLARED, "NODE_STATE", "P:Y", "PROVIDER", "READY", {}, provider_native=True))
    except CivitasError:
        mismatch_blocked = True
    checks["provider_provenance_mismatch_blocked"] = mismatch_blocked

    # Suite, catalog, maturity and local service
    suite = FederationCivitasSuite()
    manifest = suite.manifest()
    checks["suite_has_twelve_services"] = manifest["service_count"] == 12
    checks["suite_has_eight_product_bundles"] = manifest["product_count"] == 8
    checks["manifest_authority_ceiling_internal"] = manifest["authority_ceiling"] == "A1_INTERNAL"
    checks["operator_query_explains_maturity"] = suite.query("what is the current maturity?")["fully_established"] is False
    runtime_proof = _proof("runtime-readback", level=ProofLevel.RUNTIME_READBACK, source="LOCAL_RUNTIME")
    deployment = suite.shadow_deploy(MaturityEvidence(
        suite.SUITE_ID,
        MaturityStage.RUNTIME_READBACK,
        (runtime_proof,),
        tests_passed=True,
        shadow_passed=True,
        runtime_readback=True,
        independent_assurance=True,
    ))
    checks["shadow_deployment_runtime_readback"] = deployment.justified_maturity == MaturityStage.RUNTIME_READBACK.value
    checks["shadow_deployment_not_provider_runtime"] = not deployment.provider_runtime_proven
    inflated = False
    try:
        suite.shadow_deploy(MaturityEvidence(suite.SUITE_ID, MaturityStage.FULLY_ESTABLISHED, (runtime_proof,), tests_passed=True, shadow_passed=True, runtime_readback=True, independent_assurance=True))
    except CivitasError:
        inflated = True
    checks["maturity_inflation_blocked"] = inflated
    service = FederationCivitasService(suite)
    health = service.health()
    checks["local_service_health_passes"] = health["status"] == "PASS" and health["service_count"] == 12
    checks["local_service_is_loopback_shadow"] = health["mode"] == "INTERNAL_SHADOW" and not health["provider_runtime_proven"]
    checks["local_catalog_readback_complete"] = len(service.catalog()["services"]) == 12 and len(service.catalog()["products"]) == 8

    # Global invariants
    checks["zero_external_effects"] = all(
        item.external_effects == 0
        for item in (causal, impact, experiment, portfolio, institution_receipt, award, adoption, closed, anti_entropy, succession, normalized, provider_normalized, deployment)
    )
    checks["no_authority_created"] = not deployment.authority_created and not normalized.authority_created and not provider_normalized.authority_created
    checks["canary_has_exactly_46_controls"] = len(checks) == 46

    status = "PASS" if len(checks) == 46 and all(checks.values()) else "FAIL"
    body = {
        "schema": "FEDERATION-OMEGA-CIVITAS-INTEGRATED-CANARY-V1",
        "status": status,
        "count": len(checks),
        "checks": checks,
        "service_count": manifest["service_count"],
        "product_count": manifest["product_count"],
        "external_effects": 0,
        "truth_boundary": {
            "source_and_tests_are_not_provider_deployment": True,
            "local_loopback_runtime_is_not_provider_runtime": True,
            "causal_simulation_is_not_causal_fact": True,
            "foundry_promotion_eligibility_is_not_provider_effect_admission": True,
            "provider_runtime_proven": False,
            "fully_established": False,
        },
    }
    return {**body, "receipt_sha256": digest(body)}


__all__ = ["run_civitas_canary"]
