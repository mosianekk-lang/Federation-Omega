from __future__ import annotations
from dataclasses import dataclass
from typing import FrozenSet
from .contract import ACTION_REQUIRED_SCOPES, ENTERPRISE_ONLY_ACTIONS, NOT_SELF_SERVE_ACTIONS

@dataclass(frozen=True)
class ActionAuthority:
    action: str
    target: str
    owner_authorized: bool
    policy_authorized: bool
    plan_entitlements: FrozenSet[str]
    granted_scopes: FrozenSet[str]

def validate_action(a: ActionAuthority) -> None:
    if not a.target:
        raise PermissionError("exact target required")
    if not a.owner_authorized or not a.policy_authorized:
        raise PermissionError("action-specific authority required")
    if a.action in ENTERPRISE_ONLY_ACTIONS and "ENTERPRISE" not in a.plan_entitlements:
        raise PermissionError("enterprise entitlement required")
    if a.action in NOT_SELF_SERVE_ACTIONS and "NON_SELF_SERVE" not in a.plan_entitlements:
        raise PermissionError("non-self-serve entitlement required")
    need = ACTION_REQUIRED_SCOPES.get(a.action)
    if need and not need.issubset(a.granted_scopes):
        raise PermissionError("required OAuth scope missing")
