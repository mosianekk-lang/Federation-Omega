"""Fail-closed SPIFFE X.509-SVID authorization for the SEB HTTP boundary.

SPIRE (or another conforming Workload API client/helper) materializes the
workload's X.509-SVID, private key, and trust bundle.  TLS verifies possession
and the chain; this module then authorizes the URI SAN by exact SPIFFE ID.
"""
from __future__ import annotations

from dataclasses import dataclass
import hmac
from pathlib import Path
import ssl
from urllib.parse import urlsplit


class SpiffeAuthorizationError(PermissionError):
    """The TLS peer is authenticated but not authorized for this endpoint."""


def validate_spiffe_id(value: str) -> str:
    """Return a canonical SPIFFE ID or reject non-conforming/ambiguous input."""
    parsed = urlsplit(value)
    if (parsed.scheme != "spiffe" or not parsed.netloc or parsed.username is not None
            or parsed.password is not None or parsed.port is not None
            or not parsed.path.startswith("/") or parsed.path == "/"
            or parsed.query or parsed.fragment or "//" in parsed.path):
        raise ValueError("invalid SPIFFE ID")
    # SPIFFE IDs are ASCII and have a lower-case trust domain.  Refuse to
    # normalize: authorization must compare the exact identity issued.
    if parsed.netloc != parsed.netloc.lower() or value != value.encode("ascii").decode("ascii"):
        raise ValueError("non-canonical SPIFFE ID")
    return value


def peer_spiffe_ids(peer_certificate: dict) -> tuple[str, ...]:
    """Extract valid URI SAN SPIFFE IDs from ``SSLSocket.getpeercert()``."""
    identities: list[str] = []
    for san_type, san_value in peer_certificate.get("subjectAltName", ()):
        if san_type != "URI" or not san_value.startswith("spiffe://"):
            continue
        identities.append(validate_spiffe_id(san_value))
    return tuple(identities)


@dataclass(frozen=True)
class ExactSVIDAuthorizer:
    allowed_spiffe_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.allowed_spiffe_ids:
            raise ValueError("at least one allowed SPIFFE ID is required")
        canonical = tuple(validate_spiffe_id(item) for item in self.allowed_spiffe_ids)
        if len(set(canonical)) != len(canonical):
            raise ValueError("duplicate allowed SPIFFE ID")

    def authorize(self, peer_certificate: dict | None) -> str:
        if not peer_certificate:
            raise SpiffeAuthorizationError("client X.509-SVID missing")
        presented = peer_spiffe_ids(peer_certificate)
        # An X.509-SVID has exactly one URI SAN.  Multiple identities are
        # ambiguous and therefore rejected even if one happens to be allowed.
        if len(presented) != 1:
            raise SpiffeAuthorizationError("client certificate must contain one SPIFFE ID")
        identity = presented[0]
        if not any(hmac.compare_digest(identity, allowed)
                   for allowed in self.allowed_spiffe_ids):
            raise SpiffeAuthorizationError("SPIFFE ID is not authorized")
        return identity


def server_ssl_context(svid_cert: str | Path, svid_key: str | Path,
                       trust_bundle: str | Path) -> ssl.SSLContext:
    """Create a TLS server context from files populated via the Workload API."""
    paths = tuple(Path(item) for item in (svid_cert, svid_key, trust_bundle))
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing SPIFFE material: " + ", ".join(missing))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_cert_chain(str(paths[0]), str(paths[1]))
    context.load_verify_locations(cafile=str(paths[2]))
    return context
