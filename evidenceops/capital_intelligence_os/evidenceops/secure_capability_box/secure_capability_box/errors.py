class SecureBoxError(RuntimeError):
    """Base class for safe, non-secret-bearing broker failures."""


class InvalidRequest(SecureBoxError):
    pass


class AuthorizationDenied(SecureBoxError):
    pass


class InvalidHandle(SecureBoxError):
    pass


class ExpiredHandle(InvalidHandle):
    pass


class RevokedHandle(InvalidHandle):
    pass


class ReplayDetected(InvalidHandle):
    pass


class OperationConflict(SecureBoxError):
    pass


class ProviderUnavailable(SecureBoxError):
    pass


class ConnectorFailure(SecureBoxError):
    pass


class IntegrityFailure(SecureBoxError):
    pass
