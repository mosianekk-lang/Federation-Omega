"""Idempotent, local adaptive-learning ledger with promotion gates."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any

from .capability import canonical_json
from .schema import InputError


class PromotionState(IntEnum):
    DETECTED = 0
    DESIGNED = 1
    IMPLEMENTED = 2
    TESTED = 3
    VALIDATED = 4
    REGISTERED = 5
    BEHAVIOR_PROVEN = 6


@dataclass(frozen=True)
class LearningReceipt:
    fingerprint: str
    recurrence: int
    promotion_state: PromotionState
    duplicate_suppressed: bool
    promotion_authorized: bool
    authority_expansion: bool
    manual_user_tasks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "recurrence": self.recurrence,
            "promotion_state": self.promotion_state.name,
            "duplicate_suppressed": self.duplicate_suppressed,
            "promotion_authorized": self.promotion_authorized,
            "authority_expansion": self.authority_expansion,
            "manual_user_tasks": list(self.manual_user_tasks),
        }


def incident_fingerprint(incident: dict[str, Any]) -> str:
    import hashlib

    identity = {
        "failure_code": incident.get("failure_code"),
        "claim": incident.get("claim"),
        "observed_fruit": incident.get("observed_fruit"),
        "desired_outcome": incident.get("desired_outcome"),
        "affected_capabilities": sorted(map(str, incident.get("affected_capabilities", []))),
    }
    return hashlib.sha256(canonical_json(identity).encode()).hexdigest()


class LearningLedger:
    schema_version = "realityguard.learning.v1"

    def __init__(self, path: Path):
        self.path = Path(path)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": self.schema_version, "incidents": {}}
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if value.get("schema_version") != self.schema_version or not isinstance(value.get("incidents"), dict):
            raise InputError("learning ledger schema is invalid")
        return value

    def _atomic_write(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=".realityguard-learning-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    def record(
        self,
        incident: dict[str, Any],
        *,
        promotion_state: PromotionState = PromotionState.DETECTED,
        regression_tests: tuple[str, ...] = (),
        dry_run: bool = False,
    ) -> LearningReceipt:
        if not isinstance(incident, dict):
            raise InputError("incident must be an object")
        for field in ("failure_code", "claim", "observed_fruit", "desired_outcome"):
            if not incident.get(field):
                raise InputError(f"incident.{field} is required")
        if promotion_state >= PromotionState.REGISTERED:
            raise InputError("REGISTERED and BEHAVIOR_PROVEN require separate Formation promotion and later canary proof")
        if promotion_state >= PromotionState.TESTED and not regression_tests:
            raise InputError("TESTED or VALIDATED learning requires regression_tests")
        value = self._read()
        fingerprint = incident_fingerprint(incident)
        existing = value["incidents"].get(fingerprint)
        recurrence = int(existing.get("recurrence", 0)) + 1 if existing else 1
        strongest = promotion_state
        if existing:
            strongest = max(PromotionState[existing["promotion_state"]], promotion_state)
        record = {
            "fingerprint": fingerprint,
            "failure_code": str(incident["failure_code"]),
            "claim": str(incident["claim"]),
            "observed_fruit": str(incident["observed_fruit"]),
            "desired_outcome": str(incident["desired_outcome"]),
            "affected_capabilities": sorted(set(map(str, incident.get("affected_capabilities", [])))),
            "reuse_decision": str(incident.get("reuse_decision", "PATCH_EXISTING")),
            "regression_tests": sorted(set(regression_tests).union(existing.get("regression_tests", []) if existing else [])),
            "recurrence": recurrence,
            "promotion_state": strongest.name,
            "promotion_authorized": False,
            "authority_expansion": False,
            "recurring_cost": 0,
        }
        value["incidents"][fingerprint] = record
        if not dry_run:
            self._atomic_write(value)
        return LearningReceipt(
            fingerprint=fingerprint,
            recurrence=recurrence,
            promotion_state=strongest,
            duplicate_suppressed=existing is not None,
            promotion_authorized=False,
            authority_expansion=False,
            manual_user_tasks=(),
        )
