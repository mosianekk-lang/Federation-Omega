from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .algorithms_common import (
    AUTHORITY_CEILING, AlgorithmOpportunity, AlgorithmResult, clamp, number,
    sequence, sha256, text, unique_text,
)

class ControlPlaneIntegrityGuard:
    algorithm_id = "ALG-EOPS-CPIG-001"
    name = "Control-Plane Integrity Guard"

    required_fields = {
        "record_id", "record_type", "cycle_id", "packet_id", "idempotency_key",
        "expected_revision", "current_revision", "lease_epoch",
        "cycle_start_lease_epoch", "collision_key", "collision_owner",
        "actor_id", "matter_id", "case_wall_id",
    }

    def run(
        self,
        transaction: Mapping[str, Any],
        *,
        existing_ids: Iterable[str] = (),
        existing_idempotency: Mapping[str, str] | None = None,
        valid_references: Iterable[str] = (),
        collision_owners: Mapping[str, str] | None = None,
        allowed_states: Iterable[str] = (),
    ) -> AlgorithmResult:
        violations: list[str] = []
        missing = sorted(field for field in self.required_fields if transaction.get(field) in (None, ""))
        violations.extend(f"MISSING_REQUIRED_FIELD:{field}" for field in missing)
        record_id = text(transaction.get("record_id"))
        idempotency_key = text(transaction.get("idempotency_key"))
        existing_id_map = dict(existing_idempotency or {})
        if record_id in set(existing_ids):
            prior_key = existing_id_map.get(record_id)
            if not prior_key or prior_key != idempotency_key:
                violations.append("IDENTIFIER_COLLISION")
        if text(transaction.get("expected_revision")) != text(transaction.get("current_revision")):
            violations.append("REVISION_DRIFT")
        if text(transaction.get("lease_epoch")) != text(transaction.get("cycle_start_lease_epoch")):
            violations.append("CROSS_EPOCH_ATTRIBUTION")
        if text(transaction.get("collision_owner")) != text(transaction.get("actor_id")):
            violations.append("COLLISION_KEY_OWNERSHIP_MISMATCH")
        owners = dict(collision_owners or {})
        collision_key = text(transaction.get("collision_key"))
        if collision_key and collision_key in owners and owners[collision_key] != text(transaction.get("actor_id")):
            violations.append("COLLISION_KEY_ALREADY_LEASED")
        valid_refs = set(unique_text(valid_references))
        references = unique_text(sequence(transaction.get("references")))
        dangling = [reference for reference in references if reference not in valid_refs]
        violations.extend(f"DANGLING_REFERENCE:{reference}" for reference in dangling)
        state = text(transaction.get("state"))
        allowed = set(unique_text(allowed_states))
        if state and allowed and state not in allowed:
            violations.append("INVALID_EXECUTABLE_STATE")
        nested_case_ids = set(unique_text(sequence(transaction.get("nested_matter_ids"))))
        nested_walls = set(unique_text(sequence(transaction.get("nested_case_wall_ids"))))
        if nested_case_ids and nested_case_ids != {text(transaction.get("matter_id"))}:
            violations.append("CROSS_MATTER_IDENTIFIER")
        if nested_walls and nested_walls != {text(transaction.get("case_wall_id"))}:
            violations.append("CROSS_CASE_WALL_IDENTIFIER")
        permitted = not violations
        return AlgorithmResult(
            algorithm_id=self.algorithm_id,
            name=self.name,
            status="COMMIT_PERMITTED" if permitted else "BLOCKED_FAIL_CLOSED",
            maturity="TESTED_LOCAL",
            output={
                "record_id": record_id,
                "commit_permitted": permitted,
                "idempotent_replay": record_id in set(existing_ids) and existing_id_map.get(record_id) == idempotency_key,
                "references_checked": references,
                "collision_key": collision_key,
                "revision_checked": True,
                "lease_epoch_checked": True,
            },
            violations=tuple(sorted(set(violations))),
            metrics={"violation_count": float(len(set(violations)))},
        )
