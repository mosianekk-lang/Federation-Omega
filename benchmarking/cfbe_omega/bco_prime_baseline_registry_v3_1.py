"""Trust-pinned, one-time-signed baselines for BCO-Prime v3.1.

The module uses a deterministic Lamport SHA-256 one-time signature derived from
an explicitly injected 32-byte seed.  The seed is never returned or persisted.
Verification is meaningful only when the public-key fingerprint is supplied by
an external trusted receipt; registry-contained key substitution is rejected.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


SCHEMA = "BCO_PRIME_BASELINE_REGISTRY_V3_1"
VERSION = "3.1.0"
SIGNATURE_ALGORITHM = "LAMPORT-SHA256-OTS-V1"
MAX_TRACKED_FILES = 10_000
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 20_000


class BaselineContractError(ValueError):
    """Raised when baseline input, lineage or signatures are unsafe."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _strict_normalize(value: Any, path: str = "$") -> Any:
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if value != value or value in (float("inf"), float("-inf")):
            raise BaselineContractError(f"non-finite number at {path}")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise BaselineContractError(f"non-string key at {path}")
            result[key] = _strict_normalize(value[key], f"{path}.{key}")
        return result
    if isinstance(value, (list, tuple)):
        return [_strict_normalize(item, f"{path}[]") for item in value]
    raise BaselineContractError(f"unsupported value at {path}: {type(value).__name__}")


