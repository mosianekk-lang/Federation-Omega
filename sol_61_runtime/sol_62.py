from __future__ import annotations

try:
    from .sol_62_frontier_primitives import *  # noqa: F401,F403
    from .sol_62_google_surface_mesh import (
        GoogleSurfaceMesh,
        NoVerifiedRoute,
        Operation as GoogleOperation,
        RouteDecision as GoogleRouteDecision,
        load_google_surface_mesh,
    )
    from .sol_62_runtime import ExecutionIntent, MissionSpec, TransitionSpec
    from .sol_62_strict_runtime import Sol62StrictRuntime
    from .sol_62_intelligence_amplifier import (
        CognitionProfile,
        IntelligencePlan,
        ReasoningMode,
        compile_intelligence_plan,
    )
    from .sol_62_complete_client_runtime import (
        ClientRuntimePolicy,
        ExecutionResponse,
        HarvestOutcome,
        RouteCandidate,
        Sol62CompleteClientRuntime,
        TransitionBinding,
        classify_provider_constraint,
    )
except ImportError:
    from sol_62_frontier_primitives import *  # noqa: F401,F403
    from sol_62_google_surface_mesh import (
        GoogleSurfaceMesh,
        NoVerifiedRoute,
        Operation as GoogleOperation,
        RouteDecision as GoogleRouteDecision,
        load_google_surface_mesh,
    )
    from sol_62_runtime import ExecutionIntent, MissionSpec, TransitionSpec
    from sol_62_strict_runtime import Sol62StrictRuntime
    from sol_62_intelligence_amplifier import (
        CognitionProfile,
        IntelligencePlan,
        ReasoningMode,
        compile_intelligence_plan,
    )
    from sol_62_complete_client_runtime import (
        ClientRuntimePolicy,
        ExecutionResponse,
        HarvestOutcome,
        RouteCandidate,
        Sol62CompleteClientRuntime,
        TransitionBinding,
        classify_provider_constraint,
    )


# Canonical SOL 6.2 runtime: strict semantic binding facade over the
# transactional base implementation.
Sol62Runtime = Sol62StrictRuntime

__all__ = [
    "Sol62Runtime",
    "Sol62StrictRuntime",
    "MissionSpec",
    "TransitionSpec",
    "ExecutionIntent",
    "GoogleSurfaceMesh",
    "GoogleOperation",
    "GoogleRouteDecision",
    "NoVerifiedRoute",
    "load_google_surface_mesh",
    "Sol62CompleteClientRuntime",
    "ClientRuntimePolicy",
    "RouteCandidate",
    "TransitionBinding",
    "ExecutionResponse",
    "HarvestOutcome",
    "classify_provider_constraint",
    "CognitionProfile",
    "IntelligencePlan",
    "ReasoningMode",
    "compile_intelligence_plan",
]
