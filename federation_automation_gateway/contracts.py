from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping

COMMAND_SCHEMA = "FED-AUTOMATION-COMMAND-V1"
RECEIPT_SCHEMA = "FED-AUTOMATION-RECEIPT-V1"
LEASE_SCHEMA = "FED-AUTOMATION-MISSION-LEASE-V1"


class EffectClass(str, Enum):
    READ = "READ"
    LAB_WRITE = "LAB_WRITE"
    CONTROL_PLANE_WRITE = "CONTROL_PLANE_WRITE"
    PROVIDER_ADMIN_WRITE = "PROVIDER_ADMIN_WRITE"
    DESTRUCTIVE_WRITE = "DESTRUCTIVE_WRITE"
    COMMUNICATION_WRITE = "COMMUNICATION_WRITE"


@dataclass(frozen=True)
class Command:
    command_id: str
    created_at_sast: str
    requested_by_chat: str
    engine: str
    mission_id: str
    lease_id: str
    adapter_id: str
    action: str
    effect_class: EffectClass
    target_alias: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    required_proofs: tuple[str, ...] = ()
    idempotency_key: str = ""
    priority: str = "P2"

    def canonical_payload(self) -> dict[str, Any]:
        body = asdict(self)
        body["effect_class"] = self.effect_class.value
        body["required_proofs"] = list(self.required_proofs)
        body["payload"] = dict(self.payload)
        return {"schema": COMMAND_SCHEMA, **body}

    def digest(self) -> str:
        canonical = json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MissionLease:
    lease_id: str
    state: str
    scope: Mapping[str, Any]
    allowed_effects: tuple[str, ...]
    allowed_targets: tuple[str, ...]
    issued_by: str
    issued_at_sast: str
    expires_at_sast: str
    max_commands: int
    commands_used: int
    rollback_required: bool
    readback_required: bool
    communications_allowed: bool = False
    destructive_allowed: bool = False


@dataclass(frozen=True)
class Decision:
    state: str
    reason: str
    authority_mode: str
    rollback_required: bool
    readback_required: bool
    use_elevated_identity: bool = False