def _safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise BaselineContractError("path must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise BaselineContractError("path traversal rejected")
    return path.as_posix()


def secure_file_sha256(root: Path, relative: str, *, max_bytes: int = MAX_FILE_BYTES) -> dict[str, Any]:
    """Hash one contained regular file and detect replacement during reading."""
    relative = _safe_relative(relative)
    root = root.resolve()
    if not root.is_dir():
        raise BaselineContractError("root must be an existing directory")
    candidate = root / relative
    current = root
    for part in PurePosixPath(relative).parts[:-1]:
        current = current / part
        metadata = current.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise BaselineContractError(f"unsafe path component: {relative}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(candidate, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise BaselineContractError(f"regular file required: {relative}")
        if before.st_size > max_bytes:
            raise BaselineContractError(f"file size limit exceeded: {relative}")
        hasher = hashlib.sha256()
        observed = 0
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            observed += len(block)
            if observed > max_bytes:
                raise BaselineContractError(f"file size limit exceeded while reading: {relative}")
            hasher.update(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after or observed != before.st_size:
        raise BaselineContractError(f"UNSTABLE_SOURCE_HOLD:{relative}")
    return {"path": relative, "sha256": hasher.hexdigest(), "size_bytes": observed}


def contained_manifest(root: Path, relative_paths: Iterable[str]) -> list[dict[str, Any]]:
    paths = sorted({_safe_relative(item) for item in relative_paths})
    if not paths or len(paths) > MAX_TRACKED_FILES:
        raise BaselineContractError("tracked-file count is invalid")
    return [secure_file_sha256(root, item) for item in paths]


def archive_manifest(archive: Path) -> dict[str, Any]:
    """Return a complete, safety-checked ZIP payload manifest."""
    archive = archive.resolve()
    if not archive.is_file() or archive.is_symlink():
        raise BaselineContractError("archive must be a regular file")
    if archive.stat().st_size > 64 * 1024 * 1024:
        raise BaselineContractError("compressed archive size limit exceeded")
    archive_hasher = hashlib.sha256()
    with archive.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            archive_hasher.update(block)
    archive_sha = archive_hasher.hexdigest()
    members: list[dict[str, Any]] = []
    total = 0
    with zipfile.ZipFile(archive) as handle:
        infos = handle.infolist()
        names = [item.filename for item in infos]
        if len(infos) > MAX_ARCHIVE_MEMBERS:
            raise BaselineContractError("archive member limit exceeded")
        if len(names) != len(set(names)):
            raise BaselineContractError("duplicate archive member rejected")
        for info in infos:
            path = _safe_relative(info.filename.rstrip("/")) if info.filename.rstrip("/") else ""
            mode = (info.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK:
                raise BaselineContractError("archive symbolic link rejected")
            if info.is_dir():
                members.append({"path": path + "/", "kind": "DIRECTORY", "size_bytes": 0})
                continue
            if info.file_size > MAX_FILE_BYTES:
                raise BaselineContractError("archive member size limit exceeded")
            if info.compress_size and info.file_size / info.compress_size > 200:
                raise BaselineContractError("archive compression ratio limit exceeded")
            payload = handle.read(info)
            total += len(payload)
            if total > MAX_ARCHIVE_BYTES:
                raise BaselineContractError("archive total size limit exceeded")
            members.append(
                {
                    "path": path,
                    "kind": "REGULAR",
                    "size_bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
    result = {
        "archive_name": archive.name,
        "archive_sha256": archive_sha,
        "coverage": "COMPLETE",
        "member_count": len(members),
        "regular_member_count": sum(item["kind"] == "REGULAR" for item in members),
        "members": members,
    }
    result["manifest_sha256"] = digest(result)
    return result


def _derive_secret(seed: bytes, index: int, bit: int) -> bytes:
    return hmac.new(seed, f"BCO-LAMPORT:{index}:{bit}".encode("ascii"), hashlib.sha256).digest()


def _message_bits(message_sha256: str) -> list[int]:
    if not isinstance(message_sha256, str) or len(message_sha256) != 64:
        raise BaselineContractError("message SHA-256 is invalid")
    try:
        raw = bytes.fromhex(message_sha256)
    except ValueError as exc:
        raise BaselineContractError("message SHA-256 is invalid") from exc
    return [(byte >> shift) & 1 for byte in raw for shift in range(7, -1, -1)]


def _lamport_sign(message_sha256: str, signing_seed: bytes, key_id: str) -> dict[str, Any]:
    if not isinstance(signing_seed, bytes) or len(signing_seed) != 32:
        raise BaselineContractError("SIGNING_AUTHORITY_UNAVAILABLE:32-byte one-time seed required")
    if not isinstance(key_id, str) or not key_id.strip():
        raise BaselineContractError("signing key_id is required")
    public_key: list[list[str]] = []
    signature: list[str] = []
    for index, selected_bit in enumerate(_message_bits(message_sha256)):
        pair: list[str] = []
        secrets_for_index: list[bytes] = []
        for bit in (0, 1):
            secret = _derive_secret(signing_seed, index, bit)
            secrets_for_index.append(secret)
            pair.append(hashlib.sha256(secret).hexdigest())
        public_key.append(pair)
        signature.append(secrets_for_index[selected_bit].hex())
    public_fingerprint = digest(public_key)
    return {
        "algorithm": SIGNATURE_ALGORITHM,
        "key_id": key_id,
        "one_time": True,
        "public_key": public_key,
        "public_key_fingerprint": public_fingerprint,
        "signature": signature,
    }


def create_signed_baseline(
    *,
    root: Path,
    relative_paths: Sequence[str],
    predecessor_archive: Path,
    policies: Mapping[str, Any],
    capabilities: Sequence[Mapping[str, Any]],
    expected_tests: Mapping[str, Any],
    expected_results: Mapping[str, Any],
    generation: int,
    parent_baseline_sha256: str,
    signing_seed: bytes,
    key_id: str,
) -> dict[str, Any]:
    if type(generation) is not int or generation < 1:
        raise BaselineContractError("generation must be a positive integer")
    if not isinstance(parent_baseline_sha256, str) or not parent_baseline_sha256:
        raise BaselineContractError("parent_baseline_sha256 is required")
    files = contained_manifest(root, relative_paths)
    archive = archive_manifest(predecessor_archive)
    body = {
        "schema": SCHEMA,
        "version": VERSION,
        "generation": generation,
        "parent_baseline_sha256": parent_baseline_sha256,
        "coverage": "COMPLETE",
        "predecessor_archive": archive,
        "tracked_files": files,
        "tracked_roots": sorted({PurePosixPath(item["path"]).parts[0] for item in files}),
        "policies": _strict_normalize(dict(policies), "$.policies"),
        "capabilities": _strict_normalize(list(capabilities), "$.capabilities"),
        "expected_tests": _strict_normalize(dict(expected_tests), "$.expected_tests"),
        "expected_results": _strict_normalize(dict(expected_results), "$.expected_results"),
        "stablePromotionAuthorized": False,
        "providerEffectAuthorized": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    body_sha256 = digest(body)
    signature = _lamport_sign(body_sha256, signing_seed, key_id)
    envelope = {"schema": SCHEMA, "version": VERSION, "body": body, "body_sha256": body_sha256, "signature": signature}
    envelope["envelope_sha256"] = digest(envelope)
    return envelope


def verify_signed_baseline(
    envelope: Mapping[str, Any],
    *,
    expected_public_key_fingerprint: str | None,
    minimum_generation: int = 1,
    expected_parent_baseline_sha256: str | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    try:
        normalized = _strict_normalize(dict(envelope))
    except BaselineContractError as exc:
        normalized = {}
        failures.append(f"INVALID_ENVELOPE:{exc}")
    body = normalized.get("body") if isinstance(normalized.get("body"), Mapping) else {}
    claimed_body_sha = normalized.get("body_sha256")
    observed_body_sha = digest(body)
    if claimed_body_sha != observed_body_sha:
        failures.append("BODY_HASH_MISMATCH")
    claimed_envelope = normalized.get("envelope_sha256")
    without_self = dict(normalized)
    without_self.pop("envelope_sha256", None)
    if claimed_envelope != digest(without_self):
        failures.append("ENVELOPE_HASH_MISMATCH")
    signature = normalized.get("signature") if isinstance(normalized.get("signature"), Mapping) else {}
    if signature.get("algorithm") != SIGNATURE_ALGORITHM:
        failures.append("SIGNATURE_ALGORITHM_REJECTED")
    public_key = signature.get("public_key")
    revealed = signature.get("signature")
    public_fingerprint = signature.get("public_key_fingerprint")
    if not expected_public_key_fingerprint:
        failures.append("SIGNING_TRUST_ROOT_REQUIRED")
    elif public_fingerprint != expected_public_key_fingerprint:
        failures.append("PUBLIC_KEY_FINGERPRINT_MISMATCH")
    if not isinstance(public_key, list) or len(public_key) != 256:
        failures.append("PUBLIC_KEY_INVALID")
    if not isinstance(revealed, list) or len(revealed) != 256:
        failures.append("SIGNATURE_INVALID")
    if isinstance(public_key, list) and len(public_key) == 256 and isinstance(revealed, list) and len(revealed) == 256:
        for index, selected_bit in enumerate(_message_bits(observed_body_sha)):
            pair = public_key[index]
            try:
                secret = bytes.fromhex(str(revealed[index]))
                expected = pair[selected_bit]
            except (ValueError, IndexError, TypeError):
                failures.append(f"SIGNATURE_ELEMENT_INVALID:{index}")
                break
            if len(secret) != 32 or hashlib.sha256(secret).hexdigest() != expected:
                failures.append(f"SIGNATURE_MISMATCH:{index}")
                break
    generation = body.get("generation")
    if type(generation) is not int or generation < minimum_generation:
        failures.append("BASELINE_REPLAY_OR_GENERATION_INVALID")
    if expected_parent_baseline_sha256 is not None and body.get("parent_baseline_sha256") != expected_parent_baseline_sha256:
        failures.append("PARENT_BASELINE_MISMATCH")
    if body.get("coverage") != "COMPLETE":
        failures.append("BASELINE_COVERAGE_INCOMPLETE")
    valid = not failures
    result = {
        "schema": "BCO_PRIME_BASELINE_VERIFICATION_V3_1",
        "state": "VERIFIED" if valid else "SIGNATURE_OR_BASELINE_HOLD",
        "valid": valid,
        "failures": failures,
        "body_sha256": observed_body_sha,
        "public_key_fingerprint": public_fingerprint,
        "generation": generation,
        "stablePromotionAuthorized": False,
        "providerEffectAuthorized": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["receipt_sha256"] = digest(result)
    return result


def write_baseline_atomic(path: Path, envelope: Mapping[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(canonical_json(_strict_normalize(dict(envelope))) + "\n", encoding="utf-8")
    os.replace(temporary, path)


__all__ = [
    "BaselineContractError",
    "SIGNATURE_ALGORITHM",
    "archive_manifest",
    "canonical_json",
    "contained_manifest",
    "create_signed_baseline",
    "digest",
    "secure_file_sha256",
    "verify_signed_baseline",
    "write_baseline_atomic",
]
