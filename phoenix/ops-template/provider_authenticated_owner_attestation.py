#!/usr/bin/env python3
"""Verify provider-authenticated owner attestation readback without applying changes.

The module supports a GET-only GitHub readback route. It can prepare the exact
attestation message, capture authenticated provider state, verify the owner
account/repository/comment bindings, and create a hash-bound identity receipt.
It never posts the attestation, grants owner authorization, creates provider
authority, mutates a repository, or advances an external commercial gate.

Injected transports are always classified as mock conformance and can never
produce an owner-identity authenticity claim.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
EVIDENCE_SCHEMA = "FEDOMEGA-PHOENIX-PROVIDER-AUTHENTICATED-OWNER-ATTESTATION-EVIDENCE-1"
RECEIPT_SCHEMA = "FEDOMEGA-PHOENIX-PROVIDER-AUTHENTICATED-OWNER-ATTESTATION-RECEIPT-1"
PROVIDER = "github"
API_BASE = "https://api.github.com"
WEB_BASE = "https://github.com"
MAX_READBACK_AGE_SECONDS = 300
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class ProviderAuthenticatedOwnerAttestationError(RuntimeError):
    """Fail-closed provider-authenticated owner-attestation error."""


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderAuthenticatedOwnerAttestationError(
            f"{label} is unreadable"
        ) from exc
    if not isinstance(payload, dict):
        raise ProviderAuthenticatedOwnerAttestationError(
            f"{label} must be a JSON object"
        )
    return payload


def _load_attestation_module() -> Any:
    path = HERE / "owner_custody_attestation.py"
    if not path.is_file():
        raise ProviderAuthenticatedOwnerAttestationError(
            "required module is missing: owner_custody_attestation.py"
        )
    spec = importlib.util.spec_from_file_location(
        "phoenix_owner_custody_attestation_for_provider_readback", path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _parse_time(value: object, *, field: str) -> datetime:
    raw = str(value or "")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ProviderAuthenticatedOwnerAttestationError(
            f"{field} is not a valid timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise ProviderAuthenticatedOwnerAttestationError(
            f"{field} must include timezone"
        )
    return parsed.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean_login(value: object, *, field: str) -> str:
    login = str(value or "").strip()
    if not login or len(login) > 39:
        raise ProviderAuthenticatedOwnerAttestationError(
            f"{field} is missing or too long"
        )
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", login):
        raise ProviderAuthenticatedOwnerAttestationError(
            f"{field} is not a valid GitHub login"
        )
    return login


def _clean_repository(value: object) -> str:
    repository = str(value or "").strip()
    if not REPOSITORY.fullmatch(repository):
        raise ProviderAuthenticatedOwnerAttestationError(
            "repository_full_name is invalid"
        )
    return repository


def _valid_sha256(value: object, *, field: str) -> str:
    digest = str(value or "").lower()
    if not HEX64.fullmatch(digest):
        raise ProviderAuthenticatedOwnerAttestationError(
            f"{field} must be a lowercase SHA-256"
        )
    return digest


def _verify_self_hash(
    payload: dict[str, Any], *, field: str, label: str
) -> str:
    claimed = _valid_sha256(payload.get(field), field=field)
    body = dict(payload)
    body.pop(field, None)
    if sha256_bytes(canonical_bytes(body)) != claimed:
        raise ProviderAuthenticatedOwnerAttestationError(
            f"{label} hash verification failed"
        )
    return claimed


def _verify_attestation(
    *,
    attestation_path: Path,
    challenge_path: Path,
    custody_receipt_path: Path,
    copied_packet: Path,
    now: datetime,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    module = _load_attestation_module()
    try:
        attestation = module.verify_attestation_content(
            attestation_path,
            challenge_path=challenge_path,
            custody_receipt_path=custody_receipt_path,
            copied_packet=copied_packet,
            now=now,
        )
        challenge = module.verify_challenge(
            challenge_path,
            custody_receipt_path=custody_receipt_path,
            copied_packet=copied_packet,
            now=now,
        )
    except Exception as exc:
        raise ProviderAuthenticatedOwnerAttestationError(
            "owner custody attestation or challenge verification failed"
        ) from exc
    return module, attestation, challenge


def prepare_provider_message(
    *,
    attestation_path: Path,
    challenge_path: Path,
    custody_receipt_path: Path,
    copied_packet: Path,
    now: datetime,
) -> str:
    """Return the exact low-disclosure message the owner may publish."""

    _, attestation, challenge = _verify_attestation(
        attestation_path=attestation_path,
        challenge_path=challenge_path,
        custody_receipt_path=custody_receipt_path,
        copied_packet=copied_packet,
        now=now,
    )
    return "\n".join(
        (
            "FEDERATION-OMEGA OWNER CUSTODY ATTESTATION",
            f"challenge_sha256={challenge['challenge_sha256']}",
            f"attestation_sha256={attestation['attestation_sha256']}",
            "purpose=provider-authenticated-owner-attestation-readback",
            "authorization=NOT_GRANTED",
            "provider_apply=NOT_PERFORMED",
        )
    )


FetchJson = Callable[[str, dict[str, str]], dict[str, Any]]


def _default_fetch_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 200:
                raise ProviderAuthenticatedOwnerAttestationError(
                    f"GitHub GET returned HTTP {response.status}"
                )
            data = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderAuthenticatedOwnerAttestationError(
            "GitHub provider readback failed"
        ) from exc
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderAuthenticatedOwnerAttestationError(
            "GitHub provider readback returned invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise ProviderAuthenticatedOwnerAttestationError(
            "GitHub provider readback must be a JSON object"
        )
    return payload


def capture_github_readback(
    *,
    repository_full_name: str,
    comment_id: int,
    owner_login: str,
    output: Path,
    captured_at: datetime,
    fetch_json: FetchJson | None = None,
    token_env: str = "GITHUB_TOKEN",
) -> dict[str, Any]:
    """Capture GET-only GitHub owner, repository and comment state.

    A supplied ``fetch_json`` callable is test-only and is permanently labelled
    ``MOCK_CONFORMANCE``. Only the built-in HTTPS route can emit
    ``PROVIDER_NATIVE`` evidence.
    """

    repository = _clean_repository(repository_full_name)
    login = _clean_login(owner_login, field="owner_login")
    if not isinstance(comment_id, int) or comment_id <= 0:
        raise ProviderAuthenticatedOwnerAttestationError(
            "comment_id must be a positive integer"
        )

    mode = "MOCK_CONFORMANCE" if fetch_json is not None else "PROVIDER_NATIVE"
    fetcher = fetch_json or _default_fetch_json
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Federation-Omega-Owner-Attestation/1.0",
    }
    if mode == "PROVIDER_NATIVE":
        token = os.environ.get(token_env, "").strip()
        if not token:
            raise ProviderAuthenticatedOwnerAttestationError(
                f"{token_env} is required for provider-native readback"
            )
        headers["Authorization"] = f"Bearer {token}"

    encoded_repository = repository
    endpoints = {
        "authenticated_user": f"{API_BASE}/user",
        "repository": f"{API_BASE}/repos/{encoded_repository}",
        "comment": f"{API_BASE}/repos/{encoded_repository}/issues/comments/{comment_id}",
    }
    responses = {
        key: fetcher(url, dict(headers)) for key, url in endpoints.items()
    }

    body: dict[str, Any] = {
        "schema": EVIDENCE_SCHEMA,
        "status": (
            "PROVIDER_NATIVE_GET_READBACK_CAPTURED_VERIFICATION_REQUIRED"
            if mode == "PROVIDER_NATIVE"
            else "MOCK_PROVIDER_GET_CONFORMANCE_CAPTURED_NO_IDENTITY_CLAIM"
        ),
        "provider": PROVIDER,
        "capture_mode": mode,
        "api_base": API_BASE,
        "repository_full_name": repository,
        "expected_owner_login": login,
        "comment_id": comment_id,
        "captured_at": _format_time(captured_at),
        "transport": {
            "method": "GET_ONLY",
            "tls_required": True,
            "credential_material_recorded": False,
            "provider_mutation_performed": False,
        },
        "endpoints": endpoints,
        "authenticated_user": responses["authenticated_user"],
        "repository": responses["repository"],
        "comment": responses["comment"],
        "owner_authorization_present": False,
        "provider_authority_created": False,
        "provider_apply_performed": False,
        "external_commercial_gate_advanced": False,
    }
    body["evidence_sha256"] = sha256_bytes(canonical_bytes(body))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(body) + b"\n")
    return body


def verify_github_readback(
    evidence_path: Path,
    *,
    attestation_path: Path,
    challenge_path: Path,
    custody_receipt_path: Path,
    copied_packet: Path,
    repository_full_name: str,
    owner_login: str,
    now: datetime,
    _provider_native_transport: bool = False,
) -> dict[str, Any]:
    """Verify exact provider evidence and return a non-authoritative result.

    File-only verification never authenticates the provider transport. The
    private ``_provider_native_transport`` switch is used solely by
    ``capture_and_write_identity_receipt_live`` immediately after built-in
    HTTPS GETs complete in the same process.
    """

    repository_name = _clean_repository(repository_full_name)
    login = _clean_login(owner_login, field="owner_login")
    _, attestation, challenge = _verify_attestation(
        attestation_path=attestation_path,
        challenge_path=challenge_path,
        custody_receipt_path=custody_receipt_path,
        copied_packet=copied_packet,
        now=now,
    )
    expected_body = prepare_provider_message(
        attestation_path=attestation_path,
        challenge_path=challenge_path,
        custody_receipt_path=custody_receipt_path,
        copied_packet=copied_packet,
        now=now,
    )

    evidence = _load_json(evidence_path, "provider readback evidence")
    evidence_sha = _verify_self_hash(
        evidence, field="evidence_sha256", label="provider readback evidence"
    )
    if evidence.get("schema") != EVIDENCE_SCHEMA:
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider readback evidence schema mismatch"
        )
    mode = evidence.get("capture_mode")
    if mode not in {"PROVIDER_NATIVE", "MOCK_CONFORMANCE"}:
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider readback capture mode is unsafe"
        )
    expected_status = (
        "PROVIDER_NATIVE_GET_READBACK_CAPTURED_VERIFICATION_REQUIRED"
        if mode == "PROVIDER_NATIVE"
        else "MOCK_PROVIDER_GET_CONFORMANCE_CAPTURED_NO_IDENTITY_CLAIM"
    )
    if evidence.get("status") != expected_status:
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider readback status mismatch"
        )
    if evidence.get("provider") != PROVIDER or evidence.get("api_base") != API_BASE:
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider readback route mismatch"
        )
    if evidence.get("repository_full_name") != repository_name:
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider repository binding mismatch"
        )
    if evidence.get("expected_owner_login") != login:
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider owner binding mismatch"
        )
    if not isinstance(evidence.get("comment_id"), int) or evidence["comment_id"] <= 0:
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider comment binding is invalid"
        )

    transport = evidence.get("transport")
    if not isinstance(transport, dict):
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider transport evidence missing"
        )
    required_transport = {
        "method": "GET_ONLY",
        "tls_required": True,
        "credential_material_recorded": False,
        "provider_mutation_performed": False,
    }
    if any(transport.get(key) != value for key, value in required_transport.items()):
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider transport evidence is unsafe"
        )
    for field in (
        "owner_authorization_present",
        "provider_authority_created",
        "provider_apply_performed",
        "external_commercial_gate_advanced",
    ):
        if evidence.get(field) is not False:
            raise ProviderAuthenticatedOwnerAttestationError(
                f"unsafe provider evidence claim: {field}"
            )

    authenticated_user = evidence.get("authenticated_user")
    repository = evidence.get("repository")
    comment = evidence.get("comment")
    if not all(isinstance(item, dict) for item in (authenticated_user, repository, comment)):
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider response objects are missing"
        )

    if authenticated_user.get("login") != login:
        raise ProviderAuthenticatedOwnerAttestationError(
            "authenticated provider user does not match owner"
        )
    if not isinstance(authenticated_user.get("id"), int) or authenticated_user["id"] <= 0:
        raise ProviderAuthenticatedOwnerAttestationError(
            "authenticated provider user id is invalid"
        )
    if repository.get("full_name") != repository_name:
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider repository full name mismatch"
        )
    owner = repository.get("owner")
    if not isinstance(owner, dict) or owner.get("login") != login:
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider repository owner mismatch"
        )
    if repository.get("private") is not False:
        raise ProviderAuthenticatedOwnerAttestationError(
            "attestation repository visibility drift"
        )

    comment_user = comment.get("user")
    if not isinstance(comment_user, dict) or comment_user.get("login") != login:
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider comment author mismatch"
        )
    if comment.get("author_association") != "OWNER":
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider comment author is not repository owner"
        )
    if comment.get("id") != evidence["comment_id"]:
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider comment id mismatch"
        )
    if comment.get("body") != expected_body:
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider comment body does not match exact attestation message"
        )
    api_prefix = f"{API_BASE}/repos/{repository_name}/issues/"
    web_issue_prefix = f"{WEB_BASE}/{repository_name}/issues/"
    web_pull_prefix = f"{WEB_BASE}/{repository_name}/pull/"
    if not str(comment.get("issue_url") or "").startswith(api_prefix):
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider comment issue URL mismatch"
        )
    html_url = str(comment.get("html_url") or "")
    if not (html_url.startswith(web_issue_prefix) or html_url.startswith(web_pull_prefix)):
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider comment web URL mismatch"
        )

    created = _parse_time(comment.get("created_at"), field="comment.created_at")
    updated = _parse_time(comment.get("updated_at"), field="comment.updated_at")
    captured = _parse_time(evidence.get("captured_at"), field="captured_at")
    issued = _parse_time(challenge.get("issued_at"), field="challenge.issued_at")
    expires = _parse_time(challenge.get("expires_at"), field="challenge.expires_at")
    observed = now.astimezone(timezone.utc)
    if updated != created:
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider comment was edited after creation"
        )
    if created < issued or created > expires:
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider comment is outside the attestation challenge window"
        )
    if captured < created or captured > observed:
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider capture timestamp is inconsistent"
        )
    if (observed - captured).total_seconds() > MAX_READBACK_AGE_SECONDS:
        raise ProviderAuthenticatedOwnerAttestationError(
            "provider readback evidence is stale"
        )

    if _provider_native_transport and mode != "PROVIDER_NATIVE":
        raise ProviderAuthenticatedOwnerAttestationError(
            "trusted provider-native transport cannot be asserted for mock evidence"
        )
    provider_native = _provider_native_transport and mode == "PROVIDER_NATIVE"
    if provider_native:
        result_status = (
            "OWNER_IDENTITY_PROVIDER_AUTHENTICATED_OWNER_AUTHORIZATION_REQUIRED"
        )
    elif mode == "PROVIDER_NATIVE":
        result_status = (
            "PROVIDER_NATIVE_EVIDENCE_CONTENT_VERIFIED_LIVE_TRANSPORT_REPLAY_REQUIRED"
        )
    else:
        result_status = "MOCK_PROVIDER_CONFORMANCE_VERIFIED_NO_OWNER_IDENTITY_CLAIM"
    return {
        "schema": EVIDENCE_SCHEMA,
        "status": result_status,
        "provider": PROVIDER,
        "capture_mode": mode,
        "evidence_sha256": evidence_sha,
        "challenge_sha256": challenge["challenge_sha256"],
        "attestation_sha256": attestation["attestation_sha256"],
        "custody_receipt_sha256": attestation["custody_receipt_sha256"],
        "packet_file_sha256": attestation["packet_file_sha256"],
        "packet_sha256": attestation["packet_sha256"],
        "owner_reference": attestation["owner_reference"],
        "repository_full_name": repository_name,
        "owner_login": login,
        "comment_id": evidence["comment_id"],
        "owner_attestation_content_verified": True,
        "owner_attestation_provider_authenticated": provider_native,
        "owner_identity_authenticity_proven": provider_native,
        "owner_controlled_custody_independently_proven": False,
        "owner_authorization_present": False,
        "provider_authority_created": False,
        "provider_apply_performed": False,
        "external_commercial_gate_advanced": False,
    }


def capture_and_write_identity_receipt_live(
    output: Path,
    *,
    evidence_output: Path,
    attestation_path: Path,
    challenge_path: Path,
    custody_receipt_path: Path,
    copied_packet: Path,
    repository_full_name: str,
    comment_id: int,
    owner_login: str,
    now: datetime,
    token_env: str = "GITHUB_TOKEN",
) -> dict[str, Any]:
    """Perform built-in HTTPS GETs and immediately emit an identity receipt."""

    capture_github_readback(
        repository_full_name=repository_full_name,
        comment_id=comment_id,
        owner_login=owner_login,
        output=evidence_output,
        captured_at=now,
        token_env=token_env,
    )
    verified = verify_github_readback(
        evidence_output,
        attestation_path=attestation_path,
        challenge_path=challenge_path,
        custody_receipt_path=custody_receipt_path,
        copied_packet=copied_packet,
        repository_full_name=repository_full_name,
        owner_login=owner_login,
        now=now,
        _provider_native_transport=True,
    )
    body = dict(verified)
    body["schema"] = RECEIPT_SCHEMA
    body["verified_at"] = _format_time(now)
    body["owner_authorization_required"] = True
    body["fresh_provider_authority_required"] = True
    body["exact_short_lived_owner_decision_required"] = True
    body["receipt_sha256"] = sha256_bytes(canonical_bytes(body))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(body) + b"\n")
    verify_identity_receipt(output)
    return body


def write_identity_receipt(
    output: Path,
    *,
    evidence_path: Path,
    attestation_path: Path,
    challenge_path: Path,
    custody_receipt_path: Path,
    copied_packet: Path,
    repository_full_name: str,
    owner_login: str,
    now: datetime,
) -> dict[str, Any]:
    verified = verify_github_readback(
        evidence_path,
        attestation_path=attestation_path,
        challenge_path=challenge_path,
        custody_receipt_path=custody_receipt_path,
        copied_packet=copied_packet,
        repository_full_name=repository_full_name,
        owner_login=owner_login,
        now=now,
    )
    body = dict(verified)
    body["schema"] = RECEIPT_SCHEMA
    body["verified_at"] = _format_time(now)
    body["owner_authorization_required"] = True
    body["fresh_provider_authority_required"] = True
    body["exact_short_lived_owner_decision_required"] = True
    body["receipt_sha256"] = sha256_bytes(canonical_bytes(body))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(body) + b"\n")
    verify_identity_receipt(output)
    return body


def verify_identity_receipt(path: Path) -> dict[str, Any]:
    payload = _load_json(path, "owner identity receipt")
    if payload.get("schema") != RECEIPT_SCHEMA:
        raise ProviderAuthenticatedOwnerAttestationError(
            "owner identity receipt schema mismatch"
        )
    _verify_self_hash(payload, field="receipt_sha256", label="owner identity receipt")
    provider_native = payload.get("owner_identity_authenticity_proven") is True
    if provider_native:
        expected_status = (
            "OWNER_IDENTITY_PROVIDER_AUTHENTICATED_OWNER_AUTHORIZATION_REQUIRED"
        )
    elif payload.get("capture_mode") == "PROVIDER_NATIVE":
        expected_status = (
            "PROVIDER_NATIVE_EVIDENCE_CONTENT_VERIFIED_LIVE_TRANSPORT_REPLAY_REQUIRED"
        )
    else:
        expected_status = "MOCK_PROVIDER_CONFORMANCE_VERIFIED_NO_OWNER_IDENTITY_CLAIM"
    if payload.get("status") != expected_status:
        raise ProviderAuthenticatedOwnerAttestationError(
            "owner identity receipt status mismatch"
        )
    for field in (
        "owner_authorization_present",
        "provider_authority_created",
        "provider_apply_performed",
        "external_commercial_gate_advanced",
        "owner_controlled_custody_independently_proven",
    ):
        if payload.get(field) is not False:
            raise ProviderAuthenticatedOwnerAttestationError(
                f"unsafe owner identity receipt claim: {field}"
            )
    if payload.get("owner_attestation_content_verified") is not True:
        raise ProviderAuthenticatedOwnerAttestationError(
            "owner attestation content verification missing"
        )
    if payload.get("owner_identity_authenticity_proven") is not provider_native:
        raise ProviderAuthenticatedOwnerAttestationError(
            "owner identity authenticity claim does not match capture mode"
        )
    if payload.get("owner_attestation_provider_authenticated") is not provider_native:
        raise ProviderAuthenticatedOwnerAttestationError(
            "owner attestation provider-authentication claim does not match capture mode"
        )
    for field in (
        "owner_authorization_required",
        "fresh_provider_authority_required",
        "exact_short_lived_owner_decision_required",
    ):
        if payload.get(field) is not True:
            raise ProviderAuthenticatedOwnerAttestationError(
                f"required downstream gate missing: {field}"
            )
    _valid_sha256(payload.get("challenge_sha256"), field="challenge_sha256")
    _valid_sha256(payload.get("attestation_sha256"), field="attestation_sha256")
    _valid_sha256(payload.get("evidence_sha256"), field="evidence_sha256")
    _valid_sha256(payload.get("receipt_sha256"), field="receipt_sha256")
    _clean_repository(payload.get("repository_full_name"))
    _clean_login(payload.get("owner_login"), field="owner_login")
    _parse_time(payload.get("verified_at"), field="verified_at")
    return payload


def _parse_datetime(value: str) -> datetime:
    return _parse_time(value, field="timestamp")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GET-only provider-authenticated owner attestation readback"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    message = subparsers.add_parser("prepare-message")
    message.add_argument("--attestation", type=Path, required=True)
    message.add_argument("--challenge", type=Path, required=True)
    message.add_argument("--custody-receipt", type=Path, required=True)
    message.add_argument("--copied-packet", type=Path, required=True)
    message.add_argument("--now", type=_parse_datetime, required=True)

    capture = subparsers.add_parser("capture-github")
    capture.add_argument("--repository", required=True)
    capture.add_argument("--comment-id", type=int, required=True)
    capture.add_argument("--owner-login", required=True)
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument("--captured-at", type=_parse_datetime, required=True)
    capture.add_argument("--token-env", default="GITHUB_TOKEN")

    live = subparsers.add_parser("capture-verify-github-live")
    live.add_argument("--repository", required=True)
    live.add_argument("--comment-id", type=int, required=True)
    live.add_argument("--owner-login", required=True)
    live.add_argument("--evidence-output", type=Path, required=True)
    live.add_argument("--output", type=Path, required=True)
    live.add_argument("--attestation", type=Path, required=True)
    live.add_argument("--challenge", type=Path, required=True)
    live.add_argument("--custody-receipt", type=Path, required=True)
    live.add_argument("--copied-packet", type=Path, required=True)
    live.add_argument("--now", type=_parse_datetime, required=True)
    live.add_argument("--token-env", default="GITHUB_TOKEN")

    verify = subparsers.add_parser("verify")
    verify.add_argument("--evidence", type=Path, required=True)
    verify.add_argument("--attestation", type=Path, required=True)
    verify.add_argument("--challenge", type=Path, required=True)
    verify.add_argument("--custody-receipt", type=Path, required=True)
    verify.add_argument("--copied-packet", type=Path, required=True)
    verify.add_argument("--repository", required=True)
    verify.add_argument("--owner-login", required=True)
    verify.add_argument("--now", type=_parse_datetime, required=True)
    verify.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "prepare-message":
        print(
            prepare_provider_message(
                attestation_path=args.attestation,
                challenge_path=args.challenge,
                custody_receipt_path=args.custody_receipt,
                copied_packet=args.copied_packet,
                now=args.now,
            )
        )
        return 0
    if args.command == "capture-github":
        capture_github_readback(
            repository_full_name=args.repository,
            comment_id=args.comment_id,
            owner_login=args.owner_login,
            output=args.output,
            captured_at=args.captured_at,
            token_env=args.token_env,
        )
        print(args.output)
        return 0
    if args.command == "capture-verify-github-live":
        capture_and_write_identity_receipt_live(
            args.output,
            evidence_output=args.evidence_output,
            attestation_path=args.attestation,
            challenge_path=args.challenge,
            custody_receipt_path=args.custody_receipt,
            copied_packet=args.copied_packet,
            repository_full_name=args.repository,
            comment_id=args.comment_id,
            owner_login=args.owner_login,
            now=args.now,
            token_env=args.token_env,
        )
        print(args.output)
        return 0
    write_identity_receipt(
        args.output,
        evidence_path=args.evidence,
        attestation_path=args.attestation,
        challenge_path=args.challenge,
        custody_receipt_path=args.custody_receipt,
        copied_packet=args.copied_packet,
        repository_full_name=args.repository,
        owner_login=args.owner_login,
        now=args.now,
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
