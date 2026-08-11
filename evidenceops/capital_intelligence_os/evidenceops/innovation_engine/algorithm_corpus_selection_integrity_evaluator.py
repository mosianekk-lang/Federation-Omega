from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .algorithms_common import (
    AUTHORITY_CEILING, AlgorithmOpportunity, AlgorithmResult, clamp, number,
    sequence, sha256, text, unique_text,
)

class CorpusSelectionIntegrityEvaluator:
    algorithm_id = "ALG-EOPS-CSIE-001"
    name = "Corpus Selection Integrity Evaluator"

    gate_names = (
        "G1_SCOPE_LOCKED",
        "G2_EXPECTED_SOURCES_ENUMERATED",
        "G3_BODIES_RETRIEVED",
        "G4_ATTACHMENTS_AND_NESTED_CONTAINERS_HANDLED",
        "G5_ATOMIC_DECOMPOSITION_COMPLETE",
        "G6_DEDUPLICATION_AND_VERSION_RECONCILIATION_COMPLETE",
        "G7_CONTRADICTIONS_AND_COUNTEREXAMPLES_TESTED",
        "G8_REQUIREMENT_COVERAGE_COMPLETE",
        "G9_SELECTION_AND_REJECTION_LOGIC_RECORDED",
        "G10_INDEPENDENT_READBACK_PASSED",
    )
    strong_claim = re.compile(r"\b(exhaustive|best|final|complete|all|full)\b", re.IGNORECASE)

    def run(self, *, requested_claim: str, gates: Mapping[str, Any]) -> AlgorithmResult:
        normalized = {name: bool(gates.get(name, False)) for name in self.gate_names}
        missing = [name for name, passed in normalized.items() if not passed]
        strong = bool(self.strong_claim.search(text(requested_claim)))
        permitted = not missing
        status = "SELECTION_VERIFIED" if permitted else "INVENTORY_OR_ANALYSIS_INCOMPLETE"
        release_language = requested_claim if permitted else "PROVISIONAL_BOUNDED_SELECTION_ONLY"
        violations: list[str] = []
        if strong and missing:
            violations.append("STRONG_CORPUS_CLAIM_BLOCKED_BY_INCOMPLETE_GATES")
        return AlgorithmResult(
            algorithm_id=self.algorithm_id,
            name=self.name,
            status=status,
            maturity="TESTED_LOCAL",
            output={
                "requested_claim": text(requested_claim),
                "release_language": release_language,
                "gates": normalized,
                "missing_gates": missing,
                "strong_claim_requested": strong,
                "selection_or_archive_completion_permitted": permitted,
            },
            violations=tuple(violations),
            metrics={"gate_coverage": (len(self.gate_names) - len(missing)) / len(self.gate_names)},
        )
