from __future__ import annotations

from dataclasses import dataclass

from .errors import AuthorizationDenied
from .models import ActionClass, AuthorityClass, CapabilityRequest

_AUTHORITY_RANK = {item: rank for rank, item in enumerate(AuthorityClass)}


@dataclass(frozen=True)
class PolicyRule:
    connector: str
    action: str
    resource_prefix: str
    minimum_authority: AuthorityClass
    action_class: ActionClass = ActionClass.READ

    def matches(self, request: CapabilityRequest) -> bool:
        return (
            self.connector == request.connector
            and self.action == request.action
            and request.secret.reference_id.startswith(self.resource_prefix)
            and _AUTHORITY_RANK[request.identity.authority] >= _AUTHORITY_RANK[self.minimum_authority]
        )


class LeastPrivilegePolicy:
    def __init__(self, rules: list[PolicyRule] | tuple[PolicyRule, ...]) -> None:
        self._rules = tuple(rules)

    def authorize(self, request: CapabilityRequest) -> PolicyRule:
        matches = [rule for rule in self._rules if rule.matches(request)]
        if len(matches) != 1:
            raise AuthorizationDenied("request is not authorized by exactly one policy rule")
        rule = matches[0]
        if rule.action_class in {ActionClass.WRITE, ActionClass.DEPLOY, ActionClass.ADMIN}:
            raise AuthorizationDenied("consequential actions require a separate effectful permit")
        return rule
