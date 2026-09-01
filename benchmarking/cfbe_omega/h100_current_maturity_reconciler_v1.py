from __future__ import annotations

"""Current-main reconciliation for the CFBE Hyperleverage 100 programme.

This module does not create another improvement genome. It reconciles the canonical
FHU-001..FHU-100 ledger against the source-control binding fabric and the later
provider-closure evidence. The output deliberately separates programme completion
from empirical/runtime maturity so that 100/100 routing can never be mistaken for
100 live provider deployments.
"""

from dataclasses import asdict, dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Iterable

from benchmarking.cfbe_omega.federation_competitive_upgrade_fabric_v1 import (
    ImplementationMode,
    compile_control_bindings,
    load_genome,
)

SCHEMA = "CFBE-H100-CURRENT-MATURITY-RECONCILER-V1"
CLOSURE_PATH = Path(__file__).with_name("CFBE_HYPERLEVERAGE_100_CLOSURE_20260901.json")
EXPECTED_PROVIDER_GENES = frozenset({"FHU-042", "FHU-047"})
FRONTIER_STRENGTHENED_V2 = frozenset({
    "FHU-004", "FHU-010", "FHU-018", "FHU-020", "FHU-031",
    "FHU-032", "FHU-040", "FHU-041", "FHU-042", "FHU-052",
    "FHU-054", "FHU-057", "FHU-059", "FHU-069", "FHU-073",
    "FHU-074", "FHU-075", "FHU-081", "FHU-082", "FHU-084",
    "FHU-086", "FHU-090", "FHU-094", "FHU-098", "FHU-100",
})

class ProgrammeMaturity(str, Enum):
    SOURCE_REUSE_BOUND = "SOURCE_REUSE_BOUND"
    SOURCE_COMPOSITION_BOUND = "SOURCE_COMPOSITION_BOUND"
    PROVIDER_VERIFIED = "PROVIDER_VERIFIED"

class EmpiricalState(str, Enum):
    PROVIDER_VERIFIED = "PROVIDER_VERIFIED"
    HOSTED_VERIFIED = "HOSTED_VERIFIED"
    OBSERVED_PARTIAL = "OBSERVED_PARTIAL"
    SOURCE_READY = "SOURCE_READY"
    HOLD_CREDENTIAL_BINDING = "HOLD_CREDENTIAL_BINDING"
    HOLD_REAL_OBSERVATIONS = "HOLD_REAL_OBSERVATIONS"

@dataclass(frozen=True, slots=True)
class GeneMaturity:
    gene_id: str
    domain: str
    improvement: str
    implementation_mode: str
    programme_maturity: str
    executable_binding: bool
    frontier_strengthened_v2: bool
    provider_verified: bool
    provider_effect_authorized: bool = False
    stable_promotion_authorized: bool = False

@dataclass(frozen=True, slots=True)
class EmpiricalFrontier:
    lane_id: str
    state: EmpiricalState
    terminal_gate: str | None

@dataclass(frozen=True, slots=True)
class H100CurrentReconciliation:
    schema: str
    source_main_sha: str
    gene_count: int
    executable_binding_count: int
    reuse_count: int
    composed_count: int
    provider_verified_count: int
    strengthened_v2_count: int
    source_control_complete: bool
    provider_gate_count: int
    provider_gate_open_count: int
    stable_promotion_authorized: bool
    provider_effect_authorized: bool
    genes: tuple[GeneMaturity, ...]
    empirical_frontiers: tuple[EmpiricalFrontier, ...]

    def canonical_mapping(self) -> dict[str, object]:
        return asdict(self)

def _validate_sha(value: str) -> str:
    text = str(value).strip().lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise ValueError("H100_CURRENT_SOURCE_SHA_INVALID")
    return text

