#!/usr/bin/env python3
"""Build and verify a deterministic no-authority Phoenix owner packet candidate."""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

SCHEMA = "FEDOMEGA-PHOENIX-OWNER-SEALED-PACKET-CANDIDATE-1"
MAX_ARCHIVE_BYTES = 20 * 1024 * 1024


class OwnerSealedPacketError(RuntimeError):
    """Fail-closed packet candidate validation error."""


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


def _safe_member_name(name: str) -> None:
    normalized = PurePosixPath(name)
    if normalized.is_absolute() or ".." in normalized.parts or not normalized.parts:
        raise OwnerSealedPacketError(f"unsafe archive member: {name}")
    parts = normalized.parts
    if any(
        part == ".github" and index + 1 < len(parts) and parts[index + 1] == "workflows"
        for index, part in enumerate(parts)
    ):
        raise OwnerSealedPacketError(f"active workflow path prohibited: {name}")


def _read_manifest(archive: tarfile.TarFile, name: str) -> Mapping[str, Any]:
    try:
        member = archive.getmember(name)
    except KeyError as exc:
        raise OwnerSealedPacketError(f"required manifest missing: {name}") from exc
    stream = archive.extractfile(member)
    if stream is None:
        raise OwnerSealedPacketError(f"manifest is not a regular file: {name}")
    try:
        value = json.loads(stream.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnerSealedPacketError(f"invalid manifest JSON: {name}") from exc
    if not isinstance(value, dict):
        raise OwnerSealedPacketError(f"manifest must be an object: {name}")
    return value


def inspect_archive(payload: bytes, *, target: str) -> dict[str, Any]:
    if not payload or len(payload) > MAX_ARCHIVE_BYTES:
        raise OwnerSealedPacketError(f"{target} archive size is outside the permitted range")
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
            members = archive.getmembers()
            if not members:
                raise OwnerSealedPacketError(f"{target} archive is empty")
            for member in members:
                _safe_member_name(member.name)
                if member.issym() or member.islnk() or member.isdev():
                    raise OwnerSealedPacketError(
                        f"unsafe archive member type: {member.name}"
                    )
                if not (member.isdir() or member.isfile()):
                    raise OwnerSealedPacketError(
                        f"unsupported archive member type: {member.name}"
                    )

            manifest_name = (
                "PHOENIX_CORE_MANIFEST.json"
                if target == "Federation-Omega-Core"
                else "PHOENIX_OPS_MANIFEST.json"
            )
            manifest = _read_manifest(archive, manifest_name)
    except (tarfile.TarError, OSError) as exc:
        raise OwnerSealedPacketError(f"invalid {target} archive") from exc

    if manifest.get("target") != target:
        raise OwnerSealedPacketError(f"{target} manifest target mismatch")
    invariants = manifest.get("invariants")
    if not isinstance(invariants, dict):
        raise OwnerSealedPacketError(f"{target} manifest invariants missing")
    if target == "Federation-Omega-Core":
        required = {
            "workflow_count": 0,
            "runtime_state_count": 0,
            "migration_control_test_count": 0,
            "secret_marker_count": 0,
        }
    else:
        required = {
            "active_workflow_count": 0,
            "legacy_workflow_count": 0,
            "long_lived_credentials": 0,
        }
    for field, expected in required.items():
        if invariants.get(field) != expected:
            raise OwnerSealedPacketError(
                f"{target} invariant failed: {field}={invariants.get(field)!r}"
            )
    return {
        "target": target,
        "member_count": len(members),
        "manifest_sha256": sha256_bytes(canonical_bytes(manifest)),
        "invariants": required,
    }


def _validated_archive(path: Path, expected: Mapping[str, Any], *, target: str) -> tuple[bytes, dict[str, Any]]:
    payload = path.read_bytes()
    actual_sha = sha256_bytes(payload)
    actual_size = len(payload)
    if expected.get("sha256") != actual_sha:
        raise OwnerSealedPacketError(f"{target} SHA-256 mismatch")
    if expected.get("size") != actual_size:
        raise OwnerSealedPacketError(f"{target} size mismatch")
    inspection = inspect_archive(payload, target=target)
    return payload, inspection


def build_packet_candidate(
    *,
    core_archive: Path,
    ops_archive: Path,
    output: Path,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a deterministic, self-verifying candidate without granting authority."""

    source_repository = str(metadata.get("source_repository", "")).strip()
    source_sha = str(metadata.get("source_sha", "")).strip()
    if not source_repository or not source_sha:
        raise OwnerSealedPacketError("source identity is incomplete")
    core_expected = metadata.get("core")
    ops_expected = metadata.get("ops")
    if not isinstance(core_expected, Mapping) or not isinstance(ops_expected, Mapping):
        raise OwnerSealedPacketError("archive metadata is incomplete")

    core_bytes, core_inspection = _validated_archive(
        core_archive, core_expected, target="Federation-Omega-Core"
    )
    ops_bytes, ops_inspection = _validated_archive(
        ops_archive, ops_expected, target="Federation-Omega-Ops"
    )

    body: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "PACKET_CANDIDATE_VERIFIED_OWNER_CONTROLLED_CUSTODY_AND_AUTHORIZATION_REQUIRED",
        "route": "OWNER_ONLY_SEALED_PACKET",
        "source_repository": source_repository,
        "source_sha": source_sha,
        "export_policy_version": metadata.get("export_policy_version"),
        "custody_state": "OWNER_CONTROLLED_CUSTODY_NOT_PROVEN",
        "confidentiality_state": "NOT_ESTABLISHED_NO_OWNER_ENCRYPTION_KEY",
        "authority_state": "OWNER_AUTHORIZATION_NOT_PRESENT",
        "provider_readback_state": "REQUIRED_AFTER_AUTHORIZED_EXECUTION",
        "archives": {
            "core": {
                "name": core_archive.name,
                "sha256": sha256_bytes(core_bytes),
                "size": len(core_bytes),
                "content_base64": base64.b64encode(core_bytes).decode("ascii"),
                "inspection": core_inspection,
            },
            "ops": {
                "name": ops_archive.name,
                "sha256": sha256_bytes(ops_bytes),
                "size": len(ops_bytes),
                "content_base64": base64.b64encode(ops_bytes).decode("ascii"),
                "inspection": ops_inspection,
            },
        },
        "commercial_truth": {
            "customer_demand": "MARKET_PROOF_REQUIRED",
            "signed_customer_contract": "NOT_PROVEN",
            "payment_provider_operation": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
            "cloud_run_operation": "NOT_PROVEN",
            "enterprise_assurance": "UNVERIFIED",
            "partner_adoption": "MARKET_PROOF_REQUIRED",
            "production_scale": "PRODUCTION_PROOF_REQUIRED",
            "verified_live_revenue_events": 0,
            "full_commercial_maturity": False,
            "self_service_saas": "HELD",
            "service_enabled_platform": "VERIFIED_AND_PRIORISED",
        },
        "owner_authority": {
            "financial_commitments": "OWNER_RESERVED",
            "contracts": "OWNER_RESERVED",
            "external_communications": "OWNER_RESERVED",
            "consequential_releases": "OWNER_RESERVED",
            "execution_plane_cutover": "OWNER_RESERVED",
            "revenue_recognition": "OWNER_RESERVED",
        },
        "credential_material_included": False,
        "owner_authorization_consumed": False,
        "provider_apply_performed": False,
        "external_effect_performed": False,
        "external_commercial_gate_advanced": False,
    }
    body["packet_sha256"] = sha256_bytes(canonical_bytes(body))
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_bytes(body) + b"\n"
    output.write_bytes(encoded)
    verified = verify_packet_candidate(output)
    return {
        "schema": SCHEMA,
        "status": verified["status"],
        "path": output.name,
        "packet_sha256": body["packet_sha256"],
        "file_sha256": sha256_bytes(encoded),
        "size": len(encoded),
        "core_sha256": body["archives"]["core"]["sha256"],
        "ops_sha256": body["archives"]["ops"]["sha256"],
        "owner_controlled_custody_proven": False,
        "provider_apply_performed": False,
        "external_commercial_gate_advanced": False,
    }


def verify_packet_candidate(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnerSealedPacketError("packet candidate is unreadable") from exc
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise OwnerSealedPacketError("packet candidate schema mismatch")
    claimed = payload.get("packet_sha256")
    if not isinstance(claimed, str) or len(claimed) != 64:
        raise OwnerSealedPacketError("packet SHA-256 missing")
    body = dict(payload)
    body.pop("packet_sha256", None)
    if sha256_bytes(canonical_bytes(body)) != claimed:
        raise OwnerSealedPacketError("packet SHA-256 verification failed")

    expected_truth = {
        "verified_live_revenue_events": 0,
        "full_commercial_maturity": False,
        "self_service_saas": "HELD",
        "service_enabled_platform": "VERIFIED_AND_PRIORISED",
    }
    truth = payload.get("commercial_truth")
    if not isinstance(truth, dict):
        raise OwnerSealedPacketError("commercial truth missing")
    for field, expected in expected_truth.items():
        if truth.get(field) != expected:
            raise OwnerSealedPacketError(f"commercial truth changed: {field}")
    for field in (
        "credential_material_included",
        "owner_authorization_consumed",
        "provider_apply_performed",
        "external_effect_performed",
        "external_commercial_gate_advanced",
    ):
        if payload.get(field) is not False:
            raise OwnerSealedPacketError(f"unsafe packet claim: {field}")
    if payload.get("custody_state") != "OWNER_CONTROLLED_CUSTODY_NOT_PROVEN":
        raise OwnerSealedPacketError("owner-controlled custody is overclaimed")
    if payload.get("authority_state") != "OWNER_AUTHORIZATION_NOT_PRESENT":
        raise OwnerSealedPacketError("owner authority is overclaimed")

    archives = payload.get("archives")
    if not isinstance(archives, dict):
        raise OwnerSealedPacketError("archive payload missing")
    verified_archives: dict[str, Any] = {}
    for key, target in (
        ("core", "Federation-Omega-Core"),
        ("ops", "Federation-Omega-Ops"),
    ):
        record = archives.get(key)
        if not isinstance(record, dict):
            raise OwnerSealedPacketError(f"{key} archive record missing")
        encoded = record.get("content_base64")
        if not isinstance(encoded, str):
            raise OwnerSealedPacketError(f"{key} archive content missing")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise OwnerSealedPacketError(f"{key} archive encoding invalid") from exc
        if len(raw) != record.get("size") or sha256_bytes(raw) != record.get("sha256"):
            raise OwnerSealedPacketError(f"{key} archive integrity failed")
        inspection = inspect_archive(raw, target=target)
        if inspection != record.get("inspection"):
            raise OwnerSealedPacketError(f"{key} archive inspection drift")
        verified_archives[key] = {
            "sha256": record["sha256"],
            "size": record["size"],
            "inspection": inspection,
        }

    return {
        "schema": SCHEMA,
        "status": "PACKET_CANDIDATE_VERIFIED_OWNER_CONTROLLED_CUSTODY_AND_AUTHORIZATION_REQUIRED",
        "packet_sha256": claimed,
        "archives": verified_archives,
        "provider_apply_performed": False,
        "external_commercial_gate_advanced": False,
    }
