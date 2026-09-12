"""Deterministic additive adapter from the v3.1 registry surface to BCΩ-PRIME v4.

The adapter preserves every inherited v3.1 operation unchanged and adds three
local, decision-support-only v4 operations.  It creates no provider, dispatch,
deployment, scheduler, memory, proof, or stable-promotion authority.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from enum import Enum
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Protocol, Sequence

try:
    from .bco_prime_anticipatory_institution_v4 import (
        CapabilitySignal,
        CapabilityUseObservation,
        DemandSignal,
        compile_v4_decision,
        v4_capability_manifest,
    )
    from .bco_prime_meta_executive_v1 import PrimeObservation, StrategyCandidate
    from .bco_prime_v4_strategic_genome_bridge import (
        SCHEMA as GENOME_BRIDGE_SCHEMA,
        recommend_strategic_genomes,
    )
    from .federation_autopilot_metacognition_v1 import MetaCognitiveState
except ImportError:  # pragma: no cover - direct script execution
    from bco_prime_anticipatory_institution_v4 import (
        CapabilitySignal,
        CapabilityUseObservation,
        DemandSignal,
        compile_v4_decision,
        v4_capability_manifest,
    )
    from bco_prime_meta_executive_v1 import PrimeObservation, StrategyCandidate
    from bco_prime_v4_strategic_genome_bridge import (
        SCHEMA as GENOME_BRIDGE_SCHEMA,
        recommend_strategic_genomes,
    )
    from federation_autopilot_metacognition_v1 import MetaCognitiveState

from formation_omega.institutional_cognition import Horizon
from formation_omega.reconciliation_fabric_v2 import TaskGraphProfile
from formation_omega.strategic_ecology import StrategicGenomeRecord

try:
    from .bco_prime_successor_v3_1 import SuccessorRegistryV31 as _SuccessorRegistryV31
except ImportError:  # the exact v3.1 closure can be supplied as an injected registry
    try:  # pragma: no cover - direct script execution
        from bco_prime_successor_v3_1 import SuccessorRegistryV31 as _SuccessorRegistryV31
    except ImportError:  # pragma: no cover - dependency failure is tested via injection
        _SuccessorRegistryV31 = None  # type: ignore[assignment,misc]


SCHEMA = "BCO_PRIME_V4_V31_COMPATIBILITY_ADAPTER"
VERSION = "4.0.1"
SOURCE_MAIN_SHA = "ceb5cf36d1e608d0520a23114fe4bfc08eab644a"
V4_INSTITUTION_SHA256 = "3cada8deb311b9fcefe04990c0063086b0e623884591d23fe3359d258c04d0c8"
V4_GENOME_BRIDGE_SHA256 = "937024053bf593a03ffa59b21dea301f9ab2ce8c7fd86e684ba4669aa3e3f33c"
V31_REGISTRY_SHA256 = "111e37d3f6d990819f5d7ce6463cf62babb13aa3cdbb20db1490ec9366211a26"

V4_OPERATIONS = (
    "BCO-PRIME-V4-MANIFEST",
    "BCO-PRIME-V4-COMPILE-DECISION",
    "BCO-PRIME-V4-STRATEGIC-GENOME-RECOMMEND",
)

_FORBIDDEN_AUTHORITY_KEYS = {
    "authorityexpansion",
    "deploy",
    "dispatchauthorized",
    "eval",
    "exec",
    "executionauthorized",
    "externaleffectauthorized",
    "network",
    "providereffectauthorized",
    "registerlive",
    "sourcemutationauthorized",
    "stablepromotionauthorized",
    "stableselfpromotionallowed",
    "subprocess",
}


class V4CompatibilityContractError(ValueError):
    """Raised when an adapter input violates its local contract."""


class V4CompatibilityDependencyError(RuntimeError):
    """Raised when the exact v3.1 registry closure is not materialized."""


class V31Registry(Protocol):
    def health(self) -> dict[str, Any]: ...
    def manifest(self) -> dict[str, Any]: ...
    def execute(self, operation: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]: ...


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_v31_surface(registry: V31Registry) -> tuple[dict[str, Any], dict[str, Any]]:
    health = _to_json(registry.health())
    manifest = _to_json(registry.manifest())
    required = {
        "schema": "BCO_PRIME_SUCCESSOR_V3_1",
        "version": "3.1.0",
        "canonical_core_count": 100,
        "canonical_core_invariant_preserved": True,
        "v3_1_operation_count": 9,
        "sourceMutationAuthorized": False,
        "stablePromotionAuthorized": False,
    }
    for name, surface, hash_field in (
        ("health", health, "health_sha256"),
        ("manifest", manifest, "manifest_sha256"),
    ):
        if not isinstance(surface, dict):
            raise V4CompatibilityDependencyError(f"V31_REGISTRY_SURFACE_MISMATCH:{name}:not_object")
        mismatches = [key for key, value in required.items() if surface.get(key) != value]
        expected_hash = surface.get(hash_field)
        body = dict(surface)
        body.pop(hash_field, None)
        if not isinstance(expected_hash, str) or _digest(body) != expected_hash:
            mismatches.append(hash_field)
        if mismatches:
            raise V4CompatibilityDependencyError(
                f"V31_REGISTRY_SURFACE_MISMATCH:{name}:{','.join(sorted(set(mismatches)))}"
            )
    return health, manifest


def _to_json(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise V4CompatibilityContractError("non-finite output rejected")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise V4CompatibilityContractError("non-string output key rejected")
            result[key] = _to_json(value[key])
        return result
    if isinstance(value, (list, tuple)):
        return [_to_json(item) for item in value]
    raise V4CompatibilityContractError(f"unsupported output type: {type(value).__name__}")


def _strict_normalize(value: Any, path: str = "$") -> Any:
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise V4CompatibilityContractError(f"non-finite number at {path}")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise V4CompatibilityContractError(f"non-string key at {path}")
            item = value[key]
            if _normalized_key(key) in _FORBIDDEN_AUTHORITY_KEYS and item not in (None, False, 0, "", [], {}):
                raise V4CompatibilityContractError(f"authority or executable effect rejected at {path}.{key}")
            result[key] = _strict_normalize(item, f"{path}.{key}")
        return result
    if isinstance(value, (list, tuple)):
        return [_strict_normalize(item, f"{path}[]") for item in value]
    raise V4CompatibilityContractError(f"unsupported input at {path}: {type(value).__name__}")


def _object(
    value: Any,
    field: str,
    *,
    allowed: set[str],
    required: set[str] = frozenset(),
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise V4CompatibilityContractError(f"{field} must be an object")
    unknown = sorted(set(value) - allowed)
    missing = sorted(required - set(value))
    if unknown:
        raise V4CompatibilityContractError(f"{field} has unknown fields: {','.join(unknown)}")
    if missing:
        raise V4CompatibilityContractError(f"{field} is missing fields: {','.join(missing)}")
    return value


def _sequence(value: Any, field: str, *, minimum: int = 0, maximum: int = 4096) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        raise V4CompatibilityContractError(f"{field} must be an array")
    result = list(value)
    if not minimum <= len(result) <= maximum:
        raise V4CompatibilityContractError(
            f"{field} item count must be in range [{minimum},{maximum}]"
        )
    return result


def _text(value: Any, field: str, *, non_empty: bool = True) -> str:
    if not isinstance(value, str) or (non_empty and not value.strip()):
        raise V4CompatibilityContractError(f"{field} must be a{' non-empty' if non_empty else ''} string")
    return value


def _strings(value: Any, field: str, *, non_empty: bool = False) -> tuple[str, ...]:
    items = _sequence(value, field, minimum=1 if non_empty else 0, maximum=2048)
    result = tuple(_text(item, f"{field}[]") for item in items)
    return result


def _boolean(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise V4CompatibilityContractError(f"{field} must be a Boolean")
    return value


def _integer(value: Any, field: str, *, minimum: int = 0, maximum: int = 1_000_000) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise V4CompatibilityContractError(f"{field} must be an integer in range [{minimum},{maximum}]")
    return value


def _number(value: Any, field: str, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    if type(value) not in (int, float) or type(value) is bool:
        raise V4CompatibilityContractError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise V4CompatibilityContractError(f"{field} must be in range [{minimum},{maximum}]")
    return result


def _graph(value: Any) -> TaskGraphProfile:
    required = {
        "node_count", "edge_count", "ready_parallel_count", "shared_state_key_count",
        "deterministic_fraction", "uncertainty", "evidence_conflict",
    }
    raw = _object(value, "observation.graph", allowed=required | {"consequential_fraction"}, required=required)
    return TaskGraphProfile(
        node_count=_integer(raw["node_count"], "observation.graph.node_count", minimum=1),
        edge_count=_integer(raw["edge_count"], "observation.graph.edge_count"),
        ready_parallel_count=_integer(raw["ready_parallel_count"], "observation.graph.ready_parallel_count"),
        shared_state_key_count=_integer(raw["shared_state_key_count"], "observation.graph.shared_state_key_count"),
        deterministic_fraction=_number(raw["deterministic_fraction"], "observation.graph.deterministic_fraction"),
        uncertainty=_number(raw["uncertainty"], "observation.graph.uncertainty"),
        evidence_conflict=_number(raw["evidence_conflict"], "observation.graph.evidence_conflict"),
        consequential_fraction=_number(raw.get("consequential_fraction", 0.0), "observation.graph.consequential_fraction"),
    )


def _meta_state(value: Any) -> MetaCognitiveState:
    required = {
        "confidence", "evidence_coverage", "contradiction_pressure", "novelty", "progress",
        "plan_stability", "context_freshness", "resource_pressure",
    }
    raw = _object(value, "observation.meta_state", allowed=required | {"repeated_failure_count"}, required=required)
    return MetaCognitiveState(
        confidence=_number(raw["confidence"], "observation.meta_state.confidence"),
        evidence_coverage=_number(raw["evidence_coverage"], "observation.meta_state.evidence_coverage"),
        contradiction_pressure=_number(raw["contradiction_pressure"], "observation.meta_state.contradiction_pressure"),
        novelty=_number(raw["novelty"], "observation.meta_state.novelty"),
        progress=_number(raw["progress"], "observation.meta_state.progress"),
        plan_stability=_number(raw["plan_stability"], "observation.meta_state.plan_stability"),
        context_freshness=_number(raw["context_freshness"], "observation.meta_state.context_freshness"),
        resource_pressure=_number(raw["resource_pressure"], "observation.meta_state.resource_pressure"),
        repeated_failure_count=_integer(raw.get("repeated_failure_count", 0), "observation.meta_state.repeated_failure_count"),
    )


def _observation(value: Any) -> PrimeObservation:
    required = {
        "mission_id", "objective_sha256", "graph", "meta_state", "effect_class", "reversible",
        "exact_authority", "provider_runtime_available",
    }
    optional = {
        "owner_approval_required", "active_streams", "shared_write_pressure", "owner_burden",
        "architecture_overlap", "frontier_gap", "evidence_refs",
    }
    raw = _object(value, "observation", allowed=required | optional, required=required)
    return PrimeObservation(
        mission_id=_text(raw["mission_id"], "observation.mission_id"),
        objective_sha256=_text(raw["objective_sha256"], "observation.objective_sha256"),
        graph=_graph(raw["graph"]),
        meta_state=_meta_state(raw["meta_state"]),
        effect_class=_text(raw["effect_class"], "observation.effect_class"),
        reversible=_boolean(raw["reversible"], "observation.reversible"),
        exact_authority=_boolean(raw["exact_authority"], "observation.exact_authority"),
        provider_runtime_available=_boolean(raw["provider_runtime_available"], "observation.provider_runtime_available"),
        owner_approval_required=_boolean(raw.get("owner_approval_required", False), "observation.owner_approval_required"),
        active_streams=_integer(raw.get("active_streams", 1), "observation.active_streams"),
        shared_write_pressure=_number(raw.get("shared_write_pressure", 0.0), "observation.shared_write_pressure"),
        owner_burden=_number(raw.get("owner_burden", 0.0), "observation.owner_burden"),
        architecture_overlap=_number(raw.get("architecture_overlap", 0.0), "observation.architecture_overlap"),
        frontier_gap=_number(raw.get("frontier_gap", 0.0), "observation.frontier_gap"),
        evidence_refs=_strings(raw.get("evidence_refs", []), "observation.evidence_refs"),
    )


def _strategy(value: Any, index: int) -> StrategyCandidate:
    prefix = f"strategies[{index}]"
    numeric = {
        "expected_quality", "evidence_strength", "reliability", "reversibility", "information_gain",
        "failure_domain_diversity", "latency_cost", "monetary_cost", "owner_burden", "risk",
    }
    required = {"strategy_id", "failure_domain"} | numeric
    raw = _object(value, prefix, allowed=required | {"external_effect", "proof_refs"}, required=required)
    return StrategyCandidate(
        strategy_id=_text(raw["strategy_id"], f"{prefix}.strategy_id"),
        failure_domain=_text(raw["failure_domain"], f"{prefix}.failure_domain"),
        **{name: _number(raw[name], f"{prefix}.{name}") for name in numeric},
        external_effect=_boolean(raw.get("external_effect", False), f"{prefix}.external_effect"),
        proof_refs=_strings(raw.get("proof_refs", []), f"{prefix}.proof_refs"),
    )


def _capability(value: Any, index: int) -> CapabilitySignal:
    prefix = f"capabilities[{index}]"
    required = {
        "capability_id", "interfaces", "providers", "failure_domain", "state", "proof_age_hours",
        "eligible_missions", "used_missions", "successful_uses", "reliability", "owner_burden_reduction",
        "cost_efficiency", "failure_domain_uniqueness", "strategic_option_value", "maintenance_burden",
        "context_burden",
    }
    raw = _object(value, prefix, allowed=required | {"authority_ready", "external_effect", "evidence_refs"}, required=required)
    return CapabilitySignal(
        capability_id=_text(raw["capability_id"], f"{prefix}.capability_id"),
        interfaces=_strings(raw["interfaces"], f"{prefix}.interfaces", non_empty=True),
        providers=_strings(raw["providers"], f"{prefix}.providers", non_empty=True),
        failure_domain=_text(raw["failure_domain"], f"{prefix}.failure_domain"),
        state=_text(raw["state"], f"{prefix}.state"),
        proof_age_hours=_number(raw["proof_age_hours"], f"{prefix}.proof_age_hours", maximum=1_000_000.0),
        eligible_missions=_integer(raw["eligible_missions"], f"{prefix}.eligible_missions"),
        used_missions=_integer(raw["used_missions"], f"{prefix}.used_missions"),
        successful_uses=_integer(raw["successful_uses"], f"{prefix}.successful_uses"),
        reliability=_number(raw["reliability"], f"{prefix}.reliability"),
        owner_burden_reduction=_number(raw["owner_burden_reduction"], f"{prefix}.owner_burden_reduction"),
        cost_efficiency=_number(raw["cost_efficiency"], f"{prefix}.cost_efficiency"),
        failure_domain_uniqueness=_number(raw["failure_domain_uniqueness"], f"{prefix}.failure_domain_uniqueness"),
        strategic_option_value=_number(raw["strategic_option_value"], f"{prefix}.strategic_option_value"),
        maintenance_burden=_number(raw["maintenance_burden"], f"{prefix}.maintenance_burden"),
        context_burden=_number(raw["context_burden"], f"{prefix}.context_burden"),
        authority_ready=_boolean(raw.get("authority_ready", False), f"{prefix}.authority_ready"),
        external_effect=_boolean(raw.get("external_effect", False), f"{prefix}.external_effect"),
        evidence_refs=_strings(raw.get("evidence_refs", []), f"{prefix}.evidence_refs"),
    )


def _utilization(value: Any, index: int) -> CapabilityUseObservation:
    prefix = f"utilization[{index}]"
    required = {"capability_id", "relevance", "used"}
    optional = {
        "skip_reason", "safe_parallelizable", "executed_in_parallel", "manual_user_fallback",
        "executable_by_system", "current_readback_available", "current_readback_used",
    }
    raw = _object(value, prefix, allowed=required | optional, required=required)
    skip = raw.get("skip_reason")
    if skip is not None:
        skip = _text(skip, f"{prefix}.skip_reason")
    return CapabilityUseObservation(
        capability_id=_text(raw["capability_id"], f"{prefix}.capability_id"),
        relevance=_number(raw["relevance"], f"{prefix}.relevance"),
        used=_boolean(raw["used"], f"{prefix}.used"),
        skip_reason=skip,
        safe_parallelizable=_boolean(raw.get("safe_parallelizable", False), f"{prefix}.safe_parallelizable"),
        executed_in_parallel=_boolean(raw.get("executed_in_parallel", False), f"{prefix}.executed_in_parallel"),
        manual_user_fallback=_boolean(raw.get("manual_user_fallback", False), f"{prefix}.manual_user_fallback"),
        executable_by_system=_boolean(raw.get("executable_by_system", False), f"{prefix}.executable_by_system"),
        current_readback_available=_boolean(raw.get("current_readback_available", False), f"{prefix}.current_readback_available"),
        current_readback_used=_boolean(raw.get("current_readback_used", False), f"{prefix}.current_readback_used"),
    )


def _demand(value: Any, index: int) -> DemandSignal:
    prefix = f"future_demand[{index}]"
    required = {
        "demand_id", "horizon", "required_interfaces", "probability", "value", "urgency",
        "option_value", "dependency_centrality", "evidence_strength", "uncertainty",
    }
    raw = _object(value, prefix, allowed=required | {"external_effect", "evidence_refs"}, required=required)
    try:
        horizon = Horizon(_text(raw["horizon"], f"{prefix}.horizon"))
    except ValueError as exc:
        raise V4CompatibilityContractError(f"{prefix}.horizon is invalid") from exc
    return DemandSignal(
        demand_id=_text(raw["demand_id"], f"{prefix}.demand_id"),
        horizon=horizon,
        required_interfaces=_strings(raw["required_interfaces"], f"{prefix}.required_interfaces", non_empty=True),
        probability=_number(raw["probability"], f"{prefix}.probability"),
        value=_number(raw["value"], f"{prefix}.value"),
        urgency=_number(raw["urgency"], f"{prefix}.urgency"),
        option_value=_number(raw["option_value"], f"{prefix}.option_value"),
        dependency_centrality=_number(raw["dependency_centrality"], f"{prefix}.dependency_centrality"),
        evidence_strength=_number(raw["evidence_strength"], f"{prefix}.evidence_strength"),
        uncertainty=_number(raw["uncertainty"], f"{prefix}.uncertainty"),
        external_effect=_boolean(raw.get("external_effect", False), f"{prefix}.external_effect"),
        evidence_refs=_strings(raw.get("evidence_refs", []), f"{prefix}.evidence_refs"),
    )


def _compile_decision(payload: Mapping[str, Any]) -> dict[str, Any]:
    required = {"source_head_sha", "observation", "strategies", "capabilities", "utilization", "future_demand"}
    raw = _object(payload, "payload", allowed=required | {"demand_slots"}, required=required)
    result = compile_v4_decision(
        source_head_sha=_text(raw["source_head_sha"], "source_head_sha"),
        observation=_observation(raw["observation"]),
        strategies=tuple(_strategy(item, index) for index, item in enumerate(_sequence(raw["strategies"], "strategies", minimum=1, maximum=256))),
        capabilities=tuple(_capability(item, index) for index, item in enumerate(_sequence(raw["capabilities"], "capabilities", maximum=512))),
        utilization=tuple(_utilization(item, index) for index, item in enumerate(_sequence(raw["utilization"], "utilization", maximum=4096))),
        future_demand=tuple(_demand(item, index) for index, item in enumerate(_sequence(raw["future_demand"], "future_demand", maximum=512))),
        demand_slots=_integer(raw.get("demand_slots", 8), "demand_slots", minimum=1, maximum=1000),
    )
    return _to_json(asdict(result))


def _genome_record(value: Any, index: int) -> StrategicGenomeRecord:
    prefix = f"records[{index}]"
    required = {"features", "mission_sequence", "realized_value", "reliability"}
    raw = _object(value, prefix, allowed=required | {"evidence_refs"}, required=required)
    return StrategicGenomeRecord.create(
        features=_strings(raw["features"], f"{prefix}.features", non_empty=True),
        mission_sequence=_strings(raw["mission_sequence"], f"{prefix}.mission_sequence", non_empty=True),
        realized_value=_number(raw["realized_value"], f"{prefix}.realized_value"),
        reliability=_number(raw["reliability"], f"{prefix}.reliability"),
        evidence_refs=_strings(raw.get("evidence_refs", []), f"{prefix}.evidence_refs"),
    )


def _recommend_genomes(payload: Mapping[str, Any]) -> dict[str, Any]:
    required = {"records", "features"}
    raw = _object(payload, "payload", allowed=required | {"minimum_similarity", "max_results"}, required=required)
    records = tuple(_genome_record(item, index) for index, item in enumerate(_sequence(raw["records"], "records", maximum=1024)))
    result = recommend_strategic_genomes(
        records,
        features=_strings(raw["features"], "features", non_empty=True),
        minimum_similarity=_number(raw.get("minimum_similarity", 0.30), "minimum_similarity"),
        max_results=_integer(raw.get("max_results", 3), "max_results", minimum=1, maximum=1000),
    )
    return _to_json(asdict(result))


class BcoPrimeV4CompatibilityAdapter:
    """Add v4 decision support while retaining the v3.1 registry contract."""

    def __init__(
        self,
        workspace_root: Path,
        base_registry: V31Registry | None = None,
        *,
        base_registry_sha256: str | None = None,
    ) -> None:
        self.workspace_root = workspace_root.resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        if base_registry is not None:
            if base_registry_sha256 != V31_REGISTRY_SHA256:
                raise V4CompatibilityDependencyError(
                    "V31_REGISTRY_ATTESTATION_REQUIRED: injected registry must carry exact SHA-256 "
                    f"{V31_REGISTRY_SHA256}"
                )
            self.base = base_registry
            self.base_registry_source_sha256 = base_registry_sha256
        elif _SuccessorRegistryV31 is not None:
            registry_path = Path(__file__).with_name("bco_prime_successor_v3_1.py")
            if not registry_path.is_file() or _file_sha256(registry_path) != V31_REGISTRY_SHA256:
                raise V4CompatibilityDependencyError(
                    "V31_REGISTRY_INTEGRITY_MISMATCH: materialized v3.1 registry does not match "
                    f"required SHA-256 {V31_REGISTRY_SHA256}"
                )
            self.base = _SuccessorRegistryV31(self.workspace_root / "v3_1")
            self.base_registry_source_sha256 = V31_REGISTRY_SHA256
        else:
            raise V4CompatibilityDependencyError(
                "V31_REGISTRY_UNAVAILABLE: materialize the exact v3.1 dependency closure "
                f"with registry SHA-256 {V31_REGISTRY_SHA256} or inject an attested conforming registry"
            )
        self._validated_base_health, self._validated_base_manifest = _validate_v31_surface(self.base)

    def health(self) -> dict[str, Any]:
        inherited = _to_json(self.base.health())
        result = {
            "schema": SCHEMA,
            "version": VERSION,
            "source_main_sha": SOURCE_MAIN_SHA,
            "base_registry_source_sha256": self.base_registry_source_sha256,
            "base": inherited,
            "canonical_core_count": inherited.get("canonical_core_count"),
            "canonical_core_invariant_preserved": inherited.get("canonical_core_invariant_preserved") is True,
            "v3_1_operation_count": inherited.get("v3_1_operation_count"),
            "v4_operation_count": len(V4_OPERATIONS),
            "v4_operations": list(V4_OPERATIONS),
            "runtimeState": "ON_DEMAND_GOVERNED",
            "compatibilityMode": "ADDITIVE_DELEGATION",
            "dispatchAuthorized": False,
            "providerEffectAuthorized": False,
            "sourceMutationAuthorized": False,
            "stablePromotionAuthorized": False,
            "newSchedulers": 0,
            "newMemoryRoots": 0,
            "newProviderExecutors": 0,
            "manualUserTasks": [],
            "ownerActionRequired": False,
        }
        result["health_sha256"] = _digest(result)
        return result

    def manifest(self) -> dict[str, Any]:
        result = self.health()
        inherited = _to_json(self.base.manifest())
        result["components"] = {
            "successor_v3_1": {
                "schema": inherited.get("schema"),
                "version": inherited.get("version"),
                "registry_sha256": V31_REGISTRY_SHA256,
                "manifest_sha256": inherited.get("manifest_sha256"),
            },
            "anticipatory_institution_v4": {
                "sha256": V4_INSTITUTION_SHA256,
                "manifest": _to_json(v4_capability_manifest()),
            },
            "strategic_genome_bridge_v4": {
                "schema": GENOME_BRIDGE_SCHEMA,
                "sha256": V4_GENOME_BRIDGE_SHA256,
            },
        }
        result["authorityBoundary"] = {
            "decisionSupportOnly": True,
            "inheritedAuthorityExpanded": False,
            "providerEffectAuthorized": False,
            "dispatchAuthorized": False,
            "stableSelfPromotionAllowed": False,
        }
        result["manifest_sha256"] = _digest(result)
        return result

    def execute(self, operation: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not isinstance(operation, str) or not operation:
            raise V4CompatibilityContractError("operation must be a non-empty string")
        if payload is not None and not isinstance(payload, Mapping):
            raise V4CompatibilityContractError("payload must be an object")
        clean = _strict_normalize(dict(payload or {}))
        if operation not in V4_OPERATIONS:
            return self.base.execute(operation, clean)
        if operation == "BCO-PRIME-V4-MANIFEST":
            output = self.manifest()
        elif operation == "BCO-PRIME-V4-COMPILE-DECISION":
            output = _compile_decision(clean)
        else:
            output = _recommend_genomes(clean)
        receipt = {
            "schema": "BCO_PRIME_SUCCESSOR_EXECUTION_RECEIPT_V4_COMPAT",
            "version": VERSION,
            "namespace": "v4_compatibility",
            "operation": operation,
            "source_main_sha": SOURCE_MAIN_SHA,
            "input_sha256": _digest(clean),
            "output": output,
            "dispatchAuthorized": False,
            "providerEffectAuthorized": False,
            "stablePromotionAuthorized": False,
            "manualUserTasks": [],
            "ownerActionRequired": False,
        }
        receipt["receipt_sha256"] = _digest(receipt)
        return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=SCHEMA)
    parser.add_argument("--workspace-root", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("health")
    sub.add_parser("manifest")
    run = sub.add_parser("run")
    run.add_argument("operation")
    run.add_argument("--payload-json", default="{}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    adapter = BcoPrimeV4CompatibilityAdapter(Path(args.workspace_root))
    if args.command == "health":
        output = adapter.health()
    elif args.command == "manifest":
        output = adapter.manifest()
    else:
        output = adapter.execute(args.operation, json.loads(args.payload_json))
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BcoPrimeV4CompatibilityAdapter",
    "SCHEMA",
    "SOURCE_MAIN_SHA",
    "V31_REGISTRY_SHA256",
    "V4CompatibilityContractError",
    "V4CompatibilityDependencyError",
    "V4_OPERATIONS",
    "VERSION",
]
