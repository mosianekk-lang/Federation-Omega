from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .action import ACTION, CanaryFailure, CanaryRequest, LockedCanaryAction


FORMATION_AUTHORITY = "A2"


@dataclass(frozen=True)
class RegisteredAction:
    name: str
    authority_class: str
    handler: Callable[[Mapping[str, Any]], Mapping[str, Any]]


class SuperiorV040Registration:
    """Exact, fail-closed source registration for the Federation operator.

    Importing this module has no provider effect. A private operator adapter
    must explicitly install ``registration()`` and then prove the deployed
    allowlist through provider-native contract readback.
    """

    def __init__(self, action: LockedCanaryAction):
        self._action = action

    def dispatch(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(payload, Mapping):
            raise CanaryFailure("PAYLOAD_OBJECT_REQUIRED")
        request = CanaryRequest(**dict(payload))
        result = self._action.execute(request)
        return {
            "ok": True,
            "action": ACTION,
            "authorityClass": FORMATION_AUTHORITY,
            "result": result.__dict__,
        }

    def registration(self) -> RegisteredAction:
        return RegisteredAction(ACTION, FORMATION_AUTHORITY, self.dispatch)


def install_into(
    allowlist: dict[str, RegisteredAction], action: LockedCanaryAction
) -> dict[str, RegisteredAction]:
    """Install exactly one locked action without mutating an existing binding."""

    if ACTION in allowlist:
        raise CanaryFailure("ALLOWLIST_BINDING_ALREADY_EXISTS")
    updated = dict(allowlist)
    registration = SuperiorV040Registration(action).registration()
    if registration.authority_class != FORMATION_AUTHORITY:
        raise CanaryFailure("FORMATION_AUTHORITY_DRIFT")
    updated[ACTION] = registration
    return updated
