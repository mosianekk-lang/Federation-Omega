from __future__ import annotations

"""FASCG consumer bridge for CFBE AO Production Genesis (AO-PGC) Phase 1.

This module deliberately *consumes* the upstream Production Genesis compiler rather
than copying its product/genome/readiness/go-live/PGY logic.  It converts AO-PGC
outputs into a bounded FASCG production-planning receipt and preserves maturity:
source/design evidence cannot become provider, operational, value, or 10x proof by
inheritance.

The bridge has no provider executor, no deployment authority, no model-training
surface, and no self-promotion path.  Exact provider effects remain owned by the
Federation's existing authority-gated provider workflows and SOL 6.2 proof spine.
"""

from dataclasses import dataclass
from hashlib import sha256
import importlib
import json
from types import ModuleType
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "FASCG-AOPGC-PRODUCTION-GENESIS-BRIDGE-V1"
UPSTREAM_SCHEMA = "CFBE_AO_PRODUCTION_GENESIS_PHASE1_V1"
PROVIDER_EFFECT_AUTHORIZED = False
PRODUCTION_DEPLOYMENT_AUTHORIZED = False
MODEL_TRAINING_AUTHORIZED = False
PRODUCTION_SELF_MUTATION_AUTHORIZED = False
TEN_X_VERIFIED = False


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


def _norm(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(v).strip() for v in values if str(v).strip()}))


def _load_pg(pg_module: ModuleType | Any | None = None) -> Any:
    pg = pg_module
    if pg is None:
        pg = importlib.import_module("benchmarking.cfbe_omega.production_genesis_v1")
    if getattr(pg, "SCHEMA", None) != UPSTREAM_SCHEMA:
        raise ValueError("FASCG_AOPGC_SCHEMA_MISMATCH")
    for flag in (
        "PROVIDER_EFFECT_AUTHORIZED",
        "PRODUCTION_DEPLOYMENT_AUTHORIZED",
        "MODEL_TRAINING_AUTHORIZED",
    ):
        if getattr(pg, flag, None) is not False:
            raise ValueError(f"FASCG_AOPGC_UPSTREAM_EFFECT_FLAG_INVALID:{flag}")
    return pg


