from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class CapabilityScope(str, Enum):
    PLATFORM_GLOBAL = "PLATFORM_GLOBAL"
    USER_CANONICAL_SYSTEM = "USER_CANONICAL_SYSTEM"
    CURRENT_CHAT = "CURRENT_CHAT"
    CONNECTED_PROVIDER = "CONNECTED_PROVIDER"
    LOCAL_TOOL_CALL = "LOCAL_TOOL_CALL"


class CapabilityState(str, Enum):
    UNKNOWN = "UNKNOWN"
    TOOL_SCHEMA_KNOWN = "TOOL_SCHEMA_KNOWN"
    CONNECTOR_DISCOVERED = "CONNECTOR_DISCOVERED"
    AUTH_OR_SESSION_VALID = "AUTH_OR_SESSION_VALID"
    ROUTE_CALLABLE = "ROUTE_CALLABLE"
    ROUTE_EXECUTED = "ROUTE_EXECUTED"
    READBACK_VERIFIED = "READBACK_VERIFIED"
    OBJECTIVE_COMPLETE = "OBJECTIVE_COMPLETE"


class BlockerKind(str, Enum):
    LOCAL_ROUTE_ERROR = "LOCAL_ROUTE_ERROR"
    INVALID_ARGUMENT_OR_SCHEMA = "INVALID_ARGUMENT_OR_SCHEMA"
    AUTHENTICATION_OR_CONNECTION_REQUIRED = "AUTHENTICATION_OR_CONNECTION_REQUIRED"
    APPROVAL_OR_PERMISSION_REQUIRED = "APPROVAL_OR_PERMISSION_REQUIRED"
    EXTERNAL_DEPENDENCY = "EXTERNAL_DEPENDENCY"
    TRANSIENT_TECHNICAL_LIMITATION = "TRANSIENT_TECHNICAL_LIMITATION"
    SAFETY_OR_POLICY_HARD_BOUNDARY = "SAFETY_OR_POLICY_HARD_BOUNDARY"
    PLATFORM_HARD_LIMIT = "PLATFORM_HARD_LIMIT"
    AUTHORIZED_ROUTE_SPACE_EXHAUSTED = "AUTHORIZED_ROUTE_SPACE_EXHAUSTED"


class TerminalClaim(str, Enum):
    CAN = "CAN"
    CANNOT = "CANNOT"
    DONE = "DONE"


class GateDecision(str, Enum):
    ALLOW_BOUNDED = "ALLOW_BOUNDED"
    DENY_TERMINAL_CLAIM = "DENY_TERMINAL_CLAIM"


@dataclass(frozen=True)
class RouteAttempt:
    route_id: str
    blocker: BlockerKind | None = None
    succeeded: bool = False
    readback_verified: bool = False
    evidence_ref: str = ""
    materially_distinct: bool = True

    def validate(self) -> "RouteAttempt":
        if not self.route_id.strip():
            raise ValueError("route_id is required")
        if self.succeeded and self.blocker is not None:
            raise ValueError("successful route cannot also carry a blocker")
        if self.readback_verified and not self.succeeded:
            raise ValueError("readback_verified requires succeeded route")
        return self


@dataclass(frozen=True)
class CapabilityDecisionRequest:
    objective: str
    claim: TerminalClaim
    scope: CapabilityScope
    state: CapabilityState
    current_discovery_ref: str = ""
    provider_readback_ref: str = ""
    route_attempts: tuple[RouteAttempt, ...] = ()
    blocker: BlockerKind | None = None
    equivalent_routes_checked: bool = False
    internal_executable_dependencies: int = 0
    exact_platform_scope: bool = False
    manual_user_action_proposed: bool = False

    def validate(self) -> "CapabilityDecisionRequest":
        if not self.objective.strip():
            raise ValueError("objective is required")
        if self.internal_executable_dependencies < 0:
            raise ValueError("internal_executable_dependencies must be non-negative")
        for route in self.route_attempts:
            route.validate()
        return self


@dataclass(frozen=True)
class CapabilityDecision:
    decision: GateDecision
    allowed_language: str
    reason_codes: tuple[str, ...]
    scope: CapabilityScope
    resolved_state: CapabilityState
    manual_user_action_allowed: bool = False


