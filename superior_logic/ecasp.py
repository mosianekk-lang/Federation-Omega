from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable


class CorpusStatus(str, Enum):
    """Honest release states for corpus analysis and comparative selection."""

    DISCOVERY_INCOMPLETE = "DISCOVERY_INCOMPLETE"
    INVENTORY_COMPLETE_ANALYSIS_INCOMPLETE = "INVENTORY_COMPLETE_ANALYSIS_INCOMPLETE"
    PROVISIONAL_SHORTLIST = "PROVISIONAL_SHORTLIST"
    BOUNDED_SELECTION = "BOUNDED_SELECTION"
    EXHAUSTIVE_FINAL = "EXHAUSTIVE_FINAL"


TRIGGER_PHRASES = (
    "full sweep",
    "exhaustive sweep",
    "audit everything",
    "read all",
    "do all",
    "best combination",
    "strongest code",
    "strongest stack",
    "select the best",
    "complete archive",
    "entire corpus",
    "all emails",
    "all documents",
    "all modules",
    "final stack",
    "fully reconcile",
    "no stone unturned",
)

EXHAUSTIVE_CLAIM_TERMS = (
    "best",
    "final",
    "full",
    "complete",
    "exhaustive",
    "strongest",
    "fully reconciled",
)


@dataclass(frozen=True)
class CorpusObject:
    """Per-object progress state required by SLD-023 / ALG-ECASP-001."""

    object_id: str
    discovered: bool = True
    indexed: bool = False
    body_retrieved: bool = False
    parsed: bool = False
    material_attachments_expected: int = 0
    material_attachments_processed: int = 0
    module_decomposed: bool = False
    deduped: bool = False
    version_reconciled: bool = False
    conflict_tested: bool = False
    requirement_coverage_tested: bool = False
    selected_or_rejected: bool = False
    verified: bool = False
    excluded_as_immaterial: bool = False
    exclusion_reason: str | None = None

    def accounted_body(self) -> bool:
        return self.body_retrieved or (
            self.excluded_as_immaterial and bool(self.exclusion_reason)
        )

    def attachments_complete(self) -> bool:
        return self.material_attachments_processed >= self.material_attachments_expected

    def analytical_chain_complete(self) -> bool:
        if self.excluded_as_immaterial:
            return bool(self.exclusion_reason)
        return all(
            (
                self.accounted_body(),
                self.parsed,
                self.attachments_complete(),
                self.module_decomposed,
                self.deduped,
                self.version_reconciled,
                self.conflict_tested,
                self.requirement_coverage_tested,
                self.selected_or_rejected,
                self.verified,
            )
        )


@dataclass(frozen=True)
class ECASPRequest:
    instruction: str
    intended_claim: str
    expected_object_count: int
    objects: tuple[CorpusObject, ...]
    capability_universe_mapped: bool = False
    lineage_map_complete: bool = False
    conflict_dependency_matrix_complete: bool = False
    requirement_coverage_complete: bool = False
    counterexample_search_complete: bool = False
    independent_readback_complete: bool = False
    bounded_selection: bool = False
    bounded_scope_description: str | None = None
    unresolved_material_objects_disclosed: bool = False


@dataclass(frozen=True)
class GateResult:
    gate: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class ECASPResult:
    algorithm_id: str
    triggered: bool
    allow_exhaustive_final: bool
    status: CorpusStatus
    gates: tuple[GateResult, ...]
    missing_gates: tuple[str, ...]
    object_counts: dict[str, int]
    release_language: str
    audit_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        return value


def ecasp_triggered(instruction: str, intended_claim: str = "") -> bool:
    text = f"{instruction} {intended_claim}".lower()
    return any(phrase in text for phrase in TRIGGER_PHRASES) or any(
        term in intended_claim.lower() for term in EXHAUSTIVE_CLAIM_TERMS
    )


def _all(objects: Iterable[CorpusObject], predicate: str) -> bool:
    values = list(objects)
    return bool(values) and all(bool(getattr(obj, predicate)) for obj in values)


