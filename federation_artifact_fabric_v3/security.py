"""Fail-closed artifact inspection for Federation Artifact Fabric v3."""

from __future__ import annotations

from dataclasses import asdict
import io
import math
import os
from pathlib import PurePosixPath
import re
from typing import Any, Mapping
import zipfile

from .canonical import sha256_bytes
from .model import ArtifactRequest, ScanReport, ScanViolation, SensitivityClass


SCANNER_VERSION = "FAF3-SCANNER-1.0.0"
MAX_ARTIFACT_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 1_000
MAX_ARCHIVE_ENTRY_BYTES = 50 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 200 * 1024 * 1024
MAX_COMPRESSION_RATIO = 150.0
MAX_ARCHIVE_DEPTH = 2

_SAFE_NAME = re.compile(r"^[^\\/\x00-\x1f]{1,240}$")
_SAFE_ALIAS = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")

_SECRET_FIELD = re.compile(
    r"(?:^|_)(?:access_?token|refresh_?token|id_?token|api_?key|password|passwd|"
    r"client_?secret|private_?key|credential|authorization|cookie|secret|session)(?:$|_)",
    re.IGNORECASE,
)
_SAFE_SECRET_SUFFIXES = (
    "_ref",
    "_reference",
    "_alias",
    "_handle",
    "_fingerprint",
    "_sha256",
    "_id",
)

