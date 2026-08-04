from __future__ import annotations

from datetime import date
import re
from typing import Any, Iterable

from .hashing import sha256_value
from .models import AUTHORITY_ORDER, MissionContract

DATE_PATTERN = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    cleaned = {str(value).strip() for value in values if str(value).strip()}
    return tuple(sorted(cleaned))


def compile_mission(
    objective: str,
    *,
    success_criteria: Iterable[str] = (),
    authority_ceiling: str = "A1",
    deadline: str | None = None,
    budget: dict[str, Any] | None = None,
    source_requirements: Iterable[str] = (),
    constraints: Iterable[str] = (),
    proof_requirements: Iterable[str] = (),
    rollback_required: bool = True,
    external_effects_allowed: bool = False,
) -> MissionContract:
    objective = " ".join(str(objective).split())
    if len(objective) < 8:
        raise ValueError("objective is too short")
    if authority_ceiling not in AUTHORITY_ORDER:
        raise ValueError("unsupported authority ceiling")
    if external_effects_allowed and authority_ceiling in {"A0", "A1"}:
        raise ValueError("A0/A1 cannot authorize external effects")

    if deadline is None:
        match = DATE_PATTERN.search(objective)
        deadline = match.group(1) if match else None
    if deadline is not None:
        date.fromisoformat(deadline)

    normalized_budget = dict(sorted((budget or {}).items()))
    success = _clean(success_criteria) or ("Verified completion against explicit proof gates",)
    sources = _clean(source_requirements)
    constraints_tuple = _clean(constraints)
    proofs = _clean(proof_requirements) or (
        "Source identity",
        "Execution receipt",
        "Target readback",
    )
    body = {
        "objective": objective,
        "success_criteria": success,
        "authority_ceiling": authority_ceiling,
        "deadline": deadline,
        "budget": normalized_budget,
        "source_requirements": sources,
        "constraints": constraints_tuple,
        "proof_requirements": proofs,
        "rollback_required": bool(rollback_required),
        "external_effects_allowed": bool(external_effects_allowed),
    }
    contract_sha = sha256_value(body)
    mission_id = f"MISSION-{contract_sha[:24].upper()}"
    return MissionContract(
        mission_id=mission_id,
        contract_sha256=contract_sha,
        **body,
    )
