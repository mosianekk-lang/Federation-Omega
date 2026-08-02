"""Private, metadata-only HTTP adapter for the verified heartbeat authority."""

from .runtime import HeartbeatApiRuntime, RuntimeConfig, build_runtime_from_env
from .store import InMemoryImmutableStore, LocalImmutableObjectStore


def create_app(runtime=None):
    """Import the optional HTTP transport only when it is requested."""
    from .service import create_app as build_app

    return build_app(runtime)

__all__ = (
    "HeartbeatApiRuntime",
    "InMemoryImmutableStore",
    "LocalImmutableObjectStore",
    "RuntimeConfig",
    "build_runtime_from_env",
    "create_app",
)