def _provider_closure(path: Path = CLOSURE_PATH) -> tuple[frozenset[str], int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    programme = payload.get("capability_programme", {})
    if programme.get("gene_count") != 100 or programme.get("source_or_control_routed") != 100:
        raise ValueError("H100_CURRENT_CLOSURE_COVERAGE_INVALID")
    provider_gate_count = int(programme.get("explicit_provider_gates", -1))
    provider_gate_open_count = int(programme.get("provider_gate_open", -1))
    closed = frozenset(
        gene_id for gene_id in EXPECTED_PROVIDER_GENES
        if payload.get(gene_id, {}).get("state") == "PROVIDER_VERIFIED_CLOSED"
    )
    if provider_gate_count != 2 or provider_gate_open_count != 0 or closed != EXPECTED_PROVIDER_GENES:
        raise ValueError("H100_CURRENT_PROVIDER_CLOSURE_EVIDENCE_INVALID")
    return closed, provider_gate_count, provider_gate_open_count

def _empirical_frontiers() -> tuple[EmpiricalFrontier, ...]:
    return (
        EmpiricalFrontier("DURABLE_RUNTIME", EmpiricalState.HOSTED_VERIFIED, "SERVING_PROVIDER_DEPLOYMENT_AND_HEALTH_READBACK_REQUIRED"),
        EmpiricalFrontier("TOOLBOX_GOVERNANCE", EmpiricalState.SOURCE_READY, "MANAGED_VERSIONED_TOOLBOX_PROVIDER_READBACK_REQUIRED"),
        EmpiricalFrontier("WORKLOAD_IDENTITY", EmpiricalState.PROVIDER_VERIFIED, "DEPLOYMENT_ROLES_AND_SEPARATE_HARDENING_REMAIN_GATED"),
        EmpiricalFrontier("LIVE_AGENT_TELEMETRY", EmpiricalState.OBSERVED_PARTIAL, "SERVING_OTEL_EXPORTER_FRESHNESS_AND_COMPLETENESS_READBACK_REQUIRED"),
        EmpiricalFrontier("TRACE_EVAL_OPTIMIZER", EmpiricalState.HOSTED_VERIFIED, "PROSPECTIVE_OPTIMIZER_NO_REGRESSION_COHORT_REQUIRED"),
        EmpiricalFrontier("SLSA_ATTESTATION", EmpiricalState.PROVIDER_VERIFIED, None),
        EmpiricalFrontier("MULTI_PROVIDER_ROUTING", EmpiricalState.HOLD_CREDENTIAL_BINDING, "OPENROUTER_ACTIONS_CREDENTIAL_BINDING_REQUIRED"),
        EmpiricalFrontier("AI_ASSET_VALUE_GOVERNANCE", EmpiricalState.HOSTED_VERIFIED, "CROSS_PROVIDER_AI_ASSET_DISCOVERY_READBACK_REQUIRED_FOR_ENTERPRISE_COMPLETENESS"),
        EmpiricalFrontier("OWNER_VALUE", EmpiricalState.HOLD_REAL_OBSERVATIONS, "MINIMUM_10_COURT_VERIFIED_OWNER_VALUE_PAIRS_REQUIRED"),
    )

def reconcile_current_h100(source_main_sha: str, *, closure_path: Path = CLOSURE_PATH) -> H100CurrentReconciliation:
    source_main_sha = _validate_sha(source_main_sha)
    provider_verified_genes, provider_gate_count, provider_gate_open_count = _provider_closure(closure_path)
    genes = load_genome()
    bindings = {binding.gene_id: binding for binding in compile_control_bindings(genes)}
    if len(genes) != 100 or len(bindings) != 100:
        raise ValueError("H100_CURRENT_EXACT_100_REQUIRED")
    rows: list[GeneMaturity] = []
    for gene in genes:
        if gene.gene_id not in bindings or not bindings[gene.gene_id].source_control_implemented:
            raise ValueError(f"H100_CURRENT_BINDING_MISSING:{gene.gene_id}")
        provider_verified = gene.gene_id in provider_verified_genes
        if provider_verified:
            maturity = ProgrammeMaturity.PROVIDER_VERIFIED
        elif gene.implementation_mode == ImplementationMode.REUSE_VERIFIED:
            maturity = ProgrammeMaturity.SOURCE_REUSE_BOUND
        else:
            maturity = ProgrammeMaturity.SOURCE_COMPOSITION_BOUND
        rows.append(GeneMaturity(
            gene_id=gene.gene_id,
            domain=gene.domain,
            improvement=gene.improvement,
            implementation_mode=gene.implementation_mode.value,
            programme_maturity=maturity.value,
            executable_binding=True,
            frontier_strengthened_v2=gene.gene_id in FRONTIER_STRENGTHENED_V2,
            provider_verified=provider_verified,
        ))
    reuse_count = sum(g.implementation_mode == ImplementationMode.REUSE_VERIFIED for g in genes)
    composed_count = sum(g.implementation_mode == ImplementationMode.COMPOSED_BY_FABRIC for g in genes)
    provider_contract_count = sum(g.implementation_mode == ImplementationMode.PROVIDER_GATED_CONTRACT for g in genes)
    if (reuse_count, composed_count, provider_contract_count) != (36, 62, 2):
        raise ValueError("H100_CURRENT_CANONICAL_36_62_2_ACCOUNTING_DRIFT")
    if {g.gene_id for g in genes if g.implementation_mode == ImplementationMode.PROVIDER_GATED_CONTRACT} != EXPECTED_PROVIDER_GENES:
        raise ValueError("H100_CURRENT_PROVIDER_GENE_IDENTITY_DRIFT")
    if len(FRONTIER_STRENGTHENED_V2) != 25:
        raise ValueError("H100_CURRENT_V2_STRENGTHENED_COUNT_DRIFT")
    result = H100CurrentReconciliation(
        schema=SCHEMA,
        source_main_sha=source_main_sha,
        gene_count=100,
        executable_binding_count=100,
        reuse_count=reuse_count,
        composed_count=composed_count,
        provider_verified_count=len(provider_verified_genes),
        strengthened_v2_count=len(FRONTIER_STRENGTHENED_V2),
        source_control_complete=True,
        provider_gate_count=provider_gate_count,
        provider_gate_open_count=provider_gate_open_count,
        stable_promotion_authorized=False,
        provider_effect_authorized=False,
        genes=tuple(rows),
        empirical_frontiers=_empirical_frontiers(),
    )
    validate_reconciliation(result)
    return result

def validate_reconciliation(result: H100CurrentReconciliation) -> None:
    if result.schema != SCHEMA:
        raise ValueError("H100_CURRENT_SCHEMA_INVALID")
    _validate_sha(result.source_main_sha)
    if result.gene_count != 100 or result.executable_binding_count != 100:
        raise ValueError("H100_CURRENT_COVERAGE_INCOMPLETE")
    if len(result.genes) != 100 or len({row.gene_id for row in result.genes}) != 100:
        raise ValueError("H100_CURRENT_GENE_ROWS_INVALID")
    if result.provider_verified_count != 2 or result.provider_gate_open_count != 0:
        raise ValueError("H100_CURRENT_PROVIDER_CLOSURE_DRIFT")
    if any(row.provider_effect_authorized or row.stable_promotion_authorized for row in result.genes):
        raise ValueError("H100_CURRENT_AUTHORITY_INHERITANCE_FORBIDDEN")
    if result.provider_effect_authorized or result.stable_promotion_authorized:
        raise ValueError("H100_CURRENT_GLOBAL_AUTHORITY_INHERITANCE_FORBIDDEN")
    if len(result.empirical_frontiers) != 9:
        raise ValueError("H100_CURRENT_NINE_EMPIRICAL_FRONTIERS_REQUIRED")

def maturity_counts(rows: Iterable[GeneMaturity]) -> dict[str, int]:
    counts = {state.value: 0 for state in ProgrammeMaturity}
    for row in rows:
        counts[row.programme_maturity] += 1
    return counts
