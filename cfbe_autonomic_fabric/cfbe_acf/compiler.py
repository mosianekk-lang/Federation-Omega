from __future__ import annotations

from typing import Any, Mapping

from .models import ProofStage
from .util import (
    digest_json,
    reject_sensitive,
    require_bool,
    require_finite_number,
    require_int,
    require_nonempty,
)


class IntentCompiler:
    def compile(self, intent: Mapping[str, Any]) -> dict[str, Any]:
        reject_sensitive(dict(intent))
        objective = str(require_nonempty(intent.get("objective"), "intent.objective"))
        raw_capabilities = intent.get("required_capabilities", [])
        if not isinstance(raw_capabilities, list) or not all(
            isinstance(value, str) and value.strip() for value in raw_capabilities
        ):
            raise ValueError("required_capabilities must be a list of nonempty strings")
        capabilities = sorted(set(raw_capabilities))
        if not capabilities:
            raise ValueError("required_capabilities cannot be empty")
        if not isinstance(intent.get("constraints") or {}, dict):
            raise ValueError("intent.constraints must be an object")
        constraints = dict(intent.get("constraints") or {})
        authority = str(constraints.get("authority_class", "A0"))
        if authority not in {"A0", "A1", "A2", "A3", "A4", "A5"}:
            raise ValueError("invalid authority_class")
        max_cost = require_finite_number(
            constraints.get("maximum_incremental_cost", 0),
            "constraints.maximum_incremental_cost",
        )
        max_burden = require_finite_number(
            constraints.get("maximum_user_burden", 0),
            "constraints.maximum_user_burden",
        )
        mission_id = str(intent.get("mission_id") or "ACF-" + digest_json(objective)[:16])
        mission_version = require_int(
            intent.get("mission_version", 1), "intent.mission_version", minimum=1
        )
        proof_action_id = str(
            require_nonempty(
                intent.get("proof_action_id", "provider-admission"),
                "intent.proof_action_id",
            )
        )
        raw_stop_conditions = intent.get(
            "stop_conditions",
            ["authority drift", "semantic mismatch", "non-zero unapproved cost"],
        )
        if not isinstance(raw_stop_conditions, list) or not all(
            isinstance(value, str) and value.strip() for value in raw_stop_conditions
        ) or not raw_stop_conditions:
            raise ValueError("stop_conditions must be a nonempty list of strings")
        return {
            "schema": "CFBE-ACF-COMPILED-INTENT-V1",
            "mission_id": mission_id,
            "mission_version": mission_version,
            "proof_action_id": proof_action_id,
            "objective": objective,
            "required_capabilities": capabilities,
            "constraints": {
                "authority_class": authority,
                "maximum_incremental_cost": max_cost,
                "maximum_user_burden": max_burden,
                "effectful": require_bool(
                    constraints.get("effectful", False), "constraints.effectful"
                ),
                "require_semantic_readback": require_bool(
                    constraints.get("require_semantic_readback", True),
                    "constraints.require_semantic_readback",
                ),
                "require_reversible": require_bool(
                    constraints.get("require_reversible", True),
                    "constraints.require_reversible",
                ),
                "minimum_proof_stage": ProofStage(
                    constraints.get("minimum_proof_stage", "DISCOVERED")
                ).value,
                "maximum_age_seconds": require_int(
                    constraints.get("maximum_age_seconds", 86400),
                    "constraints.maximum_age_seconds",
                    minimum=1,
                ),
                "dry_run": require_bool(
                    constraints.get("dry_run", True), "constraints.dry_run"
                ),
            },
            "stop_conditions": tuple(raw_stop_conditions),
        }
