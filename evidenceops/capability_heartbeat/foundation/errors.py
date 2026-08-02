"""Typed, public-safe failures for the capability heartbeat foundation."""


class HeartbeatError(ValueError):
    """Base fail-closed validation error."""


class ContractError(HeartbeatError):
    """A strict contract was malformed or semantically invalid."""


class PrivacyError(HeartbeatError):
    """Data exceeded the metadata-only privacy boundary."""


class FreshnessError(HeartbeatError):
    """Data was stale, expired, or implausibly future-dated."""


class ReplayError(HeartbeatError):
    """An identifier was replayed with conflicting content."""


class AuthorityError(HeartbeatError):
    """A child or envelope attempted to widen authority."""


class StopFencedError(HeartbeatError):
    """A stopped or superseded control generation was used."""


class SignatureError(HeartbeatError):
    """A signature or receipt failed deterministic verification."""