def evaluate_ecasp(request: ECASPRequest) -> ECASPResult:
    """Evaluate the ten ECASP release gates.

    The evaluator is deliberately fail-closed. A complete inventory is only G1;
    it cannot establish body, capability, lineage, conflict or coverage completion.
    """

    objects = list(request.objects)
    discovered = sum(1 for item in objects if item.discovered)
    indexed = sum(1 for item in objects if item.indexed)
    body_accounted = sum(1 for item in objects if item.accounted_body())
    analysed = sum(1 for item in objects if item.analytical_chain_complete())
    attachments_expected = sum(item.material_attachments_expected for item in objects)
    attachments_processed = sum(item.material_attachments_processed for item in objects)

    g1 = request.expected_object_count > 0 and discovered == request.expected_object_count
    g2 = g1 and body_accounted == request.expected_object_count
    g3 = g2 and attachments_processed >= attachments_expected
    g4 = g2 and request.capability_universe_mapped and _all(objects, "module_decomposed")
    g5 = request.lineage_map_complete and _all(objects, "version_reconciled")
    g6 = (
        request.conflict_dependency_matrix_complete
        and _all(objects, "deduped")
        and _all(objects, "conflict_tested")
    )
    g7 = request.requirement_coverage_complete and _all(
        objects, "requirement_coverage_tested"
    )
    g8 = request.counterexample_search_complete
    g9 = request.independent_readback_complete and analysed == request.expected_object_count

    intended_claim_lower = request.intended_claim.lower()
    strong_claim = any(term in intended_claim_lower for term in EXHAUSTIVE_CLAIM_TERMS)
    gates_before_claim = all((g1, g2, g3, g4, g5, g6, g7, g8, g9))
    g10 = (not strong_claim) or gates_before_claim

    gates = (
        GateResult("G1_INVENTORY", g1, f"discovered={discovered}; expected={request.expected_object_count}"),
        GateResult("G2_BODY_COVERAGE", g2, f"body_accounted={body_accounted}; expected={request.expected_object_count}"),
        GateResult("G3_ATTACHMENTS", g3, f"processed={attachments_processed}; expected={attachments_expected}"),
        GateResult("G4_CAPABILITY_UNIVERSE", g4, "capability map and per-object decomposition required"),
        GateResult("G5_VERSION_LINEAGE", g5, "lineage and supersession reconciliation required"),
        GateResult("G6_CONFLICT_DEPENDENCY", g6, "dedupe plus conflict/dependency matrix required"),
        GateResult("G7_REQUIREMENT_COVERAGE", g7, "requirements must be mapped to every material candidate"),
        GateResult("G8_COUNTEREXAMPLE", g8, "counterexample search/red-team must be complete"),
        GateResult("G9_INDEPENDENT_READBACK", g9, f"analysed={analysed}; expected={request.expected_object_count}"),
        GateResult("G10_CLAIM_LANGUAGE", g10, "claim strength must not exceed G1-G9 proof"),
    )
    missing = tuple(gate.gate for gate in gates if not gate.passed)
    allow_exhaustive = all(gate.passed for gate in gates)

    if allow_exhaustive:
        status = CorpusStatus.EXHAUSTIVE_FINAL
        release = "EXHAUSTIVE_FINAL: all ECASP G1-G10 gates passed."
    elif not g1:
        status = CorpusStatus.DISCOVERY_INCOMPLETE
        release = "DISCOVERY_INCOMPLETE: the bounded inventory is not complete."
    elif request.bounded_selection and request.bounded_scope_description and request.unresolved_material_objects_disclosed:
        status = CorpusStatus.BOUNDED_SELECTION
        release = (
            "BOUNDED_SELECTION: recommendation is limited to "
            f"{request.bounded_scope_description}; unresolved material objects are disclosed."
        )
    elif analysed > 0:
        status = CorpusStatus.PROVISIONAL_SHORTLIST
        release = "PROVISIONAL_SHORTLIST: some candidates were analysed, but exhaustive comparison is not proven."
    else:
        status = CorpusStatus.INVENTORY_COMPLETE_ANALYSIS_INCOMPLETE
        release = "INVENTORY_COMPLETE_ANALYSIS_INCOMPLETE: counting/indexing is complete, content comparison is not."

    return ECASPResult(
        algorithm_id="ALG-ECASP-001",
        triggered=ecasp_triggered(request.instruction, request.intended_claim),
        allow_exhaustive_final=allow_exhaustive,
        status=status,
        gates=gates,
        missing_gates=missing,
        object_counts={
            "expected": request.expected_object_count,
            "discovered": discovered,
            "indexed": indexed,
            "body_accounted": body_accounted,
            "analytically_complete": analysed,
            "attachments_expected": attachments_expected,
            "attachments_processed": attachments_processed,
        },
        release_language=release,
        audit_payload={
            "bounded_selection": request.bounded_selection,
            "bounded_scope_description": request.bounded_scope_description,
            "unresolved_material_objects_disclosed": request.unresolved_material_objects_disclosed,
        },
    )
