"""Public-safe failures for the private heartbeat API boundary."""


class HeartbeatApiError(ValueError):
    """Base API error; messages are never returned directly to callers."""


class AuthenticationDenied(HeartbeatApiError):
    """Application-internal authentication failed."""


class RuntimeUnavailable(HeartbeatApiError):
    """The runtime cannot safely serve the requested operation."""


class ResourceNotFound(HeartbeatApiError):
    """A metadata resource does not exist."""


class ImmutableConflict(HeartbeatApiError):
    """An immutable key was replayed with different bytes or meaning."""


class MetadataBoundaryViolation(HeartbeatApiError):
    """Input crossed the metadata-only privacy boundary."""
