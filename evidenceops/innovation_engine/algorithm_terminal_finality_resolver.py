from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .algorithms_common import (
    AUTHORITY_CEILING, AlgorithmOpportunity, AlgorithmResult, clamp, number,
    sequence, sha256, text, unique_text,
)

class TerminalFinalityResolver:
    algorithm_id = "ALG-EOPS-TFR-001"
    name = "Terminal Finality Resolver"

    terminal_states = {
        "EXTRACTED_VERIFIED",
        "DUPLICATE_CANONICAL_LINKED",
        "SUPERSEDED_BY_STRONGER_SOURCE",
        "IRRELEVANT_REASONED",
        "RESTRICTED_CONTROLLED",
        "TECHNICALLY_UNREADABLE_AFTER_EXHAUSTED_RECOVERY",
        "EXTERNALLY_UNAVAILABLE_AFTER_PROVED_SEARCH_REQUEST_AND_NON_PRODUCTION",
        "OWNER_DECISION_REQUIRED",
    }
    transitional_states = {"PARTIAL", "PENDING", "QUEUED", "UNRESOLVED", "BLOCKED", "UNKNOWN"}
    transitional_required = {
        "packet_id",
        "owner",
        "recovery_route",
        "next_test",
        "release_effect",
        "terminal_condition",
    }

    def run(self, items: Sequence[Mapping[str, Any]]) -> AlgorithmResult:
        resolved: list[dict[str, Any]] = []
        violations: list[str] = []
        terminal_count = 0
        for index, item in enumerate(items, start=1):
            item_id = text(item.get("item_id")) or f"ITEM-{index:05d}"
            state = text(item.get("state")).upper() or "UNKNOWN"
            row_violations: list[str] = []
            if state in self.terminal_states:
                terminal_count += 1
            elif state in self.transitional_states:
                missing = sorted(
                    field
                    for field in self.transitional_required
                    if item.get(field) in (None, "", [], {})
                )
                if missing:
                    row_violations.append("TRANSITIONAL_STATE_MISSING_CONTROL_FIELDS:" + ",".join(missing))
            else:
                row_violations.append("INVALID_FINALITY_STATE")
            violations.extend(f"{item_id}:{violation}" for violation in row_violations)
            resolved.append(
                {
                    "item_id": item_id,
                    "state": state,
                    "terminal": state in self.terminal_states,
                    "violations": row_violations,
                    "next_test": text(item.get("next_test")),
                    "terminal_condition": text(item.get("terminal_condition")),
                }
            )
        complete = bool(items) and terminal_count == len(items) and not violations
        status = "TERMINAL_FINALITY_COMPLETE" if complete else "TERMINAL_FINALITY_OPEN"
        return AlgorithmResult(
            algorithm_id=self.algorithm_id,
            name=self.name,
            status=status,
            maturity="TESTED_LOCAL",
            output={
                "items": resolved,
                "total": len(items),
                "terminal_count": terminal_count,
                "unresolved_count": len(items) - terminal_count,
                "final_certificate_permitted": complete,
            },
            violations=tuple(violations),
            metrics={
                "terminal_coverage": terminal_count / len(items) if items else 0.0,
                "violation_count": float(len(violations)),
            },
        )