_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("BEARER_TOKEN", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{16,}=*", re.IGNORECASE)),
    ("GITHUB_TOKEN", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("GITHUB_PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("OPENAI_KEY", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("GOOGLE_API_KEY", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("GOOGLE_OAUTH_TOKEN", re.compile(r"\bya29\.[0-9A-Za-z_-]{20,}\b")),
    ("AWS_ACCESS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "ASSIGNED_SECRET",
        re.compile(
            r"(?i)\b(?:api[_ -]?key|access[_ -]?token|client[_ -]?secret|password|passwd)"
            r"\s*[:=]\s*['\"]?[A-Za-z0-9_./+~=-]{16,}"
        ),
    ),
)

_HIDDEN_REASONING_PATTERNS = (
    re.compile(r"(?i)\bhidden[_ -]?reasoning\b"),
    re.compile(r"(?i)\bprivate[_ -]?chain[_ -]?of[_ -]?thought\b"),
    re.compile(r"(?i)\bchain[_ -]?of[_ -]?thought\s*[:=]"),
    re.compile(r"(?i)<(?:analysis|scratchpad|hidden_reasoning)>")
)

_TEXT_MEDIA_TYPES = {
    "application/json",
    "application/javascript",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
    "application/sql",
}

_EXTENSION_MEDIA = {
    ".json": "application/json",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".pdf": "application/pdf",
    ".zip": "application/zip",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

_MACRO_EXTENSIONS = {".docm", ".xlsm", ".pptm", ".xlam", ".dotm"}
_EXECUTABLE_EXTENSIONS = {
    ".exe", ".dll", ".com", ".scr", ".msi", ".bat", ".cmd", ".ps1", ".jar", ".apk"
}


def _entropy(value: str) -> float:
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for character in value:
        counts[character] = counts.get(character, 0) + 1
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def _reject_secret_metadata(value: Any, path: str = "metadata") -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key)
            lowered = key.lower()
            if _SECRET_FIELD.search(lowered) and not lowered.endswith(_SAFE_SECRET_SUFFIXES):
                raise ScanViolation(f"secret-bearing metadata field rejected: {path}.{key}")
            _reject_secret_metadata(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for index, item in enumerate(value):
            _reject_secret_metadata(item, f"{path}[{index}]")
        return
    if isinstance(value, str):
        _scan_text(value, path)


def _scan_text(text: str, path: str) -> None:
    for label, pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            raise ScanViolation(f"{label} pattern detected in {path}")
    for pattern in _HIDDEN_REASONING_PATTERNS:
        if pattern.search(text):
            raise ScanViolation(f"hidden reasoning marker detected in {path}")
    for match in re.finditer(
        r"(?i)\b(?:token|secret|password|credential)\w*\s*[:=]\s*['\"]?([A-Za-z0-9+/=_-]{32,})",
        text,
    ):
        candidate = match.group(1)
        if _entropy(candidate) >= 4.2:
            raise ScanViolation(f"high-entropy secret assignment detected in {path}")


def _detected_media_type(content: bytes) -> str:
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"PK\x03\x04"):
        return "application/zip"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith((b"{", b"[")):
        return "application/json-or-text"
    return "application/octet-stream"


def _safe_archive_path(name: str) -> PurePosixPath:
    normalised = name.replace("\\", "/")
    path = PurePosixPath(normalised)
    if path.is_absolute() or ".." in path.parts or not normalised or "\x00" in normalised:
        raise ScanViolation(f"unsafe archive path: {name!r}")
    return path


def _scan_zip(content: bytes, *, depth: int) -> tuple[int, int]:
    if depth > MAX_ARCHIVE_DEPTH:
        raise ScanViolation("nested archive depth exceeds limit")
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ScanViolation("declared ZIP/OOXML content is malformed") from exc
    entries = archive.infolist()
    if len(entries) > MAX_ARCHIVE_ENTRIES:
        raise ScanViolation("archive entry count exceeds limit")
    total = 0
    seen: set[str] = set()
    for info in entries:
        path = _safe_archive_path(info.filename)
        key = str(path).casefold()
        if key in seen:
            raise ScanViolation(f"duplicate archive entry: {info.filename}")
        seen.add(key)
        if info.flag_bits & 0x1:
            raise ScanViolation(f"encrypted archive entry rejected: {info.filename}")
        if info.file_size > MAX_ARCHIVE_ENTRY_BYTES:
            raise ScanViolation(f"archive entry exceeds size limit: {info.filename}")
        total += info.file_size
        if total > MAX_ARCHIVE_TOTAL_BYTES:
            raise ScanViolation("archive total uncompressed bytes exceed limit")
        if info.file_size and info.compress_size == 0:
            raise ScanViolation(f"invalid compression metadata: {info.filename}")
        if info.compress_size:
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > MAX_COMPRESSION_RATIO:
                raise ScanViolation(f"suspicious compression ratio: {info.filename}")
        unix_mode = (info.external_attr >> 16) & 0o170000
        if unix_mode == 0o120000:
            raise ScanViolation(f"symbolic link in archive rejected: {info.filename}")
        suffix = path.suffix.lower()
        if suffix in _MACRO_EXTENSIONS or suffix in _EXECUTABLE_EXTENSIONS:
            raise ScanViolation(f"active or executable archive member rejected: {info.filename}")
        if info.is_dir():
            continue
        data = archive.read(info)
        if suffix in {".zip", ".docx", ".xlsx", ".pptx"} and data.startswith(b"PK\x03\x04"):
            _scan_zip(data, depth=depth + 1)
        elif suffix in {".txt", ".md", ".json", ".csv", ".xml", ".yaml", ".yml", ".js", ".py"}:
            _scan_text(data.decode("utf-8", errors="replace"), f"archive:{info.filename}")
    return len(entries), total


def scan_artifact(request: ArtifactRequest) -> ScanReport:
    name = str(request.artifact_name).strip()
    if not _SAFE_NAME.fullmatch(name) or name in {".", ".."}:
        raise ScanViolation("unsafe or empty artifact name")
    if not _SAFE_ALIAS.fullmatch(str(request.destination_alias).strip()):
        raise ScanViolation("destination must be a symbolic private alias, not a provider ID")
    if not request.workstream.strip() or not request.version.strip():
        raise ScanViolation("workstream and version are required")
    if not isinstance(request.content, bytes):
        raise ScanViolation("artifact content must be exact bytes")
    if len(request.content) > MAX_ARTIFACT_BYTES:
        raise ScanViolation("artifact exceeds maximum admitted size")
    if len(request.content) == 0:
        raise ScanViolation("zero-byte artifact rejected")
    _reject_secret_metadata(request.metadata)
    _scan_text(request.source_ref, "source_ref")
    suffix = os.path.splitext(name)[1].lower()
    if suffix in _MACRO_EXTENSIONS:
        raise ScanViolation(f"macro-enabled format requires a separate controlled lane: {suffix}")
    if suffix in _EXECUTABLE_EXTENSIONS:
        raise ScanViolation(f"executable format rejected: {suffix}")
    declared = request.media_type.strip().lower()
    expected = _EXTENSION_MEDIA.get(suffix)
    if expected and declared != expected:
        raise ScanViolation(f"extension/MIME mismatch: {suffix} requires {expected}")
    detected = _detected_media_type(request.content)
    if declared == "application/pdf" and detected != "application/pdf":
        raise ScanViolation("PDF MIME declared but PDF signature absent")
    if declared == "image/png" and detected != "image/png":
        raise ScanViolation("PNG MIME declared but PNG signature absent")
    if declared == "image/jpeg" and detected != "image/jpeg":
        raise ScanViolation("JPEG MIME declared but JPEG signature absent")
    if declared == "application/zip" and detected != "application/zip":
        raise ScanViolation("ZIP MIME declared but ZIP signature absent")
    if suffix in {".docx", ".xlsx", ".pptx"} and detected != "application/zip":
        raise ScanViolation("OOXML extension declared but ZIP container signature absent")
    archive_entries = 0
    archive_total = 0
    if detected == "application/zip":
        archive_entries, archive_total = _scan_zip(request.content, depth=0)
    elif declared.startswith("text/") or declared in _TEXT_MEDIA_TYPES:
        _scan_text(request.content.decode("utf-8", errors="replace"), "artifact")
    elif request.sensitivity == SensitivityClass.PUBLIC_SAFE:
        _scan_text(request.content.decode("utf-8", errors="ignore"), "public-safe-binary")
    return ScanReport(
        passed=True,
        sha256=sha256_bytes(request.content),
        size_bytes=len(request.content),
        detected_media_type=detected,
        findings=(),
        archive_entries=archive_entries,
        archive_uncompressed_bytes=archive_total,
        scanner_version=SCANNER_VERSION,
    )


def scan_report_dict(report: ScanReport) -> dict[str, Any]:
    return asdict(report)
