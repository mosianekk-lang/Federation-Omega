from __future__ import annotations

from datetime import datetime
import fnmatch
from typing import Iterable

from .chat_inheritance import ENGINE_ALLOWLIST, engine_allowed
from .contracts import Command, Decision, EffectClass, MissionLease

# Reusable mission leases intentionally never authorize outbound communication
# or destructive action families. Those retain their separate exact-user gate.
FORBIDDEN_REUSABLE_PREFIXES = (
    "SEND_",
    "REPLY_",
    "FORWARD_",
    "EMAIL_",
    "DELETE_",
    "PURGE_",
    "DESTROY_",
    "DROP_",
)


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _matches_any(value: str, patterns: Iterable[str]) -> bool:
    patterns = tuple(patterns)
    return not patterns or any(fnmatch.fnmatchcase(value, pattern) for pattern in patterns)


def evaluate(command: Command, lease: MissionLease | None, *, now: datetime) -> Decision:
    if not engine_allowed(command.engine):
        return Decision("DENY", "Unknown engine profile.", "NONE", True, True)

    action = command.action.strip().upper()
    if any(action.startswith(prefix) for prefix in FORBIDDEN_REUSABLE_PREFIXES):
        return Decision(
            "DENY",
            "Reusable Federation automation authority never covers communications or destructive action families.",
            "ONE_USE_EXPLICIT",
            True,
            True,
        )

    if command.effect_class is EffectClass.READ:
        return Decision(
            "ALLOW",
            "Read-only action is autonomous.",
            "AUTO_READ",
            False,
            True,
        )

    if command.effect_class is EffectClass.LAB_WRITE:
        return Decision(
            "ALLOW",
            "Non-serving lab mutation is autonomous with rollback and semantic readback.",
            "AUTO_LAB",
            True,
            True,
        )

    if command.effect_class is EffectClass.COMMUNICATION_WRITE:
        return Decision(
            "DENY",
            "Outbound communications require a separate explicit user send/forward/reply directive.",
            "EXPLICIT_USER_ONLY",
            False,
            True,
        )

    if command.effect_class is EffectClass.DESTRUCTIVE_WRITE:
        return Decision(
            "DENY",
            "Destructive actions require a one-use exact-target execution lease.",
            "ONE_USE_EXPLICIT",
            True,
            True,
        )

    if lease is None:
        return Decision(
            "DENY",
            "An active mission lease is required for control-plane/provider-admin mutation.",
            "MISSION_LEASE",
            True,
            True,
        )

    if lease.state != "ACTIVE":
        return Decision(
            "DENY",
            f"Mission lease is not active: {lease.state}.",
            "MISSION_LEASE",
            True,
            True,
        )

    if now > _parse_time(lease.expires_at_sast):
        return Decision("DENY", "Mission lease expired.", "MISSION_LEASE", True, True)

    if lease.max_commands > 0 and lease.commands_used >= lease.max_commands:
        return Decision(
            "DENY",
            "Mission lease command budget exhausted.",
            "MISSION_LEASE",
            True,
            True,
        )

    if command.effect_class.value not in set(lease.allowed_effects):
        return Decision(
            "DENY",
            "Effect class is outside the mission lease.",
            "MISSION_LEASE",
            True,
            True,
        )

    if not _matches_any(command.target_alias, lease.allowed_targets):
        return Decision(
            "DENY",
            "Target alias is outside the mission lease.",
            "MISSION_LEASE",
            True,
            True,
        )

    return Decision(
        "ALLOW",
        "Command is inside the active mission lease and remains proof/rollback gated.",
        "MISSION_LEASE",
        lease.rollback_required,
        lease.readback_required,
        use_elevated_identity=command.effect_class is EffectClass.PROVIDER_ADMIN_WRITE,
    )