class CapabilityResolutionGate:
    """Fail-closed pre-response gate for capability and completion claims.

    This gate deliberately separates route failure from objective incapability.
    It does not discover tools itself; callers must pass current discovery,
    route-attempt and readback evidence from the active environment.
    """

    non_terminal_blockers = {
        BlockerKind.LOCAL_ROUTE_ERROR,
        BlockerKind.INVALID_ARGUMENT_OR_SCHEMA,
        BlockerKind.AUTHENTICATION_OR_CONNECTION_REQUIRED,
        BlockerKind.APPROVAL_OR_PERMISSION_REQUIRED,
        BlockerKind.EXTERNAL_DEPENDENCY,
        BlockerKind.TRANSIENT_TECHNICAL_LIMITATION,
    }

    def _distinct_routes(self, request: CapabilityDecisionRequest) -> int:
        return len({r.route_id for r in request.route_attempts if r.materially_distinct})

    def _has_verified_success(self, request: CapabilityDecisionRequest) -> bool:
        return any(r.succeeded and r.readback_verified for r in request.route_attempts)

    def evaluate(self, request: CapabilityDecisionRequest) -> CapabilityDecision:
        request.validate()
        reasons: list[str] = []

        if request.claim is TerminalClaim.CAN:
            if request.state not in {CapabilityState.READBACK_VERIFIED, CapabilityState.OBJECTIVE_COMPLETE}:
                reasons.append("CAN_REQUIRES_READBACK_VERIFIED_STATE")
            if not request.provider_readback_ref.strip() and not self._has_verified_success(request):
                reasons.append("CAN_REQUIRES_READBACK_RECEIPT")
            if reasons:
                return CapabilityDecision(
                    GateDecision.DENY_TERMINAL_CLAIM,
                    "Capability is not yet proven for this action and scope.",
                    tuple(reasons),
                    request.scope,
                    request.state,
                )
            return CapabilityDecision(
                GateDecision.ALLOW_BOUNDED,
                "Capability is verified for the tested action and scope.",
                (),
                request.scope,
                request.state,
            )

        if request.claim is TerminalClaim.DONE:
            if request.state is not CapabilityState.OBJECTIVE_COMPLETE:
                reasons.append("DONE_REQUIRES_OBJECTIVE_COMPLETE_STATE")
            if request.internal_executable_dependencies != 0:
                reasons.append("DONE_REQUIRES_ZERO_EXECUTABLE_INTERNAL_DEPENDENCIES")
            if not request.provider_readback_ref.strip() and not self._has_verified_success(request):
                reasons.append("DONE_REQUIRES_READBACK_RECEIPT")
            if reasons:
                return CapabilityDecision(
                    GateDecision.DENY_TERMINAL_CLAIM,
                    "The objective is not yet proof-bound complete.",
                    tuple(reasons),
                    request.scope,
                    request.state,
                )
            return CapabilityDecision(
                GateDecision.ALLOW_BOUNDED,
                "The objective is verified complete for the stated scope.",
                (),
                request.scope,
                request.state,
            )

        # CANNOT is a capability claim and therefore receives an explicit proof burden.
        blocker = request.blocker
        if blocker in self.non_terminal_blockers:
            return CapabilityDecision(
                GateDecision.DENY_TERMINAL_CLAIM,
                self._bounded_blocker_language(blocker),
                ("ROUTE_OR_DEPENDENCY_BLOCKER_IS_NOT_OBJECTIVE_INCAPABILITY",),
                request.scope,
                request.state,
                manual_user_action_allowed=False,
            )

        if blocker is BlockerKind.SAFETY_OR_POLICY_HARD_BOUNDARY:
            return CapabilityDecision(
                GateDecision.ALLOW_BOUNDED,
                "I cannot assist with the prohibited action because a governing safety or policy boundary applies; allowed alternatives remain in scope.",
                ("HARD_SAFETY_OR_POLICY_BOUNDARY",),
                request.scope,
                request.state,
                manual_user_action_allowed=False,
            )

        if blocker is BlockerKind.PLATFORM_HARD_LIMIT:
            if not request.exact_platform_scope:
                reasons.append("PLATFORM_LIMIT_MUST_BE_BOUND_TO_EXACT_PLATFORM_SCOPE")
            if not request.equivalent_routes_checked:
                reasons.append("PLATFORM_LIMIT_REQUIRES_EQUIVALENT_ROUTE_CHECK")
            if not request.current_discovery_ref.strip():
                reasons.append("PLATFORM_LIMIT_REQUIRES_CURRENT_BOUNDARY_EVIDENCE")
            if reasons:
                return CapabilityDecision(
                    GateDecision.DENY_TERMINAL_CLAIM,
                    "The exact platform-level route may be limited, but equivalent authorized implementations have not yet been resolved.",
                    tuple(reasons),
                    request.scope,
                    request.state,
                )
            return CapabilityDecision(
                GateDecision.ALLOW_BOUNDED,
                "The exact platform-level action is unavailable; equivalent authorized routes were checked separately.",
                ("EXACT_SCOPE_PLATFORM_HARD_LIMIT",),
                request.scope,
                request.state,
                manual_user_action_allowed=request.manual_user_action_proposed,
            )

        if blocker is BlockerKind.AUTHORIZED_ROUTE_SPACE_EXHAUSTED:
            if not request.current_discovery_ref.strip():
                reasons.append("ROUTE_EXHAUSTION_REQUIRES_CURRENT_DISCOVERY_EVIDENCE")
            if not request.equivalent_routes_checked:
                reasons.append("ROUTE_EXHAUSTION_REQUIRES_EQUIVALENT_ROUTE_CHECK")
            if not request.route_attempts:
                reasons.append("ROUTE_EXHAUSTION_REQUIRES_ROUTE_ATTEMPT_LEDGER")
            if any(r.succeeded and r.readback_verified for r in request.route_attempts):
                reasons.append("ROUTE_EXHAUSTION_CONTRADICTED_BY_VERIFIED_SUCCESS")
            if reasons:
                return CapabilityDecision(
                    GateDecision.DENY_TERMINAL_CLAIM,
                    "The authorized route space is not yet proven exhausted.",
                    tuple(reasons),
                    request.scope,
                    request.state,
                )
            route_count = self._distinct_routes(request)
            return CapabilityDecision(
                GateDecision.ALLOW_BOUNDED,
                "I cannot complete this objective in the current authorized environment; the checked route space is exhausted and the remaining dependency is stated separately.",
                (f"AUTHORIZED_ROUTE_SPACE_EXHAUSTED:{route_count}_DISTINCT_ROUTES",),
                request.scope,
                request.state,
                manual_user_action_allowed=request.manual_user_action_proposed,
            )

        return CapabilityDecision(
            GateDecision.DENY_TERMINAL_CLAIM,
            "Capability is unresolved; current discovery and blocker classification are required before an objective-level incapability claim.",
            ("CANNOT_REQUIRES_TYPED_TERMINAL_BLOCKER",),
            request.scope,
            request.state,
            manual_user_action_allowed=False,
        )

    @staticmethod
    def _bounded_blocker_language(blocker: BlockerKind) -> str:
        language = {
            BlockerKind.LOCAL_ROUTE_ERROR: "This route failed; the objective remains unresolved and alternate authorized routes must be checked.",
            BlockerKind.INVALID_ARGUMENT_OR_SCHEMA: "The attempted route or parameters are invalid; discover the correct schema/metadata and retry or switch route.",
            BlockerKind.AUTHENTICATION_OR_CONNECTION_REQUIRED: "This provider route is not currently authenticated or connected; alternate connected routes and current connection options must still be checked.",
            BlockerKind.APPROVAL_OR_PERMISSION_REQUIRED: "This action requires approval or permission; independent safe work remains executable.",
            BlockerKind.EXTERNAL_DEPENDENCY: "An external dependency remains; internal executable work must be dispositioned separately.",
            BlockerKind.TRANSIENT_TECHNICAL_LIMITATION: "The current route is temporarily unavailable; retry reasonably or use a materially different authorized route.",
        }
        return language[blocker]


__all__ = [
    "BlockerKind",
    "CapabilityDecision",
    "CapabilityDecisionRequest",
    "CapabilityResolutionGate",
    "CapabilityScope",
    "CapabilityState",
    "GateDecision",
    "RouteAttempt",
    "TerminalClaim",
]
