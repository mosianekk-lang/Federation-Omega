"""Privacy-minimized, typed chat handoff state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import BlockerCode, NodeState, canonicalize, digest, enum_value, parse_utc
from .errors import ContractError
from .privacy import minimize_metadata, require_code, require_hash


@dataclass(frozen=True, slots=True)
class ChatHandoff:
    node_id: str
    mission_code: str
    owner_code: str
    matter_code: str
    state: NodeState
    capability_hashes: tuple[str, ...]
    blocker_codes: tuple[BlockerCode, ...]
    observed_at: str
    expires_at: str
    version_code: str
    receipt_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.capability_hashes, (tuple, list)) or not isinstance(self.blocker_codes, (tuple, list)):
            raise ContractError("HANDOFF_TUPLE_SEQUENCE_REQUIRED")
        object.__setattr__(self, "capability_hashes", tuple(self.capability_hashes))
        for field_name in ("node_id", "mission_code", "owner_code", "matter_code", "version_code"):
            require_code(getattr(self, field_name), field=field_name)
        object.__setattr__(self, "state", enum_value(NodeState, self.state, field="state"))
        object.__setattr__(
            self,
            "blocker_codes",
            tuple(enum_value(BlockerCode, item, field="blocker_codes") for item in self.blocker_codes),
        )
        for item in self.capability_hashes:
            require_hash(item, field="capability_hashes")
        parse_utc(self.observed_at, field="observed_at")
        if parse_utc(self.expires_at, field="expires_at") <= parse_utc(self.observed_at, field="observed_at"):
            raise ValueError("HANDOFF_EXPIRY_INVALID")
        require_hash(self.receipt_hash, field="receipt_hash")

    @property
    def handoff_hash(self) -> str:
        return digest(canonicalize(self))

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "ChatHandoff":
        safe = minimize_metadata(
            payload,
            allowed_keys=frozenset(
                {
                    "node_id",
                    "mission_code",
                    "owner_code",
                    "matter_code",
                    "state",
                    "capability_hashes",
                    "blocker_codes",
                    "observed_at",
                    "expires_at",
                    "version_code",
                    "receipt_hash",
                }
            ),
        )
        safe["capability_hashes"] = tuple(safe["capability_hashes"])
        safe["blocker_codes"] = tuple(safe["blocker_codes"])
        return cls(**safe)
