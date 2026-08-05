#!/usr/bin/env python3
"""Prepare and validate a fail-closed owner-custody attestation intake.

This module does not authenticate the caller, grant owner authorization, create
provider authority or perform provider operations. It hash-binds an owner
self-attestation to an already verified custody receipt and copied packet, then
produces a non-authoritative authorization-request candidate that still
requires provider-authenticated owner identity, an exact short-lived owner
decision and fresh provider-native authority readback.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CHALLENGE_SCHEMA = "FEDOMEGA-PHOENIX-OWNER-CUSTODY-ATTESTATION-CHALLENGE-1"
ATTESTATION_SCHEMA = "FEDOMEGA-PHOENIX-OWNER-CUSTODY-ATTESTATION-1"
REQUEST_SCHEMA = "FEDOMEGA-PHOENIX-OWNER-AUTHORIZATION-REQUEST-1"
DECISION_SCHEMA = "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-DECISION-2"
CONFIRMATION = "I ATTEST OWNER-CONTROLLED CUSTODY OF THIS EXACT PACKET"
MAX_WINDOW_SECONDS = 900
MAX_LABEL_LENGTH = 128
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class OwnerCustodyAttestationError(RuntimeError):
    """Fail-closed owner-custody attestation intake error."""


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_custody_module() -> Any:
    path = HERE / "owner_custody_ceremony.py"
    if not path.is_file():
        raise OwnerCustodyAttestationError(
            "required module is missing: owner_custody_ceremony.py"
        )
    spec = importlib.util.spec_from_file_location(
        "phoenix_owner_custody_ceremony_for_attestation", path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnerCustodyAttestationError(f"{label} is unreadable") from exc
    if not isinstance(payload, dict):
        raise OwnerCustodyAttestationError(f"{label} must be a JSON object")
    return payload


def _clean_label(value: object, *, field: str) -> str:
    label = str(value or "").strip()
    if not label or len(label) > MAX_LABEL_LENGTH:
        raise OwnerCustodyAttestationError(f"{field} is missing or too long")
    if any(ord(character) < 32 for character in label):
        raise OwnerCustodyAttestationError(f"{field} contains control characters")
    return label


def _valid_sha256(value: object, *, field: str) -> str:
    digest = str(value or "").lower()
    if not HEX64.fullmatch(digest):
        raise OwnerCustodyAttestationError(f"{field} must be a lowercase SHA-256")
    return digest


def _parse_time(value: object, *, field: str) -> datetime:
    raw = str(value or "")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise OwnerCustodyAttestationError(f"{field} is not a valid timestamp") from exc
    if parsed.tzinfo is None:
        raise OwnerCustodyAttestationError(f"{field} must include timezone")
    return parsed.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _verify_self_hash(payload: dict[str, Any], *, field: str, label: str) -> str:
    claimed = _valid_sha256(payload.get(field), field=field)
    body = dict(payload)
    body.pop(field, None)
    if sha256_bytes(canonical_bytes(body)) != claimed:
        raise OwnerCustodyAttestationError(f"{label} hash verification failed")
    return claimed


def _verify_custody(custody_receipt_path: Path, copied_packet: Path) -> dict[str, Any]:
    custody = _load_custody_module()
    try:
        return custody.verify_receipt(custody_receipt_path, copied_packet=copied_packet)
    except Exception as exc:
        raise OwnerCustodyAttestationError(
            "custody receipt or copied packet verification failed"
        ) from exc


def prepare_challenge(
    *,
    custody_receipt_path: Path,
    copied_packet: Path,
    output: Path,
    execution_route: str,
    issued_at: datetime,
    expires_at: datetime,
) -> dict[str, Any]:
    """Create a deterministic, non-authoritative owner-attestation challenge."""

    receipt = _verify_custody(custody_receipt_path, copied_packet)
    route = _clean_label(execution_route, field="execution_route")
    issued = issued_at.astimezone(timezone.utc)
    expires = expires_at.astimezone(timezone.utc)
    lifetime = (expires - issued).total_seconds()
    if lifetime <= 0 or lifetime > MAX_WINDOW_SECONDS:
        raise OwnerCustodyAttestationError(
            "attestation challenge window must be positive and at most 900 seconds"
        )

    body: dict[str, Any] = {
        "schema": CHALLENGE_SCHEMA,
        "status": "OWNER_ATTESTATION_CHALLENGE_PREPARED_OWNER_RESPONSE_REQUIRED",
        "custody_receipt_sha256": receipt["receipt_sha256"],
        "packet_file_sha256": receipt["packet_file_sha256"],
        "packet_sha256": receipt["packet_sha256"],
        "owner_reference": receipt["owner_reference"],
        "destination_label": receipt["destination_label"],
        "destination_fingerprint": receipt["destination_fingerprint"],
        "execution_route": route,
        "issued_at": _format_time(issued),
        "expires_at": _format_time(expires),
        "required_confirmation": CONFIRMATION,
        "owner_identity_authenticity_required": True,
        "owner_controlled_custody_proven": False,
        "owner_attestation_present": False,
        "owner_authorization_present": False,
        "provider_authority_present": False,
        "provider_apply_performed": False,
        "external_commercial_gate_advanced": False,
        "credential_material_included": False,
    }
    body["challenge_sha256"] = sha256_bytes(canonical_bytes(body))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(body) + b"\n")
    return verify_challenge(
        output,
        custody_receipt_path=custody_receipt_path,
        copied_packet=copied_packet,
        now=issued,
        allow_not_yet_active=True,
    )


def verify_challenge(
    path: Path,
    *,
    custody_receipt_path: Path,
    copied_packet: Path,
    now: datetime,
    allow_not_yet_active: bool = False,
) -> dict[str, Any]:
    payload = _load_json(path, "attestation challenge")
    if payload.get("schema") != CHALLENGE_SCHEMA:
        raise OwnerCustodyAttestationError("attestation challenge schema mismatch")
    _verify_self_hash(payload, field="challenge_sha256", label="attestation challenge")
    if payload.get("status") != "OWNER_ATTESTATION_CHALLENGE_PREPARED_OWNER_RESPONSE_REQUIRED":
        raise OwnerCustodyAttestationError("attestation challenge status is unsafe")
    if payload.get("required_confirmation") != CONFIRMATION:
        raise OwnerCustodyAttestationError("attestation confirmation phrase drift")
    for field in (
        "owner_controlled_custody_proven",
        "owner_attestation_present",
        "owner_authorization_present",
        "provider_authority_present",
        "provider_apply_performed",
        "external_commercial_gate_advanced",
        "credential_material_included",
    ):
        if payload.get(field) is not False:
            raise OwnerCustodyAttestationError(f"unsafe challenge claim: {field}")
    if payload.get("owner_identity_authenticity_required") is not True:
        raise OwnerCustodyAttestationError("owner identity authenticity requirement missing")

    receipt = _verify_custody(custody_receipt_path, copied_packet)
    bindings = {
        "custody_receipt_sha256": receipt["receipt_sha256"],
        "packet_file_sha256": receipt["packet_file_sha256"],
        "packet_sha256": receipt["packet_sha256"],
        "owner_reference": receipt["owner_reference"],
        "destination_label": receipt["destination_label"],
        "destination_fingerprint": receipt["destination_fingerprint"],
    }
    mismatches = sorted(
        field for field, expected in bindings.items() if payload.get(field) != expected
    )
    if mismatches:
        raise OwnerCustodyAttestationError(
            f"attestation challenge custody binding mismatch: {mismatches}"
        )
    _clean_label(payload.get("execution_route"), field="execution_route")
    issued = _parse_time(payload.get("issued_at"), field="issued_at")
    expires = _parse_time(payload.get("expires_at"), field="expires_at")
    lifetime = (expires - issued).total_seconds()
    if lifetime <= 0 or lifetime > MAX_WINDOW_SECONDS:
        raise OwnerCustodyAttestationError("attestation challenge lifetime is invalid")
    observed = now.astimezone(timezone.utc)
    if observed > expires:
        raise OwnerCustodyAttestationError("attestation challenge has expired")
    if observed < issued and not allow_not_yet_active:
        raise OwnerCustodyAttestationError("attestation challenge is not active")
    return payload


def create_attestation(
    *,
    challenge_path: Path,
    custody_receipt_path: Path,
    copied_packet: Path,
    output: Path,
    confirmation: str,
    attested_at: datetime,
) -> dict[str, Any]:
    """Create a self-attestation whose identity authenticity remains unproven."""

    challenge = verify_challenge(
        challenge_path,
        custody_receipt_path=custody_receipt_path,
        copied_packet=copied_packet,
        now=attested_at,
    )
    if confirmation != CONFIRMATION:
        raise OwnerCustodyAttestationError(
            "exact owner-custody attestation confirmation is required"
        )

    body: dict[str, Any] = {
        "schema": ATTESTATION_SCHEMA,
        "status": "OWNER_CUSTODY_SELF_ATTESTED_IDENTITY_AUTHENTICITY_REQUIRED",
        "challenge_sha256": challenge["challenge_sha256"],
        "custody_receipt_sha256": challenge["custody_receipt_sha256"],
        "packet_file_sha256": challenge["packet_file_sha256"],
        "packet_sha256": challenge["packet_sha256"],
        "owner_reference": challenge["owner_reference"],
        "destination_label": challenge["destination_label"],
        "destination_fingerprint": challenge["destination_fingerprint"],
        "execution_route": challenge["execution_route"],
        "confirmation": CONFIRMATION,
        "attested_at": _format_time(attested_at),
        "owner_controlled_custody_self_attested": True,
        "owner_identity_authenticity_proven": False,
        "owner_authorization_present": False,
        "provider_authority_present": False,
        "provider_apply_performed": False,
        "external_commercial_gate_advanced": False,
        "credential_material_included": False,
    }
    body["attestation_sha256"] = sha256_bytes(canonical_bytes(body))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(body) + b"\n")
    verify_attestation_content(
        output,
        challenge_path=challenge_path,
        custody_receipt_path=custody_receipt_path,
        copied_packet=copied_packet,
        now=attested_at,
    )
    return body


def verify_attestation_content(
    path: Path,
    *,
    challenge_path: Path,
    custody_receipt_path: Path,
    copied_packet: Path,
    now: datetime,
) -> dict[str, Any]:
    challenge = verify_challenge(
        challenge_path,
        custody_receipt_path=custody_receipt_path,
        copied_packet=copied_packet,
        now=now,
    )
    payload = _load_json(path, "owner custody attestation")
    if payload.get("schema") != ATTESTATION_SCHEMA:
        raise OwnerCustodyAttestationError("owner attestation schema mismatch")
    attestation_sha = _verify_self_hash(
        payload, field="attestation_sha256", label="owner attestation"
    )
    if payload.get("status") != "OWNER_CUSTODY_SELF_ATTESTED_IDENTITY_AUTHENTICITY_REQUIRED":
        raise OwnerCustodyAttestationError("owner attestation status is unsafe")
    if payload.get("confirmation") != CONFIRMATION:
        raise OwnerCustodyAttestationError("owner attestation confirmation drift")
    expected = {
        "challenge_sha256": challenge["challenge_sha256"],
        "custody_receipt_sha256": challenge["custody_receipt_sha256"],
        "packet_file_sha256": challenge["packet_file_sha256"],
        "packet_sha256": challenge["packet_sha256"],
        "owner_reference": challenge["owner_reference"],
        "destination_label": challenge["destination_label"],
        "destination_fingerprint": challenge["destination_fingerprint"],
        "execution_route": challenge["execution_route"],
    }
    mismatches = sorted(
        field for field, value in expected.items() if payload.get(field) != value
    )
    if mismatches:
        raise OwnerCustodyAttestationError(
            f"owner attestation binding mismatch: {mismatches}"
        )
    if payload.get("owner_controlled_custody_self_attested") is not True:
        raise OwnerCustodyAttestationError("owner custody self-attestation missing")
    for field in (
        "owner_identity_authenticity_proven",
        "owner_authorization_present",
        "provider_authority_present",
        "provider_apply_performed",
        "external_commercial_gate_advanced",
        "credential_material_included",
    ):
        if payload.get(field) is not False:
            raise OwnerCustodyAttestationError(f"unsafe owner attestation claim: {field}")
    attested = _parse_time(payload.get("attested_at"), field="attested_at")
    issued = _parse_time(challenge["issued_at"], field="issued_at")
    expires = _parse_time(challenge["expires_at"], field="expires_at")
    if attested < issued or attested > expires:
        raise OwnerCustodyAttestationError(
            "owner attestation timestamp is outside the challenge window"
        )
    if attested > now.astimezone(timezone.utc):
        raise OwnerCustodyAttestationError("owner attestation timestamp is in the future")
    return {
        "schema": ATTESTATION_SCHEMA,
        "status": "OWNER_ATTESTATION_CONTENT_HASH_BOUND_IDENTITY_AUTHENTICITY_AND_AUTHORIZATION_REQUIRED",
        "attestation_sha256": attestation_sha,
        "challenge_sha256": challenge["challenge_sha256"],
        "custody_receipt_sha256": challenge["custody_receipt_sha256"],
        "packet_file_sha256": challenge["packet_file_sha256"],
        "packet_sha256": challenge["packet_sha256"],
        "owner_reference": challenge["owner_reference"],
        "execution_route": challenge["execution_route"],
        "owner_controlled_custody_self_attested": True,
        "owner_controlled_custody_independently_proven": False,
        "owner_identity_authenticity_proven": False,
        "owner_authorization_present": False,
        "provider_authority_present": False,
        "provider_apply_performed": False,
        "external_commercial_gate_advanced": False,
    }


def compile_authorization_request(
    *,
    attestation_path: Path,
    challenge_path: Path,
    custody_receipt_path: Path,
    copied_packet: Path,
    output: Path,
    now: datetime,
) -> dict[str, Any]:
    """Compile a non-authoritative request for the next owner-reserved decision."""

    verified = verify_attestation_content(
        attestation_path,
        challenge_path=challenge_path,
        custody_receipt_path=custody_receipt_path,
        copied_packet=copied_packet,
        now=now,
    )
    challenge = _load_json(challenge_path, "attestation challenge")
    body: dict[str, Any] = {
        "schema": REQUEST_SCHEMA,
        "status": "OWNER_IDENTITY_PROOF_AND_EXACT_SHORT_LIVED_AUTHORIZATION_DECISION_REQUIRED",
        "requested_decision_schema": DECISION_SCHEMA,
        "challenge_sha256": verified["challenge_sha256"],
        "attestation_sha256": verified["attestation_sha256"],
        "custody_receipt_sha256": verified["custody_receipt_sha256"],
        "packet_file_sha256": verified["packet_file_sha256"],
        "packet_sha256": verified["packet_sha256"],
        "owner_reference": verified["owner_reference"],
        "execution_route": verified["execution_route"],
        "request_expires_at": challenge["expires_at"],
        "provider_authenticated_owner_identity_receipt_required": True,
        "fresh_provider_authority_receipt_required": True,
        "owner_controlled_custody_independently_proven": False,
        "owner_identity_authenticity_proven": False,
        "owner_authorization_present": False,
        "provider_authority_present": False,
        "provider_apply_performed": False,
        "external_commercial_gate_advanced": False,
        "credential_material_included": False,
        "owner_reserved": [
            "packet custody and transfer",
            "execution-plane cutover",
            "consequential release",
            "financial commitments",
            "contracts",
            "external communications",
            "revenue recognition",
        ],
    }
    body["request_sha256"] = sha256_bytes(canonical_bytes(body))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(body) + b"\n")
    return verify_authorization_request(output)


def verify_authorization_request(path: Path) -> dict[str, Any]:
    payload = _load_json(path, "owner authorization request")
    if payload.get("schema") != REQUEST_SCHEMA:
        raise OwnerCustodyAttestationError("owner authorization request schema mismatch")
    _verify_self_hash(payload, field="request_sha256", label="owner authorization request")
    if payload.get("status") != "OWNER_IDENTITY_PROOF_AND_EXACT_SHORT_LIVED_AUTHORIZATION_DECISION_REQUIRED":
        raise OwnerCustodyAttestationError("owner authorization request status is unsafe")
    if payload.get("requested_decision_schema") != DECISION_SCHEMA:
        raise OwnerCustodyAttestationError("owner decision schema drift")
    for field in (
        "owner_controlled_custody_independently_proven",
        "owner_identity_authenticity_proven",
        "owner_authorization_present",
        "provider_authority_present",
        "provider_apply_performed",
        "external_commercial_gate_advanced",
        "credential_material_included",
    ):
        if payload.get(field) is not False:
            raise OwnerCustodyAttestationError(
                f"unsafe owner authorization request claim: {field}"
            )
    if payload.get("provider_authenticated_owner_identity_receipt_required") is not True:
        raise OwnerCustodyAttestationError(
            "provider-authenticated owner identity is not required"
        )
    if payload.get("fresh_provider_authority_receipt_required") is not True:
        raise OwnerCustodyAttestationError("fresh provider authority is not required")
    for field in (
        "challenge_sha256",
        "attestation_sha256",
        "custody_receipt_sha256",
        "packet_file_sha256",
        "packet_sha256",
    ):
        _valid_sha256(payload.get(field), field=field)
    _clean_label(payload.get("owner_reference"), field="owner_reference")
    _clean_label(payload.get("execution_route"), field="execution_route")
    _parse_time(payload.get("request_expires_at"), field="request_expires_at")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--custody-receipt", type=Path, required=True)
    prepare.add_argument("--copied-packet", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--execution-route", required=True)
    prepare.add_argument("--issued-at", required=True)
    prepare.add_argument("--expires-at", required=True)

    attest = subparsers.add_parser("attest")
    attest.add_argument("--challenge", type=Path, required=True)
    attest.add_argument("--custody-receipt", type=Path, required=True)
    attest.add_argument("--copied-packet", type=Path, required=True)
    attest.add_argument("--output", type=Path, required=True)
    attest.add_argument("--confirm", required=True)
    attest.add_argument("--attested-at", required=True)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--attestation", type=Path, required=True)
    verify.add_argument("--challenge", type=Path, required=True)
    verify.add_argument("--custody-receipt", type=Path, required=True)
    verify.add_argument("--copied-packet", type=Path, required=True)
    verify.add_argument("--now", required=True)

    compile_request = subparsers.add_parser("compile-request")
    compile_request.add_argument("--attestation", type=Path, required=True)
    compile_request.add_argument("--challenge", type=Path, required=True)
    compile_request.add_argument("--custody-receipt", type=Path, required=True)
    compile_request.add_argument("--copied-packet", type=Path, required=True)
    compile_request.add_argument("--output", type=Path, required=True)
    compile_request.add_argument("--now", required=True)

    verify_request = subparsers.add_parser("verify-request")
    verify_request.add_argument("--request", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare_challenge(
            custody_receipt_path=args.custody_receipt,
            copied_packet=args.copied_packet,
            output=args.output,
            execution_route=args.execution_route,
            issued_at=_parse_time(args.issued_at, field="issued_at"),
            expires_at=_parse_time(args.expires_at, field="expires_at"),
        )
    elif args.command == "attest":
        result = create_attestation(
            challenge_path=args.challenge,
            custody_receipt_path=args.custody_receipt,
            copied_packet=args.copied_packet,
            output=args.output,
            confirmation=args.confirm,
            attested_at=_parse_time(args.attested_at, field="attested_at"),
        )
    elif args.command == "verify":
        result = verify_attestation_content(
            args.attestation,
            challenge_path=args.challenge,
            custody_receipt_path=args.custody_receipt,
            copied_packet=args.copied_packet,
            now=_parse_time(args.now, field="now"),
        )
    elif args.command == "compile-request":
        result = compile_authorization_request(
            attestation_path=args.attestation,
            challenge_path=args.challenge,
            custody_receipt_path=args.custody_receipt,
            copied_packet=args.copied_packet,
            output=args.output,
            now=_parse_time(args.now, field="now"),
        )
    else:
        result = verify_authorization_request(args.request)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