@dataclass(frozen=True, slots=True)
class ProductContractSpec:
    product_id: str
    objective: str
    user_classes: tuple[str, ...]
    user_journeys: tuple[str, ...]
    required_outcomes: tuple[str, ...]
    authority_ceiling: str
    data_boundary: str
    owner_intent_hash: str
    quality_floor: float = 0.95
    security_floor: float = 0.95
    reliability_floor: float = 0.95

    def validate(self) -> "ProductContractSpec":
        if not all((self.product_id.strip(), self.objective.strip(), self.authority_ceiling.strip(), self.data_boundary.strip())):
            raise ValueError("FASCG_AOPGC_PRODUCT_CONTRACT_REQUIRED")
        if not self.user_classes or not self.user_journeys or not self.required_outcomes:
            raise ValueError("FASCG_AOPGC_PRODUCT_OUTCOME_JOURNEY_REQUIRED")
        if len(self.owner_intent_hash) != 64:
            raise ValueError("FASCG_AOPGC_OWNER_INTENT_HASH_REQUIRED")
        if any(not 0 <= x <= 1 for x in (self.quality_floor, self.security_floor, self.reliability_floor)):
            raise ValueError("FASCG_AOPGC_FLOOR_RANGE_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class AOPGCProductionEvidence:
    schema: str
    upstream_schema: str
    production_genome_id: str
    production_genome_sha256: str
    production_build_plan_sha256: str
    aocef_profile_sha256: str
    cognitive_genome_id: str
    complementary_system_count: int
    build_phase_count: int
    test_class_count: int
    proof_key_count: int
    readiness_stage: str
    observed_proof_keys: tuple[str, ...]
    missing_to_next: tuple[str, ...]
    go_live_status: str
    go_live_blockers: tuple[str, ...]
    exact_effect_authority: bool
    rollback_verified: bool
    semantic_canary_defined: bool
    aopgc_pgy_ratio: float | None
    aopgc_eligible_10x: bool
    fascg_promotion_ceiling: str
    provider_bound: bool
    operational_verified: bool
    value_verified: bool
    fascg_ten_x_verified: bool
    receipt_sha256: str

    @property
    def progressive_go_live_candidate(self) -> bool:
        return self.go_live_status == "READY_FOR_PROGRESSIVE_GO_LIVE"


def _proof_enum(pg: Any, proof_names: Sequence[str]) -> tuple[Any, ...]:
    names = _norm(proof_names)
    valid = {item.value: item for item in pg.ProofKey}
    unknown = sorted(set(names) - set(valid))
    if unknown:
        raise ValueError("FASCG_AOPGC_UNKNOWN_PROOF_KEY:" + ",".join(unknown))
    return tuple(valid[name] for name in names)


def _vector(pg: Any, values: Mapping[str, Any] | None) -> Any | None:
    if values is None:
        return None
    return pg.ProductionGenesisVector(**dict(values))


def compile_aopgc_production_evidence(
    contract: ProductContractSpec,
    *,
    observed_proof_keys: Sequence[str],
    exact_effect_authority: bool,
    rollback_verified: bool,
    semantic_canary_defined: bool,
    compute_budget: float,
    allowed_mutations: Sequence[str] | None = None,
    candidate_vector: Mapping[str, Any] | None = None,
    frontier_vector: Mapping[str, Any] | None = None,
    pgy_provider_verified: bool = False,
    forward_system_classes: int = 0,
    no_benchmark_leakage: bool = True,
    pg_module: ModuleType | Any | None = None,
) -> AOPGCProductionEvidence:
    """Compile FASCG production evidence through the upstream AO-PGC API.

    A PGY >=10x result is retained as AO-PGC evidence only.  It cannot set
    ``fascg_ten_x_verified`` because FASCG's separate composite-frontier ARY court
    requires its own matched operational evidence and replications.
    """

    contract.validate()
    if compute_budget < 0:
        raise ValueError("FASCG_AOPGC_COMPUTE_BUDGET_NEGATIVE")
    if forward_system_classes < 0:
        raise ValueError("FASCG_AOPGC_FORWARD_SYSTEM_CLASSES_NEGATIVE")
    if (candidate_vector is None) ^ (frontier_vector is None):
        raise ValueError("FASCG_AOPGC_PGY_VECTORS_MUST_BE_PAIRED")

    pg = _load_pg(pg_module)
    upstream_contract = pg.ProductContract(
        product_id=contract.product_id,
        objective=contract.objective,
        user_classes=tuple(contract.user_classes),
        user_journeys=tuple(contract.user_journeys),
        required_outcomes=tuple(contract.required_outcomes),
        authority_ceiling=contract.authority_ceiling,
        data_boundary=contract.data_boundary,
        owner_intent_hash=contract.owner_intent_hash,
        quality_floor=contract.quality_floor,
        security_floor=contract.security_floor,
        reliability_floor=contract.reliability_floor,
    ).validate()

    kwargs: dict[str, Any] = {}
    if allowed_mutations is not None:
        kwargs["allowed_mutations"] = tuple(allowed_mutations)
    genome = pg.compile_production_genome(upstream_contract, **kwargs)
    plan = pg.compile_build_plan(genome)
    test_matrix = pg.compile_test_matrix(genome)
    profile = pg.compile_aocef_profile(
        genome,
        objective=contract.objective,
        compute_budget=compute_budget,
        safety_floor=contract.security_floor,
        reliability_floor=contract.reliability_floor,
    )

    proof_enums = _proof_enum(pg, observed_proof_keys)
    readiness = pg.evaluate_readiness(proof_enums)
    go_live = pg.evaluate_progressive_go_live(
        proof_enums,
        exact_effect_authority=bool(exact_effect_authority),
        rollback_verified=bool(rollback_verified),
        semantic_canary_defined=bool(semantic_canary_defined),
    )

    system_count = len(tuple(pg.ComplementarySystem))
    phase_count = len(tuple(pg.BuildPhase))
    test_count = len(tuple(pg.TestClass))
    proof_count = len(tuple(pg.ProofKey))
    if (system_count, phase_count, test_count, proof_count) != (20, 17, 14, 28):
        raise ValueError("FASCG_AOPGC_UPSTREAM_SHAPE_DRIFT")
    if len(genome.systems) != 20:
        raise ValueError("FASCG_AOPGC_GENOME_SYSTEM_SET_INCOMPLETE")
    if getattr(profile.outer_envelope, "no_production_self_mutation", None) is not True:
        raise ValueError("FASCG_AOPGC_PRODUCTION_SELF_MUTATION_BOUNDARY_MISSING")
    if profile.outer_envelope.owner_intent_hash != contract.owner_intent_hash:
        raise ValueError("FASCG_AOPGC_OWNER_INTENT_DRIFT")
    if profile.outer_envelope.authority_ceiling != contract.authority_ceiling:
        raise ValueError("FASCG_AOPGC_AUTHORITY_DRIFT")

    pgy_ratio: float | None = None
    pgy_eligible = False
    if candidate_vector is not None and frontier_vector is not None:
        candidate = _vector(pg, candidate_vector)
        frontier = _vector(pg, frontier_vector)
        pgy = pg.evaluate_production_genesis_yield(
            candidate,
            frontier,
            maturity=readiness.stage,
            provider_verified=bool(pgy_provider_verified),
            forward_system_classes=forward_system_classes,
            no_benchmark_leakage=bool(no_benchmark_leakage),
            rollback_verified=bool(rollback_verified),
        )
        pgy_ratio = round(float(pgy.ratio), 8)
        pgy_eligible = bool(pgy.eligible_10x)

    stage_name = readiness.stage.name
    if stage_name == "VALUE_VERIFIED":
        ceiling = "VALUE_EVIDENCE_CANDIDATE"
    elif stage_name == "OPERATIONAL_VERIFIED":
        ceiling = "OPERATIONAL_EVIDENCE_CANDIDATE"
    elif stage_name in {"DEPLOYED", "PROVIDER_VERIFIED"}:
        ceiling = stage_name
    elif stage_name in {"PROVIDER_CANARY_READY", "SUPPLY_CHAIN_VERIFIED", "DIGITAL_TWIN_VERIFIED"}:
        ceiling = stage_name
    else:
        ceiling = "DETERMINISTIC_OR_LOWER"

    body = {
        "schema": SCHEMA,
        "upstream_schema": UPSTREAM_SCHEMA,
        "production_genome_id": genome.genome_id,
        "production_genome_sha256": genome.fingerprint_sha256,
        "production_build_plan_sha256": plan.fingerprint_sha256,
        "aocef_profile_sha256": profile.fingerprint_sha256,
        "cognitive_genome_id": profile.cognitive_genome_id,
        "complementary_system_count": system_count,
        "build_phase_count": phase_count,
        "test_class_count": test_count,
        "proof_key_count": proof_count,
        "readiness_stage": stage_name,
        "observed_proof_keys": [p.value for p in readiness.observed],
        "missing_to_next": [p.value for p in readiness.missing_to_next],
        "go_live_status": go_live.status,
        "go_live_blockers": list(go_live.blockers),
        "exact_effect_authority": bool(exact_effect_authority),
        "rollback_verified": bool(rollback_verified),
        "semantic_canary_defined": bool(semantic_canary_defined),
        "aopgc_pgy_ratio": pgy_ratio,
        "aopgc_eligible_10x": pgy_eligible,
        "fascg_promotion_ceiling": ceiling,
        "provider_bound": stage_name in {"PROVIDER_VERIFIED", "DEPLOYED", "OPERATIONAL_VERIFIED", "VALUE_VERIFIED"},
        "operational_verified": stage_name in {"OPERATIONAL_VERIFIED", "VALUE_VERIFIED"},
        "value_verified": stage_name == "VALUE_VERIFIED",
        "fascg_ten_x_verified": False,
    }
    digest = _hash(body)
    return AOPGCProductionEvidence(
        schema=SCHEMA,
        upstream_schema=UPSTREAM_SCHEMA,
        production_genome_id=genome.genome_id,
        production_genome_sha256=genome.fingerprint_sha256,
        production_build_plan_sha256=plan.fingerprint_sha256,
        aocef_profile_sha256=profile.fingerprint_sha256,
        cognitive_genome_id=profile.cognitive_genome_id,
        complementary_system_count=system_count,
        build_phase_count=phase_count,
        test_class_count=test_count,
        proof_key_count=proof_count,
        readiness_stage=stage_name,
        observed_proof_keys=tuple(p.value for p in readiness.observed),
        missing_to_next=tuple(p.value for p in readiness.missing_to_next),
        go_live_status=go_live.status,
        go_live_blockers=tuple(go_live.blockers),
        exact_effect_authority=bool(exact_effect_authority),
        rollback_verified=bool(rollback_verified),
        semantic_canary_defined=bool(semantic_canary_defined),
        aopgc_pgy_ratio=pgy_ratio,
        aopgc_eligible_10x=pgy_eligible,
        fascg_promotion_ceiling=ceiling,
        provider_bound=body["provider_bound"],
        operational_verified=body["operational_verified"],
        value_verified=body["value_verified"],
        fascg_ten_x_verified=False,
        receipt_sha256=digest,
    )


__all__ = [
    "AOPGCProductionEvidence",
    "MODEL_TRAINING_AUTHORIZED",
    "PRODUCTION_DEPLOYMENT_AUTHORIZED",
    "PRODUCTION_SELF_MUTATION_AUTHORIZED",
    "PROVIDER_EFFECT_AUTHORIZED",
    "ProductContractSpec",
    "SCHEMA",
    "TEN_X_VERIFIED",
    "UPSTREAM_SCHEMA",
    "compile_aopgc_production_evidence",
]
