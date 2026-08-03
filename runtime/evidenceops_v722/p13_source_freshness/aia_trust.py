from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import certifi
import requests

PEM_PATTERN = re.compile(
    rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
    re.DOTALL,
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(command: list[str], *, input_text: str | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def request_with_retries(
    url: str,
    *,
    headers: dict[str, str],
    timeout: tuple[int, int],
    verify: str,
    attempts: int = 3,
) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
                verify=verify,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.SSLError:
            raise
        except (
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
        ) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(attempt * 3)
    raise RuntimeError(f"Provider retrieval failed after {attempts} attempts: {last_error}")


def openssl_certificate_text(pem_path: Path) -> str:
    result = run(["openssl", "x509", "-in", str(pem_path), "-noout", "-subject", "-issuer", "-text"])
    if result.returncode != 0:
        raise RuntimeError(f"OpenSSL could not parse certificate: {result.stderr}")
    return result.stdout


def aia_urls_from_pem(pem_path: Path) -> list[str]:
    text = openssl_certificate_text(pem_path)
    return re.findall(r"CA Issuers\s*-\s*URI:([^\s]+)", text)


def der_sha_from_pem(pem_path: Path) -> str:
    result = subprocess.run(
        ["openssl", "x509", "-in", str(pem_path), "-outform", "DER"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
    return sha256(result.stdout)


def convert_aia_payload_to_pem(raw_path: Path, output_path: Path) -> None:
    attempts = [
        ["openssl", "x509", "-inform", "DER", "-in", str(raw_path), "-out", str(output_path)],
        ["openssl", "x509", "-inform", "PEM", "-in", str(raw_path), "-out", str(output_path)],
        ["openssl", "pkcs7", "-inform", "DER", "-in", str(raw_path), "-print_certs", "-out", str(output_path)],
        ["openssl", "pkcs7", "-inform", "PEM", "-in", str(raw_path), "-print_certs", "-out", str(output_path)],
    ]
    errors: list[str] = []
    for command in attempts:
        result = run(command)
        if result.returncode == 0 and output_path.exists() and PEM_PATTERN.search(output_path.read_bytes()):
            return
        errors.append(result.stderr.strip())
    raise RuntimeError(f"AIA payload was neither X.509 nor PKCS7: {errors}")


def presented_leaf(host: str, port: int, directory: Path, timeout: int) -> Path:
    result = run(
        [
            "openssl", "s_client",
            "-connect", f"{host}:{port}",
            "-servername", host,
            "-showcerts",
        ],
        input_text="",
        timeout=timeout,
    )
    blocks = PEM_PATTERN.findall((result.stdout + "\n" + result.stderr).encode("utf-8"))
    if not blocks:
        raise RuntimeError(f"OpenSSL s_client returned no certificate for {host}: {result.stderr}")
    leaf_path = directory / "leaf.pem"
    leaf_path.write_bytes(blocks[0] + b"\n")
    return leaf_path


def build_verified_bundle(url: str, timeout: tuple[int, int] = (45, 120)) -> tuple[str, dict[str, Any]]:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise ValueError(f"URL has no hostname: {url}")
    port = parsed.port or 443
    directory = Path(tempfile.mkdtemp(prefix="evidenceops-aia-"))
    leaf_path = presented_leaf(host, port, directory, timeout[0])
    intermediate_path = directory / "intermediates.pem"
    intermediate_path.write_bytes(b"")
    retrievals: list[dict[str, Any]] = []
    pending = aia_urls_from_pem(leaf_path)
    seen: set[str] = set()

    for index in range(4):
        if not pending:
            break
        issuer_url = pending.pop(0)
        if issuer_url in seen:
            continue
        seen.add(issuer_url)
        response = request_with_retries(
            issuer_url,
            headers={"User-Agent": "EvidenceOps-P13-AIA/7.2.2"},
            timeout=timeout,
            verify=certifi.where(),
            attempts=3,
        )
        raw_path = directory / f"issuer-{index}.raw"
        pem_path = directory / f"issuer-{index}.pem"
        raw_path.write_bytes(response.content)
        convert_aia_payload_to_pem(raw_path, pem_path)
        pem_bytes = pem_path.read_bytes()
        with intermediate_path.open("ab") as handle:
            handle.write(pem_bytes + b"\n")
        certificate_blocks = PEM_PATTERN.findall(pem_bytes)
        issuer_metadata: list[dict[str, Any]] = []
        for block_index, block in enumerate(certificate_blocks):
            cert_path = directory / f"issuer-{index}-{block_index}.pem"
            cert_path.write_bytes(block + b"\n")
            text = openssl_certificate_text(cert_path)
            issuer_metadata.append({
                "certificate_sha256": der_sha_from_pem(cert_path),
                "subject": next((line.strip() for line in text.splitlines() if line.startswith("subject=")), ""),
                "issuer": next((line.strip() for line in text.splitlines() if line.startswith("issuer=")), ""),
            })
            pending.extend(url for url in aia_urls_from_pem(cert_path) if url not in seen)
        retrievals.append({
            "requested_url": issuer_url,
            "final_url": response.url,
            "status": response.status_code,
            "payload_sha256": sha256(response.content),
            "certificates": issuer_metadata,
        })
        verification = run([
            "openssl", "verify",
            "-CAfile", certifi.where(),
            "-untrusted", str(intermediate_path),
            str(leaf_path),
        ])
        if verification.returncode == 0:
            bundle_path = directory / "combined-ca.pem"
            bundle_path.write_bytes(Path(certifi.where()).read_bytes() + b"\n" + intermediate_path.read_bytes())
            return str(bundle_path), {
                "mode": "CERTIFI_PLUS_OPENSSL_AIA_CHAIN_VERIFIED",
                "leaf_sha256": der_sha_from_pem(leaf_path),
                "issuer_retrievals": retrievals,
                "openssl_verify_stdout": verification.stdout.strip(),
                "openssl_verify_stderr": verification.stderr.strip(),
            }

    final_verification = run([
        "openssl", "verify",
        "-CAfile", certifi.where(),
        "-untrusted", str(intermediate_path),
        str(leaf_path),
    ])
    raise RuntimeError(
        "AIA chain did not verify to a Certifi root: "
        f"stdout={final_verification.stdout!r} stderr={final_verification.stderr!r} "
        f"retrievals={retrievals!r}"
    )


def verified_get(
    url: str,
    *,
    headers: dict[str, str],
    timeout: tuple[int, int],
) -> tuple[requests.Response, dict[str, Any]]:
    try:
        response = request_with_retries(
            url,
            headers=headers,
            timeout=timeout,
            verify=certifi.where(),
            attempts=3,
        )
        return response, {"mode": "CERTIFI_DEFAULT_VERIFIED"}
    except requests.exceptions.SSLError as initial_error:
        bundle, chain_metadata = build_verified_bundle(url, timeout=timeout)
        response = request_with_retries(
            url,
            headers=headers,
            timeout=timeout,
            verify=bundle,
            attempts=3,
        )
        chain_metadata["initial_ssl_error"] = str(initial_error)
        return response, chain_metadata
