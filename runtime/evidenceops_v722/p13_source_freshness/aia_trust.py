from __future__ import annotations

import hashlib
import socket
import ssl
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import certifi
import requests
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import AuthorityInformationAccessOID


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_certificate(data: bytes) -> x509.Certificate:
    if b"-----BEGIN CERTIFICATE-----" in data:
        return x509.load_pem_x509_certificate(data)
    return x509.load_der_x509_certificate(data)


def peer_leaf(url: str, timeout: int = 30) -> x509.Certificate:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise ValueError(f"URL has no hostname: {url}")
    port = parsed.port or 443
    context = ssl._create_unverified_context()
    with socket.create_connection((host, port), timeout=timeout) as raw:
        with context.wrap_socket(raw, server_hostname=host) as wrapped:
            der = wrapped.getpeercert(binary_form=True)
    if not der:
        raise RuntimeError(f"No peer certificate returned by {host}")
    return x509.load_der_x509_certificate(der)


def ca_issuer_urls(cert: x509.Certificate) -> list[str]:
    try:
        extension = cert.extensions.get_extension_for_class(x509.AuthorityInformationAccess)
    except x509.ExtensionNotFound:
        return []
    urls: list[str] = []
    for descriptor in extension.value:
        if descriptor.access_method == AuthorityInformationAccessOID.CA_ISSUERS:
            value = getattr(descriptor.access_location, "value", None)
            if isinstance(value, str):
                urls.append(value)
    return urls


def build_verified_bundle(url: str, timeout: tuple[int, int] = (20, 60)) -> tuple[str, dict[str, Any]]:
    leaf = peer_leaf(url, timeout=timeout[0])
    chain: list[x509.Certificate] = []
    retrievals: list[dict[str, Any]] = []
    current = leaf

    for _ in range(4):
        urls = ca_issuer_urls(current)
        if not urls:
            break
        issuer_url = urls[0]
        response = requests.get(
            issuer_url,
            timeout=timeout,
            allow_redirects=True,
            verify=certifi.where(),
            headers={"User-Agent": "EvidenceOps-P13-AIA/7.2.2"},
        )
        response.raise_for_status()
        issuer = load_certificate(response.content)
        chain.append(issuer)
        retrievals.append({
            "requested_url": issuer_url,
            "final_url": response.url,
            "status": response.status_code,
            "certificate_sha256": sha256(issuer.public_bytes(serialization.Encoding.DER)),
            "subject": issuer.subject.rfc4514_string(),
            "issuer": issuer.issuer.rfc4514_string(),
        })
        if issuer.subject == issuer.issuer:
            break
        current = issuer

    if not chain:
        raise RuntimeError("Peer certificate did not expose a usable CA Issuers AIA chain")

    directory = Path(tempfile.mkdtemp(prefix="evidenceops-aia-"))
    leaf_path = directory / "leaf.pem"
    intermediate_path = directory / "intermediates.pem"
    bundle_path = directory / "combined-ca.pem"
    leaf_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    intermediate_bytes = b"".join(cert.public_bytes(serialization.Encoding.PEM) for cert in chain)
    intermediate_path.write_bytes(intermediate_bytes)
    bundle_path.write_bytes(Path(certifi.where()).read_bytes() + b"\n" + intermediate_bytes)

    verification = subprocess.run(
        [
            "openssl", "verify",
            "-CAfile", certifi.where(),
            "-untrusted", str(intermediate_path),
            str(leaf_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if verification.returncode != 0:
        raise RuntimeError(
            "AIA chain did not verify to a Certifi root: "
            f"stdout={verification.stdout!r} stderr={verification.stderr!r}"
        )

    metadata = {
        "mode": "CERTIFI_PLUS_AIA_CHAIN_VERIFIED",
        "leaf_sha256": sha256(leaf.public_bytes(serialization.Encoding.DER)),
        "leaf_subject": leaf.subject.rfc4514_string(),
        "leaf_issuer": leaf.issuer.rfc4514_string(),
        "issuer_retrievals": retrievals,
        "openssl_verify_stdout": verification.stdout.strip(),
        "openssl_verify_stderr": verification.stderr.strip(),
    }
    return str(bundle_path), metadata


def verified_get(
    url: str,
    *,
    headers: dict[str, str],
    timeout: tuple[int, int],
) -> tuple[requests.Response, dict[str, Any]]:
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            verify=certifi.where(),
        )
        response.raise_for_status()
        return response, {"mode": "CERTIFI_DEFAULT_VERIFIED"}
    except requests.exceptions.SSLError as initial_error:
        bundle, chain_metadata = build_verified_bundle(url, timeout=timeout)
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            verify=bundle,
        )
        response.raise_for_status()
        chain_metadata["initial_ssl_error"] = str(initial_error)
        return response, chain_metadata
