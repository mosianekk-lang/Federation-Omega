#!/usr/bin/env python3
"""Prepare and verify a fail-closed owner-custody ceremony for a Phoenix packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

import owner_sealed_packet as packet

SCHEMA = "FEDOMEGA-PHOENIX-OWNER-CUSTODY-CEREMONY-1"
RECEIPT_SCHEMA = "FEDOMEGA-PHOENIX-OWNER-CUSTODY-COPY-RECEIPT-1"
CONFIRMATION = "ESTABLISH OWNER-CONTROLLED CUSTODY"
MAX_LABEL_LENGTH = 128


class OwnerCustodyCeremonyError(RuntimeError):
    """Fail-closed custody ceremony validation error."""


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clean_label(value: object, *, field: str) -> str:
    label = str(value or "").strip()
    if not label or len(label) > MAX_LABEL_LENGTH:
        raise OwnerCustodyCeremonyError(f"{field} is missing or too long")
    if any(ord(character) < 32 for character in label):
        raise OwnerCustodyCeremonyError(f"{field} contains control characters")
    return label


def _valid_sha256(value: object, *, field: str) -> str:
    digest = str(value or "").lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise OwnerCustodyCeremonyError(f"{field} must be a lowercase SHA-256")
    return digest


def prepare_manifest(
    *,
    packet_path: Path,
    output: Path,
    owner_reference: str,
    destination_label: str,
    destination_fingerprint: str,
) -> dict[str, Any]:
    """Prepare a deterministic ceremony manifest without moving the packet."""

    verified = packet.verify_packet_candidate(packet_path)
    owner_reference = _clean_label(owner_reference, field="owner_reference")
    destination_label = _clean_label(destination_label, field="destination_label")
    destination_fingerprint = _valid_sha256(
        destination_fingerprint, field="destination_fingerprint"
    )
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "CUSTODY_CEREMONY_PREPARED_OWNER_EXECUTION_REQUIRED",
        "route": "OWNER_ONLY_SEALED_PACKET",
        "packet_file_sha256": sha256_file(packet_path),
        "packet_sha256": verified["packet_sha256"],
        "owner_reference": owner_reference,
        "destination_label": destination_label,
        "destination_fingerprint": destination_fingerprint,
        "required_confirmation": CONFIRMATION,
        "copy_mode": "ATOMIC_LOCAL_COPY_0600",
        "owner_controlled_custody_proven": False,
        "owner_attestation_required": True,
        "owner_authorization_present": False,
        "provider_apply_performed": False,
        "external_commercial_gate_advanced": False,
        "credential_material_included": False,
    }
    body["manifest_sha256"] = sha256_bytes(canonical_bytes(body))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(body) + b"\n")
    return verify_manifest(output, packet_path=packet_path)


def verify_manifest(path: Path, *, packet_path: Path | None = None) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnerCustodyCeremonyError("custody manifest is unreadable") from exc
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise OwnerCustodyCeremonyError("custody manifest schema mismatch")
    claimed = _valid_sha256(payload.get("manifest_sha256"), field="manifest_sha256")
    body = dict(payload)
    body.pop("manifest_sha256", None)
    if sha256_bytes(canonical_bytes(body)) != claimed:
        raise OwnerCustodyCeremonyError("custody manifest hash verification failed")
    if payload.get("status") != "CUSTODY_CEREMONY_PREPARED_OWNER_EXECUTION_REQUIRED":
        raise OwnerCustodyCeremonyError("custody status is unsafe")
    if payload.get("required_confirmation") != CONFIRMATION:
        raise OwnerCustodyCeremonyError("custody confirmation phrase drift")
    for field in (
        "owner_controlled_custody_proven",
        "owner_authorization_present",
        "provider_apply_performed",
        "external_commercial_gate_advanced",
        "credential_material_included",
    ):
        if payload.get(field) is not False:
            raise OwnerCustodyCeremonyError(f"unsafe custody claim: {field}")
    if payload.get("owner_attestation_required") is not True:
        raise OwnerCustodyCeremonyError("owner attestation requirement missing")
    _clean_label(payload.get("owner_reference"), field="owner_reference")
    _clean_label(payload.get("destination_label"), field="destination_label")
    _valid_sha256(payload.get("destination_fingerprint"), field="destination_fingerprint")
    _valid_sha256(payload.get("packet_file_sha256"), field="packet_file_sha256")
    _valid_sha256(payload.get("packet_sha256"), field="packet_sha256")
    if packet_path is not None:
        verified = packet.verify_packet_candidate(packet_path)
        if sha256_file(packet_path) != payload["packet_file_sha256"]:
            raise OwnerCustodyCeremonyError("packet file drift from custody manifest")
        if verified["packet_sha256"] != payload["packet_sha256"]:
            raise OwnerCustodyCeremonyError("packet identity drift from custody manifest")
    return payload


def _validate_destination(destination: Path) -> None:
    parent = destination.parent
    if not parent.is_dir() or parent.is_symlink():
        raise OwnerCustodyCeremonyError("destination parent must be a real directory")
    if destination.is_symlink():
        raise OwnerCustodyCeremonyError("destination symlink is prohibited")


def _write_atomic_0600(payload: bytes, destination: Path) -> bool:
    _validate_destination(destination)
    if destination.exists():
        if not destination.is_file():
            raise OwnerCustodyCeremonyError("existing destination is not a regular file")
        current = destination.read_bytes()
        mode = stat.S_IMODE(destination.stat().st_mode)
        if current != payload or mode & 0o077:
            raise OwnerCustodyCeremonyError("existing custody copy drift or unsafe permissions")
        return True

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if destination.exists():
            raise OwnerCustodyCeremonyError("destination appeared during custody copy")
        os.replace(temporary, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()
    return False


def execute_local_copy(
    *,
    packet_path: Path,
    manifest_path: Path,
    destination: Path,
    receipt_output: Path,
    confirmation: str,
) -> dict[str, Any]:
    """Perform a local integrity-preserving copy; owner control still requires attestation."""

    if confirmation != CONFIRMATION:
        raise OwnerCustodyCeremonyError("exact custody confirmation is required")
    manifest = verify_manifest(manifest_path, packet_path=packet_path)
    payload = packet_path.read_bytes()
    idempotent = _write_atomic_0600(payload, destination)
    copied_sha = sha256_file(destination)
    if copied_sha != manifest["packet_file_sha256"]:
        raise OwnerCustodyCeremonyError("custody copy hash verification failed")
    if stat.S_IMODE(destination.stat().st_mode) & 0o077:
        raise OwnerCustodyCeremonyError("custody copy permissions are too broad")

    body: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "status": "CUSTODY_COPY_INTEGRITY_VERIFIED_OWNER_CONTROL_ATTESTATION_REQUIRED",
        "manifest_sha256": manifest["manifest_sha256"],
        "packet_file_sha256": copied_sha,
        "packet_sha256": manifest["packet_sha256"],
        "owner_reference": manifest["owner_reference"],
        "destination_label": manifest["destination_label"],
        "destination_fingerprint": manifest["destination_fingerprint"],
        "destination_file_name": destination.name,
        "copy_mode": "0600",
        "idempotent_replay": idempotent,
        "owner_controlled_custody_proven": False,
        "owner_attestation_required": True,
        "owner_authorization_present": False,
        "provider_apply_performed": False,
        "external_commercial_gate_advanced": False,
    }
    body["receipt_sha256"] = sha256_bytes(canonical_bytes(body))
    receipt_output.parent.mkdir(parents=True, exist_ok=True)
    receipt_output.write_bytes(canonical_bytes(body) + b"\n")
    return verify_receipt(receipt_output, copied_packet=destination)


def verify_receipt(path: Path, *, copied_packet: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnerCustodyCeremonyError("custody receipt is unreadable") from exc
    if not isinstance(payload, dict) or payload.get("schema") != RECEIPT_SCHEMA:
        raise OwnerCustodyCeremonyError("custody receipt schema mismatch")
    claimed = _valid_sha256(payload.get("receipt_sha256"), field="receipt_sha256")
    body = dict(payload)
    body.pop("receipt_sha256", None)
    if sha256_bytes(canonical_bytes(body)) != claimed:
        raise OwnerCustodyCeremonyError("custody receipt hash verification failed")
    if payload.get("status") != "CUSTODY_COPY_INTEGRITY_VERIFIED_OWNER_CONTROL_ATTESTATION_REQUIRED":
        raise OwnerCustodyCeremonyError("custody receipt status is unsafe")
    for field in (
        "owner_controlled_custody_proven",
        "owner_authorization_present",
        "provider_apply_performed",
        "external_commercial_gate_advanced",
    ):
        if payload.get(field) is not False:
            raise OwnerCustodyCeremonyError(f"unsafe custody receipt claim: {field}")
    if payload.get("owner_attestation_required") is not True:
        raise OwnerCustodyCeremonyError("owner attestation requirement missing")
    if not copied_packet.is_file() or copied_packet.is_symlink():
        raise OwnerCustodyCeremonyError("copied packet is unavailable or unsafe")
    if sha256_file(copied_packet) != payload.get("packet_file_sha256"):
        raise OwnerCustodyCeremonyError("copied packet drift from receipt")
    if stat.S_IMODE(copied_packet.stat().st_mode) & 0o077:
        raise OwnerCustodyCeremonyError("copied packet permissions drift")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--packet", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--owner-reference", required=True)
    prepare.add_argument("--destination-label", required=True)
    prepare.add_argument("--destination-fingerprint", required=True)

    copy = subparsers.add_parser("copy")
    copy.add_argument("--packet", type=Path, required=True)
    copy.add_argument("--manifest", type=Path, required=True)
    copy.add_argument("--destination", type=Path, required=True)
    copy.add_argument("--receipt-output", type=Path, required=True)
    copy.add_argument("--confirm", required=True)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--receipt", type=Path, required=True)
    verify.add_argument("--copied-packet", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare_manifest(
            packet_path=args.packet,
            output=args.output,
            owner_reference=args.owner_reference,
            destination_label=args.destination_label,
            destination_fingerprint=args.destination_fingerprint,
        )
    elif args.command == "copy":
        result = execute_local_copy(
            packet_path=args.packet,
            manifest_path=args.manifest,
            destination=args.destination,
            receipt_output=args.receipt_output,
            confirmation=args.confirm,
        )
    else:
        result = verify_receipt(args.receipt, copied_packet=args.copied_packet)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
