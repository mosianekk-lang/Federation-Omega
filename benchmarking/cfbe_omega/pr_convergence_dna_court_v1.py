from __future__ import annotations

"""CFBE PR Capability-DNA + Semantic-Equivalence Court v1.

This is a thin, no-effect adapter over the admitted Wave-2 scientific capability
compiler.  It does not create another scheduler, authority plane, memory root,
provider executor, or maturity ladder.

Purpose:
- decompose high-entropy PRs into capability primitives;
- compare those primitives with the current admitted estate;
- distinguish REUSE/EXTEND/selective-harvest/provider-held work;
- prevent wholesale restacks of branches whose useful parts are already present.

The court is source/control evidence only.  It never merges/closes PRs, never
changes provider state, never authorizes external effects, and never upgrades
runtime or owner-value maturity.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Iterable

from benchmarking.cfbe_omega.scientific_capability_compiler_v2 import decompose_primitives

SCHEMA = "CFBE_PR_CAPABILITY_DNA_EQUIVALENCE_COURT_V1"
SOURCE_EPOCH = "62b6bccec96e39472997cf8620f7f151f2d91c75"

PR_HEADS = {
    1021: "f8443200b2d1125075c64b86d846a06d993bd752",
    1025: "e464c5a2ed42a7560e528d14d16f7ff8ca3ab4cb",
    1022: "476a3ad31b4f4d14a1c8416055dc78ee7898425e",
}


class CapabilityDisposition(str, Enum):
    REUSE = "REUSE"
    EXTEND = "EXTEND"
    SELECTIVE_HARVEST = "SELECTIVE_HARVEST"
    UNIQUE_RESTACK = "UNIQUE_RESTACK"
    PROVIDER_GATED_HOLD = "PROVIDER_GATED_HOLD"


class BranchDisposition(str, Enum):
    SPLIT_HARVEST_AND_REPAIR = "SPLIT_HARVEST_AND_REPAIR"
    SELECTIVE_HARVEST = "SELECTIVE_HARVEST"
    SUPERSEDE_AFTER_SELECTIVE_HARVEST = "SUPERSEDE_AFTER_SELECTIVE_HARVEST"


@dataclass(frozen=True, slots=True)
class CandidateCapability:
    capability_id: str
    pr_number: int
    objective: str
    primitives: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    provider_effect_required: bool = False
    workflow_or_provider_authority_surface: bool = False

    def validate(self) -> "CandidateCapability":
        if self.pr_number not in PR_HEADS:
            raise ValueError("CONVERGENCE_UNKNOWN_PR")
        if not self.capability_id or not self.objective or not self.primitives:
            raise ValueError("CONVERGENCE_CAPABILITY_IDENTITY_REQUIRED")
        if not self.evidence_refs:
            raise ValueError("CONVERGENCE_EVIDENCE_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class CapabilityCourtReceipt:
    capability_id: str
    pr_number: int
    overlap_ratio: float
    reused_primitives: tuple[str, ...]
    missing_primitives: tuple[str, ...]
    disposition: CapabilityDisposition
    evidence_refs: tuple[str, ...]
    provider_effect_authorized: bool = False
    stable_promotion_authorized: bool = False
    receipt_sha256: str = ""


@dataclass(frozen=True, slots=True)
class BranchCourtReceipt:
    pr_number: int
    head_sha: str
    candidate_count: int
    reuse_count: int
    extend_count: int
    selective_harvest_count: int
    unique_restack_count: int
    provider_hold_count: int
    branch_disposition: BranchDisposition
    provider_effect_authorized: bool = False
    stable_promotion_authorized: bool = False
    receipt_sha256: str = ""


# Current-main primitives are intentionally architectural capabilities rather than
# file names.  They are supported by current admitted source including SLOS 3.3,
# CFBE Wave 2, BCΩ-PRIME v4, the capability market, and the BCO->Modisa->SOL 6.1
# binding.  Absence from this set means "not proven equivalent in this court", not
# "the estate can never provide it".
ESTATE_PRIMITIVES = frozenset(
    {
        "mission_ir_compiler",
        "typed_dependency_dag",
        "dependency_safe_parallel_waves",
        "critical_path_extraction",
        "lane_priority_utility_ranking",
        "digital_twin",
        "risk_proof_authority_route_filtering",
        "counterfactual_no_action_baseline",
        "shadow_champion_challenger",
        "evidence_distillation",
        "opportunity_discovery",
        "capability_dna",
        "primitive_decomposition",
        "semantic_novelty",
        "capability_ecology",
        "cognitive_load_index",
        "information_gain_scheduler",
        "causal_attribution_graph",
        "counterfactual_challenger",
        "capability_authority_lattice",
        "cryptographic_execution_transcript",
        "agent_flight_recorder",
        "capability_market",
        "multi_timescale_planning",
        "owner_interrupt_policy",
        "owner_burden_measurement",
        "opportunity_exploitation",
        "new_build_reuse_gate",
        "capability_underuse_detection",
        "mission_authority_proof_gate",
        "durable_internal_commit",
        "provider_admission_separation",
        "token_bucket",
        "read_only_speculation_contract",
        "failure_lane_isolation",
        "recovery_checkpointing",
        "proof_before_promotion",
    }
)


CANDIDATES = (
    # PR 1021 — constitutional/security convergence.  Some primitives were
    # overtaken; others remain useful and should be split out rather than merged
    # as one stale constitutional stack.
    CandidateCapability(
        "P1021-CONSTITUTIONAL-ROLE-SEPARATION",
        1021,
        "One semantic mission owner, transactional execution kernel and separate provider-effect plane.",
        ("mission_authority_proof_gate", "durable_internal_commit", "provider_admission_separation", "duplicate_sovereign_rejection"),
        ("PR1021_BODY", "CURRENT_BCO_MODISA_SOL61_BINDING"),
    ),
    CandidateCapability(
        "P1021-SECURE-SERVICE-DEFAULT-DENY",
        1021,
        "Default-deny mutation service with short-lived request authentication.",
        ("default_deny_mutations", "short_lived_hmac", "trusted_provider_ingress", "mutation_request_authentication"),
        ("PR1021:superior_logic/secure_service.py", "PR1021:superior_logic/security.py"),
    ),
    CandidateCapability(
        "P1021-PROVIDER-ATTESTATION-STORE",
        1021,
        "Evidence-referenced expiring provider capability attestations for routing.",
        ("provider_capability_freshness", "attestation_expiry", "evidence_reference_binding", "risk_proof_authority_route_filtering"),
        ("PR1021:superior_logic/provider_attestations.py",),
    ),
    CandidateCapability(
        "P1021-CHANGE-IMPACT-CLASSIFIER",
        1021,
        "Classify source drift into ignore/retest/rebase actions.",
        ("source_delta_classification", "ignore_unrelated", "retest_only", "rebase_required"),
        ("PR1021:superior_logic/change_impact.py",),
    ),
    CandidateCapability(
        "P1021-EVIDENCE-DISTILLATION",
        1021,
        "Content-addressed bounded evidence receipts instead of raw control-plane payloads.",
        ("evidence_distillation",),
        ("PR1021:superior_logic/evidence_distillation.py", "MAIN:superior_logic/evidence_distillation.py"),
    ),
    CandidateCapability(
        "P1021-TRACE-SPINE",
        1021,
        "Mission-to-effect-to-readback trace lineage.",
        ("cryptographic_execution_transcript", "agent_flight_recorder", "provider_admission_separation", "semantic_readback_trace"),
        ("PR1021:superior_logic/trace.py", "MAIN:scientific_capability_compiler_v2"),
    ),
    CandidateCapability(
        "P1021-WIF-SUCCESS-CONSUMPTION-LEASE",
        1021,
        "Consume the WIF hardening lease only after a prior successful provider transaction.",
        ("one_use_effect_lease", "successful_run_history_fence", "already_consumed_no_effect_receipt", "provider_native_readback"),
        ("PR1021:.github/workflows/sol62-wif-hardening-lease.yml", "MAIN:.github/workflows/sol62-wif-hardening-lease.yml"),
        provider_effect_required=True,
        workflow_or_provider_authority_surface=True,
    ),
    CandidateCapability(
        "P1021-HERMETIC-PROOFOS-FALLBACK",
        1021,
        "Fail-closed hermetic ProofOS fallback when normal repository shell assumptions are unavailable.",
        ("hermetic_proof_fallback", "proof_scope_isolation", "fail_closed_drift", "proof_before_promotion"),
        ("PR1021:proofos_omega/hermetic.py", "PR1021:tests/test_proofos_hermetic_fallback.py"),
    ),

    # PR 1025 — most of the MissionIR/twin/evolution control plane is now on main
    # through SLOS 3.3, but runtime scheduling/execution deltas remain candidates.
    CandidateCapability(
        "P1025-MISSIONIR",
        1025,
        "Typed deterministic mission intermediate representation and dependency graph.",
        ("mission_ir_compiler", "typed_dependency_dag", "dependency_safe_parallel_waves"),
        ("PR1025:superior_logic/mission_ir.py", "MAIN:SLOS3.3"),
    ),
    CandidateCapability(
        "P1025-DIGITAL-TWIN",
        1025,
        "Capability/authority/proof/cost/risk digital twin route synthesis.",
        ("digital_twin", "risk_proof_authority_route_filtering", "counterfactual_no_action_baseline"),
        ("PR1025:superior_logic/digital_twin.py", "MAIN:SLOS3.3"),
    ),
    CandidateCapability(
        "P1025-CAPABILITY-GRAPH",
        1025,
        "Capability graph with conflict-domain and attestation-aware route selection.",
        ("digital_twin", "risk_proof_authority_route_filtering", "conflict_domain_graph", "provider_capability_freshness"),
        ("PR1025:superior_logic/capability_graph.py",),
    ),
    CandidateCapability(
        "P1025-CP-VOI-BOUNDED-BEAM",
        1025,
        "Critical-path and value-of-information bounded beam scheduling.",
        ("critical_path_extraction", "information_gain_scheduler", "bounded_beam_search", "conflict_domain_fencing"),
        ("PR1025:superior_logic/hyperperformance.py",),
    ),
    CandidateCapability(
        "P1025-TOKEN-BUCKET-FANOUT",
        1025,
        "Bound fan-out cost/compute through the existing token-bucket primitive.",
        ("token_bucket", "dependency_safe_parallel_waves"),
        ("PR1025:superior_logic/hyperperformance.py", "MAIN:sol_61_runtime.sol_62_frontier_primitives.TokenBucket"),
    ),
    CandidateCapability(
        "P1025-WORK-STEALING",
        1025,
        "Assign queued independent lanes to idle workers while respecting conflict domains.",
        ("work_stealing", "conflict_domain_fencing", "failure_lane_isolation"),
        ("PR1025:ParallelLaneScheduler.work_steal",),
    ),
    CandidateCapability(
        "P1025-ASYNC-PARALLEL-EXECUTOR",
        1025,
        "Actual provider-agnostic asyncio fan-out/fan-in for admitted lanes.",
        ("async_parallel_lane_execution", "dependency_safe_parallel_waves", "conflict_domain_fencing", "provider_admission_separation"),
        ("PR1025:ParallelLaneExecutor",),
    ),
    CandidateCapability(
        "P1025-SPECULATIVE-READ-RACE-HEDGE",
        1025,
        "Speculative route races and straggler hedges restricted to read-only work.",
        ("read_only_speculation_contract", "speculative_read_race", "straggler_hedging", "semantic_winner_fanin"),
        ("PR1025:ParallelLaneExecutor.race_read_routes", "PR1025:ParallelLaneExecutor.hedge_read_route"),
    ),
    CandidateCapability(
        "P1025-SHADOW-EVOLUTION",
        1025,
        "Common-mission champion/challenger evolution without execution authority.",
        ("shadow_champion_challenger", "proof_before_promotion"),
        ("PR1025:superior_logic/shadow_evolution.py", "MAIN:SLOS3.3"),
    ),

    # PR 1022 — institutional layer.  The branch packages many general Federation
    # capabilities under KDV-specific names; the court keeps only genuinely missing
    # institutional controls for selective harvest.
    CandidateCapability(
        "P1022-OBJECTIVE-ECOLOGY-RESOURCE-ECONOMY",
        1022,
        "Rank objectives, shared unlocks and resource allocation by leverage.",
        ("opportunity_exploitation", "multi_timescale_planning", "capability_market", "information_gain_scheduler"),
        ("PR1022:kim_dataverse_level7_plus_v1.objective_ecology", "MAIN:BCO_PRIME_V4"),
    ),
    CandidateCapability(
        "P1022-OWNER-INTERRUPTION-AUTONOMY-DEBT",
        1022,
        "Restrict owner interruption and measure repeated automatable burden as autonomy debt.",
        ("owner_interrupt_policy", "owner_burden_measurement", "cognitive_load_index", "autonomy_debt_ledger"),
        ("PR1022:kim_dataverse_level7_plus_v1.owner_interruption_firewall", "MAIN:BCO_PRIME/BUBBLES"),
    ),
    CandidateCapability(
        "P1022-CAPABILITY-MARKET",
        1022,
        "Select/reuse capabilities through an institutional capability market.",
        ("capability_market", "new_build_reuse_gate", "capability_underuse_detection"),
        ("PR1022:capability_market_requirement", "MAIN:alpha_omega_v30.capability_market"),
    ),
    CandidateCapability(
        "P1022-ARCHITECTURE-ENTROPY",
        1022,
        "Detect overlapping capability responsibilities and convergence opportunities.",
        ("semantic_novelty", "capability_ecology", "primitive_decomposition", "responsibility_overlap_recommendation"),
        ("PR1022:architecture_entropy_recommendation", "MAIN:CFBE_WAVE2"),
    ),
    CandidateCapability(
        "P1022-CAUSAL-VALUE-COUNTERFACTUAL",
        1022,
        "Learn causal value and compare cross-provider counterfactual outcomes.",
        ("causal_attribution_graph", "counterfactual_challenger", "owner_burden_measurement", "cross_provider_counterfactual"),
        ("PR1022:kim_dataverse_causal_value_learning_v1.py", "PR1022:kim_dataverse_cross_provider_counterfactual_v1.py", "MAIN:CFBE_WAVE2"),
    ),
    CandidateCapability(
        "P1022-PERSISTENT-CARRIER-CONTINUITY",
        1022,
        "Qualify persistent no-chat continuity and wake/handoff behavior without claiming deployment.",
        ("recovery_checkpointing", "persistent_carrier_qualification", "wait_wake_handoff", "proof_before_promotion"),
        ("PR1022:kim_dataverse_persistent_carrier_contract_v1.py",),
    ),
    CandidateCapability(
        "P1022-NEGATIVE-KNOWLEDGE-VALUE-RETENTION",
        1022,
        "Diffuse verified negative lessons and preserve value through lifecycle changes.",
        ("negative_knowledge_diffusion", "value_retention", "proof_before_promotion", "capability_ecology"),
        ("PR1022:kim_dataverse_negative_knowledge_diffusion_v1.py", "PR1022:kim_dataverse_value_retention_v1.py"),
    ),
    CandidateCapability(
        "P1022-DYNAMIC-ORGANIZATION",
        1022,
        "Dynamically recompose bounded specialist organization while preserving authority ceilings.",
        ("dynamic_specialist_reorganization", "failure_lane_isolation", "capability_market", "provider_admission_separation"),
        ("PR1022:kim_dataverse_dynamic_organization_v1.py",),
    ),
)


def _stable_hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def classify_capability(candidate: CandidateCapability) -> CapabilityCourtReceipt:
    candidate.validate()
    decomposition = decompose_primitives(
        capability_id=candidate.capability_id,
        required_primitives=candidate.primitives,
        estate_primitives=ESTATE_PRIMITIVES,
    )
    overlap = float(decomposition.overlap_ratio)
    reused = tuple(sorted(set(candidate.primitives) & set(ESTATE_PRIMITIVES)))
    missing = tuple(sorted(set(candidate.primitives) - set(ESTATE_PRIMITIVES)))

    if candidate.provider_effect_required or candidate.workflow_or_provider_authority_surface:
        disposition = CapabilityDisposition.PROVIDER_GATED_HOLD
    elif overlap >= 0.999999:
        disposition = CapabilityDisposition.REUSE
    elif overlap >= 0.70:
        disposition = CapabilityDisposition.EXTEND
    elif overlap >= 0.34:
        disposition = CapabilityDisposition.SELECTIVE_HARVEST
    else:
        disposition = CapabilityDisposition.UNIQUE_RESTACK

    payload = {
        "schema": SCHEMA,
        "source_epoch": SOURCE_EPOCH,
        "capability_id": candidate.capability_id,
        "pr_number": candidate.pr_number,
        "overlap_ratio": round(overlap, 6),
        "reused_primitives": reused,
        "missing_primitives": missing,
        "disposition": disposition.value,
        "evidence_refs": candidate.evidence_refs,
        "provider_effect_authorized": False,
        "stable_promotion_authorized": False,
    }
    return CapabilityCourtReceipt(
        capability_id=candidate.capability_id,
        pr_number=candidate.pr_number,
        overlap_ratio=round(overlap, 6),
        reused_primitives=reused,
        missing_primitives=missing,
        disposition=disposition,
        evidence_refs=candidate.evidence_refs,
        provider_effect_authorized=False,
        stable_promotion_authorized=False,
        receipt_sha256=_stable_hash(payload),
    )


def _branch_disposition(pr_number: int, receipts: Iterable[CapabilityCourtReceipt]) -> BranchDisposition:
    rows = tuple(receipts)
    if pr_number == 1021:
        return BranchDisposition.SPLIT_HARVEST_AND_REPAIR
    if pr_number == 1025:
        return BranchDisposition.SELECTIVE_HARVEST
    if pr_number == 1022:
        return BranchDisposition.SUPERSEDE_AFTER_SELECTIVE_HARVEST
    raise ValueError("CONVERGENCE_UNKNOWN_PR")


def run_court() -> tuple[tuple[CapabilityCourtReceipt, ...], tuple[BranchCourtReceipt, ...]]:
    capability_receipts = tuple(classify_capability(candidate) for candidate in CANDIDATES)
    branch_receipts: list[BranchCourtReceipt] = []
    for pr_number in (1021, 1025, 1022):
        rows = tuple(row for row in capability_receipts if row.pr_number == pr_number)
        counts = {mode: sum(row.disposition is mode for row in rows) for mode in CapabilityDisposition}
        disposition = _branch_disposition(pr_number, rows)
        payload = {
            "schema": SCHEMA,
            "source_epoch": SOURCE_EPOCH,
            "pr_number": pr_number,
            "head_sha": PR_HEADS[pr_number],
            "candidate_count": len(rows),
            "counts": {mode.value: counts[mode] for mode in CapabilityDisposition},
            "branch_disposition": disposition.value,
            "provider_effect_authorized": False,
            "stable_promotion_authorized": False,
        }
        branch_receipts.append(
            BranchCourtReceipt(
                pr_number=pr_number,
                head_sha=PR_HEADS[pr_number],
                candidate_count=len(rows),
                reuse_count=counts[CapabilityDisposition.REUSE],
                extend_count=counts[CapabilityDisposition.EXTEND],
                selective_harvest_count=counts[CapabilityDisposition.SELECTIVE_HARVEST],
                unique_restack_count=counts[CapabilityDisposition.UNIQUE_RESTACK],
                provider_hold_count=counts[CapabilityDisposition.PROVIDER_GATED_HOLD],
                branch_disposition=disposition,
                provider_effect_authorized=False,
                stable_promotion_authorized=False,
                receipt_sha256=_stable_hash(payload),
            )
        )
    return capability_receipts, tuple(branch_receipts)


def court_summary() -> dict[str, Any]:
    capabilities, branches = run_court()
    return {
        "schema": SCHEMA,
        "source_epoch": SOURCE_EPOCH,
        "candidate_capabilities": len(capabilities),
        "branches": [asdict(row) for row in branches],
        "provider_effect_authorized": False,
        "stable_promotion_authorized": False,
        "merge_or_close_authorized": False,
    }


__all__ = [
    "BranchCourtReceipt",
    "BranchDisposition",
    "CANDIDATES",
    "CapabilityCourtReceipt",
    "CapabilityDisposition",
    "CandidateCapability",
    "ESTATE_PRIMITIVES",
    "PR_HEADS",
    "SCHEMA",
    "SOURCE_EPOCH",
    "classify_capability",
    "court_summary",
    "run_court",
]
