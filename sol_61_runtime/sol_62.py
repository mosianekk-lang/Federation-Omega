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
]
