"""Deterministic drift, privacy-first incremental harvest and shadow repair."""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
import math
import os
import re
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

try:
    from . import bco_prime_baseline_registry_v3_1 as baseline
except ImportError:  # pragma: no cover
    import bco_prime_baseline_registry_v3_1 as baseline


SCHEMA = "BCO_PRIME_DRIFT_HARVEST_V3_1"
VERSION = "3.1.0"
ALLOWED_SUFFIXES = frozenset({".py", ".json", ".jsonl", ".md", ".txt", ".csv"})
COMPATIBLE_LICENSES = frozenset({"MIT", "Apache-2.0", "BSD-3-Clause", "Proprietary-Authorized"})
_SPDX = re.compile(r"SPDX-License-Identifier:\s*([^\r\n*]+)", re.IGNORECASE)
_SECRET_PATTERNS = (
    ("PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE)),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("AWS_KEY", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("GITHUB_TOKEN", re.compile(r"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("URI_CREDENTIAL", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@", re.IGNORECASE)),
    (
        "SECRET_ASSIGNMENT",
        re.compile(
            r"(?i)[\"']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|secret|client[_-]?secret|authorization)[\"']?\s*[:=]\s*[\"']?[^\s,;\"']{6,}"
        ),
    ),
)
_FORBIDDEN_EFFECT_KEYS = {
    "externaleffect",
    "providereffect",
    "providereffectauthorized",
    "authorityexpansion",
    "network",
    "deploy",
    "registerlive",
    "stablepromotionauthorized",
    "exec",
    "eval",
    "subprocess",
    "applypatch",
}


class DriftHarvestError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def reject_effect_escape(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _normalize_key(key) in _FORBIDDEN_EFFECT_KEYS and item not in (None, False, 0, "", [], {}):
                raise DriftHarvestError(f"external or executable effect rejected at {path}.{key}")
            reject_effect_escape(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            reject_effect_escape(item, f"{path}[{index}]")


def _safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise DriftHarvestError("path must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise DriftHarvestError("path traversal rejected")
    return path.as_posix()


def _entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = {char: text.count(char) for char in set(text)}
    length = len(text)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def secret_hold(text: str) -> tuple[bool, tuple[str, ...]]:
    reasons = [name for name, pattern in _SECRET_PATTERNS if pattern.search(text)]
    for token in re.findall(r"[A-Za-z0-9+/=_-]{32,}", text):
        if len(set(token)) >= 12 and _entropy(token) >= 4.2:
            reasons.append("HIGH_ENTROPY_TOKEN")
            break
    return bool(reasons), tuple(sorted(set(reasons)))


def license_state(text: str, dependencies: Sequence[str], dependency_licenses: Mapping[str, str]) -> dict[str, Any]:
    matches = [item.strip() for item in _SPDX.findall(text[:32768])]
    unique = sorted(set(matches))
    reasons: list[str] = []
    identifier = unique[0] if len(unique) == 1 else "UNKNOWN"
    if len(unique) > 1:
        reasons.append("CONFLICTING_SPDX_IDENTIFIERS")
    if identifier != "UNKNOWN" and re.search(r"\s(?:OR|AND|WITH)\s|[()]", identifier, re.IGNORECASE):
        reasons.append("COMPOUND_SPDX_REQUIRES_REVIEW")
    if identifier not in COMPATIBLE_LICENSES:
        reasons.append("UNKNOWN_OR_INCOMPATIBLE_LICENSE")
    missing_dependencies = sorted(
        dependency
        for dependency in dependencies
        if dependency.split(".")[0] not in sys.stdlib_module_names
        and dependency_licenses.get(dependency) not in COMPATIBLE_LICENSES
    )
    if missing_dependencies:
        reasons.append("TRANSITIVE_LICENSE_UNVERIFIED")
    return {
        "identifier": identifier,
        "state": "COMPATIBLE" if not reasons else "LICENSE_HOLD",
        "compatible": not reasons,
        "reasons": reasons,
        "unverified_dependency_ids": [hashlib.sha256(item.encode()).hexdigest() for item in missing_dependencies],
    }


def _secure_read(root: Path, relative: str, max_bytes: int) -> bytes:
    relative = _safe_relative(relative)
    root = root.resolve()
    candidate = root / relative
    current = root
    for part in PurePosixPath(relative).parts[:-1]:
        current = current / part
        data = current.lstat()
        if stat.S_ISLNK(data.st_mode) or not stat.S_ISDIR(data.st_mode):
            raise DriftHarvestError("unsafe path component")
    descriptor = os.open(candidate, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
            raise DriftHarvestError("regular bounded file required")
        chunks: list[bytes] = []
        size = 0
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            size += len(block)
            if size > max_bytes:
                raise DriftHarvestError("file size limit exceeded while reading")
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise DriftHarvestError("UNSTABLE_SOURCE_HOLD")
    return b"".join(chunks)


def _python_dna(text: str, source_scope: str, path_token: str, content_id: str) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise DriftHarvestError("MALFORMED_PYTHON") from exc
    dependencies: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            dependencies.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            dependencies.add(node.module)
    records: list[dict[str, Any]] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or node.name.startswith("_"):
            continue
        kind = "CLASS" if isinstance(node, ast.ClassDef) else "FUNCTION"
        if isinstance(node, ast.ClassDef):
            signature_basis = {"bases": [ast.dump(item, include_attributes=False) for item in node.bases]}
        else:
            signature_basis = {
                "args": [arg.arg for arg in node.args.args],
                "kwonly": [arg.arg for arg in node.args.kwonlyargs],
                "returns": ast.dump(node.returns, include_attributes=False) if node.returns else None,
            }
        signature_sha = digest(signature_basis)
        symbol_id = hashlib.sha256(node.name.encode("utf-8")).hexdigest()
        semantic_id = digest({"content_id": content_id, "kind": kind, "symbol_id": symbol_id, "signature_sha256": signature_sha})
        occurrence_id = digest({"scope": source_scope, "path_token": path_token, "symbol_id": symbol_id})
        records.append(
            {
                "dna_id": semantic_id,
                "occurrence_id": occurrence_id,
                "content_id": content_id,
                "path_token": path_token,
                "symbol_id": symbol_id,
                "kind": kind,
                "signature_sha256": signature_sha,
                "dependency_ids": sorted(hashlib.sha256(item.encode()).hexdigest() for item in dependencies),
                "quarantine_state": "SHADOW_ONLY",
            }
        )
    if not records:
        records.append(
            {
                "dna_id": digest({"content_id": content_id, "kind": "MODULE"}),
                "occurrence_id": digest({"scope": source_scope, "path_token": path_token, "kind": "MODULE"}),
                "content_id": content_id,
                "path_token": path_token,
                "symbol_id": hashlib.sha256(b"MODULE").hexdigest(),
                "kind": "MODULE",
                "signature_sha256": digest({"kind": "MODULE"}),
                "dependency_ids": sorted(hashlib.sha256(item.encode()).hexdigest() for item in dependencies),
                "quarantine_state": "SHADOW_ONLY",
            }
        )
    return records, tuple(sorted(dependencies))


def _generic_dna(suffix: str, text: str, source_scope: str, path_token: str, content_id: str) -> list[dict[str, Any]]:
    if suffix == ".json":
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            raise DriftHarvestError("MALFORMED_JSON") from exc
    if suffix == ".jsonl":
        for line in text.splitlines():
            if line.strip():
                try:
                    json.loads(line)
                except json.JSONDecodeError as exc:
                    raise DriftHarvestError("MALFORMED_JSONL") from exc
    kind = "STRUCTURED_ARTIFACT" if suffix in {".json", ".jsonl"} else "DOCUMENT_ARTIFACT"
    return [
        {
            "dna_id": digest({"content_id": content_id, "kind": kind}),
            "occurrence_id": digest({"scope": source_scope, "path_token": path_token, "kind": kind}),
            "content_id": content_id,
            "path_token": path_token,
            "symbol_id": hashlib.sha256(kind.encode()).hexdigest(),
            "kind": kind,
            "signature_sha256": digest({"kind": kind}),
            "dependency_ids": [],
            "quarantine_state": "SHADOW_ONLY",
        }
    ]


def _cursor_payload(cursor: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(cursor)
    result.pop("hmac_sha256", None)
    return result


def sign_cursor(cursor: Mapping[str, Any], cursor_key: bytes) -> dict[str, Any]:
    if not isinstance(cursor_key, bytes) or len(cursor_key) < 32:
        raise DriftHarvestError("SIGNING_AUTHORITY_UNAVAILABLE:cursor key required")
    result = dict(cursor)
    result["hmac_sha256"] = hmac.new(cursor_key, canonical_json(_cursor_payload(result)).encode(), hashlib.sha256).hexdigest()
    return result


def verify_cursor(cursor: Mapping[str, Any], cursor_key: bytes, *, baseline_sha256: str, scope_sha256: str) -> int:
    if not isinstance(cursor_key, bytes) or len(cursor_key) < 32:
        raise DriftHarvestError("SIGNING_AUTHORITY_UNAVAILABLE:cursor key required")
    claimed = str(cursor.get("hmac_sha256") or "")
    observed = hmac.new(cursor_key, canonical_json(_cursor_payload(cursor)).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(claimed, observed):
        raise DriftHarvestError("CURSOR_SIGNATURE_INVALID")
    if cursor.get("baseline_sha256") != baseline_sha256 or cursor.get("scope_sha256") != scope_sha256:
        raise DriftHarvestError("CURSOR_SCOPE_OR_BASELINE_MISMATCH")
    index = cursor.get("next_index")
    if type(index) is not int or index < 0:
        raise DriftHarvestError("CURSOR_INDEX_INVALID")
    return index


class IncrementalCapabilityScanner:
    """Bounded scanner that increments extraction, never integrity coverage."""

    def __init__(
        self,
        root: Path,
        *,
        source_id: str,
        tenant_id: str,
        matter_id: str,
        baseline_sha256: str,
        max_files: int = 1000,
        max_file_bytes: int = 1024 * 1024,
        max_total_bytes: int = 32 * 1024 * 1024,
        max_depth: int = 16,
        dependency_licenses: Mapping[str, str] | None = None,
    ) -> None:
        self.root = root.resolve()
        if not self.root.is_dir():
            raise DriftHarvestError("scan root must exist")
        if any(type(item) is not int or item < 1 for item in (max_files, max_file_bytes, max_total_bytes, max_depth)):
            raise DriftHarvestError("scan limits must be positive integers")
        self.source_id = str(source_id)
        self.tenant_id = str(tenant_id)
        self.matter_id = str(matter_id)
        if not all((self.source_id, self.tenant_id, self.matter_id, baseline_sha256)):
            raise DriftHarvestError("source, tenant, matter and baseline bindings are required")
        self.baseline_sha256 = baseline_sha256
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes
        self.max_total_bytes = max_total_bytes
        self.max_depth = max_depth
        self.dependency_licenses = dict(dependency_licenses or {})

    def scan(
        self,
        *,
        cursor: Mapping[str, Any] | None = None,
        cursor_key: bytes | None = None,
        cancelled: bool = False,
    ) -> dict[str, Any]:
        if type(cancelled) is not bool:
            raise DriftHarvestError("cancelled must be a Boolean")
        if cancelled:
            return self._cancelled()
        root_before = self.root.stat()
        candidates: list[str] = []
        for path in self.root.rglob("*"):
            relative = path.relative_to(self.root).as_posix()
            if len(PurePosixPath(relative).parts) > self.max_depth:
                continue
            if path.is_symlink():
                candidates.append(relative)
            elif path.is_file() and path.suffix.lower() in ALLOWED_SUFFIXES:
                candidates.append(relative)
        candidates.sort()
        scope_sha = digest({"source_id": self.source_id, "tenant_id": self.tenant_id, "matter_id": self.matter_id, "root_name_hash": hashlib.sha256(self.root.name.encode()).hexdigest()})
        start = 0
        if cursor is not None:
            start = verify_cursor(cursor, cursor_key or b"", baseline_sha256=self.baseline_sha256, scope_sha256=scope_sha)
        records: list[dict[str, Any]] = []
        rejects: list[dict[str, Any]] = []
        bytes_read = 0
        index = start
        while index < len(candidates) and index - start < self.max_files:
            if cancelled:
                return self._cancelled()
            relative = candidates[index]
            path_token = hashlib.sha256(relative.encode("utf-8")).hexdigest()
            try:
                raw = _secure_read(self.root, relative, self.max_file_bytes)
                if bytes_read + len(raw) > self.max_total_bytes:
                    break
                bytes_read += len(raw)
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise DriftHarvestError("NON_UTF8_HOLD") from exc
                held, secret_reasons = secret_hold(text)
                if held:
                    rejects.append({"path_token": path_token, "state": "SECRET_HOLD", "reason_codes": list(secret_reasons)})
                    index += 1
                    continue
                suffix = PurePosixPath(relative).suffix.lower()
                content_id = hashlib.sha256(raw).hexdigest()
                if suffix == ".py":
                    current, dependencies = _python_dna(text, scope_sha, path_token, content_id)
                else:
                    current = _generic_dna(suffix, text, scope_sha, path_token, content_id)
                    dependencies = ()
                licence = license_state(text, dependencies, self.dependency_licenses)
                if not licence["compatible"]:
                    rejects.append({"path_token": path_token, "state": "LICENSE_HOLD", "reason_codes": licence["reasons"]})
                else:
                    for item in current:
                        item["license"] = licence
                        records.append(item)
            except (OSError, DriftHarvestError) as exc:
                rejects.append({"path_token": path_token, "state": "SOURCE_HOLD", "reason_codes": [str(exc)]})
            index += 1
        complete = index >= len(candidates)
        next_cursor = None
        state = "COMPLETE" if complete else "PARTIAL"
        if not complete:
            if cursor_key is None:
                state = "BLOCKED_WITH_ROUTE"
                rejects.append({"path_token": None, "state": "CURSOR_HOLD", "reason_codes": ["SIGNING_AUTHORITY_UNAVAILABLE"]})
            else:
                next_cursor = sign_cursor(
                    {
                        "schema": "BCO_PRIME_HARVEST_CURSOR_V3_1",
                        "baseline_sha256": self.baseline_sha256,
                        "scope_sha256": scope_sha,
                        "next_index": index,
                    },
                    cursor_key,
                )
        root_after = self.root.stat()
        if (root_before.st_dev, root_before.st_ino) != (root_after.st_dev, root_after.st_ino):
            raise DriftHarvestError("ROOT_SWAP_DETECTED")
        result = {
            "schema": "BCO_PRIME_INCREMENTAL_SCAN_V3_1",
            "state": state,
            "coverage_complete": complete,
            "deletions_authoritative": complete and start == 0,
            "baseline_sha256": self.baseline_sha256,
            "scope_sha256": scope_sha,
            "candidate_count": len(candidates),
            "scanned_count": index - start,
            "bytes_read": bytes_read,
            "records": sorted(records, key=lambda item: (item["dna_id"], item["occurrence_id"])),
            "rejects": rejects,
            "next_cursor": next_cursor,
            "raw_content_emitted": False,
            "stablePromotionAuthorized": False,
            "providerEffectAuthorized": False,
            "manualUserTasks": [],
            "ownerActionRequired": False,
        }
        result["receipt_sha256"] = digest(result)
        return result

    @staticmethod
    def _cancelled() -> dict[str, Any]:
        result = {
            "schema": "BCO_PRIME_INCREMENTAL_SCAN_V3_1",
            "state": "CANCELLED",
            "coverage_complete": False,
            "deletions_authoritative": False,
            "records": [],
            "rejects": [],
            "next_cursor": None,
            "raw_content_emitted": False,
            "stablePromotionAuthorized": False,
            "providerEffectAuthorized": False,
            "manualUserTasks": [],
            "ownerActionRequired": False,
        }
        result["receipt_sha256"] = digest(result)
        return result


def diff_capability_scans(previous: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    if current.get("coverage_complete") is not True:
        state = "PARTIAL"
    else:
        state = "COMPLETE"
    old_records = {(item.get("dna_id"), item.get("occurrence_id")): item for item in previous.get("records", [])}
    new_records = {(item.get("dna_id"), item.get("occurrence_id")): item for item in current.get("records", [])}
    old_dna = {str(item.get("dna_id")) for item in previous.get("records", [])}
    new_dna = {str(item.get("dna_id")) for item in current.get("records", [])}
    old_occurrences = {str(item.get("occurrence_id")): item for item in previous.get("records", [])}
    new_occurrences = {str(item.get("occurrence_id")): item for item in current.get("records", [])}
    moved: list[dict[str, str]] = []
    old_by_dna = {str(item.get("dna_id")): str(item.get("occurrence_id")) for item in previous.get("records", [])}
    new_by_dna = {str(item.get("dna_id")): str(item.get("occurrence_id")) for item in current.get("records", [])}
    for dna_id in sorted(old_dna & new_dna):
        if old_by_dna.get(dna_id) != new_by_dna.get(dna_id):
            moved.append({"dna_id": dna_id, "from_occurrence_id": old_by_dna[dna_id], "to_occurrence_id": new_by_dna[dna_id]})
    removed = sorted(old_dna - new_dna) if current.get("deletions_authoritative") is True else []
    result = {
        "schema": "BCO_PRIME_CAPABILITY_DNA_DIFF_V3_1",
        "state": state,
        "added_dna_ids": sorted(new_dna - old_dna),
        "removed_dna_ids": removed,
        "moved_occurrences": moved,
        "added_occurrence_ids": sorted(set(new_occurrences) - set(old_occurrences)),
        "removed_occurrence_ids": sorted(set(old_occurrences) - set(new_occurrences)) if current.get("deletions_authoritative") is True else [],
        "unchanged_pairs": len(set(old_records) & set(new_records)),
        "deletions_authoritative": current.get("deletions_authoritative") is True,
        "holds": list(current.get("rejects", [])),
        "stablePromotionAuthorized": False,
        "providerEffectAuthorized": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["receipt_sha256"] = digest(result)
    return result


def detect_drift(
    baseline_envelope: Mapping[str, Any],
    *,
    root: Path,
    expected_public_key_fingerprint: str | None,
    minimum_generation: int,
    policies: Mapping[str, Any],
    capabilities: Sequence[Mapping[str, Any]],
    test_results: Mapping[str, Any],
    result_assertions: Mapping[str, Any],
    coverage_complete: bool,
) -> dict[str, Any]:
    if type(coverage_complete) is not bool:
        raise DriftHarvestError("coverage_complete must be a Boolean")
    verification = baseline.verify_signed_baseline(
        baseline_envelope,
        expected_public_key_fingerprint=expected_public_key_fingerprint,
        minimum_generation=minimum_generation,
    )
    body = baseline_envelope.get("body", {})
    events: list[dict[str, Any]] = []
    if not verification["valid"]:
        events.append({"class": "BASELINE_INTEGRITY", "severity": "HARD", "evidence": verification["receipt_sha256"]})
    tracked = {item["path"]: item for item in body.get("tracked_files", []) if isinstance(item, Mapping) and item.get("path")}
    current: dict[str, dict[str, Any]] = {}
    for path in sorted(tracked):
        try:
            current[path] = baseline.secure_file_sha256(root, path)
        except (OSError, baseline.BaselineContractError):
            events.append({"class": "SOURCE_DELETE", "severity": "HARD", "path_token": hashlib.sha256(path.encode()).hexdigest()})
    for path, expected in tracked.items():
        observed = current.get(path)
        if observed and observed["sha256"] != expected.get("sha256"):
            events.append({"class": "SOURCE_MODIFY", "severity": "HARD", "path_token": hashlib.sha256(path.encode()).hexdigest(), "expected_sha256": expected.get("sha256"), "observed_sha256": observed["sha256"]})
    if digest(policies) != digest(body.get("policies", {})):
        events.append({"class": "POLICY_DRIFT", "severity": "HARD", "expected_sha256": digest(body.get("policies", {})), "observed_sha256": digest(policies)})
    if digest(list(capabilities)) != digest(body.get("capabilities", [])):
        events.append({"class": "CAPABILITY_DNA_CHANGE", "severity": "HARD", "expected_sha256": digest(body.get("capabilities", [])), "observed_sha256": digest(list(capabilities))})
    expected_tests = body.get("expected_tests", {})
    if digest(test_results) != digest(expected_tests):
        events.append({"class": "TEST_REGRESSION", "severity": "HARD", "expected_sha256": digest(expected_tests), "observed_sha256": digest(test_results)})
    expected_results = body.get("expected_results", {})
    if digest(result_assertions) != digest(expected_results):
        events.append({"class": "RESULT_DRIFT", "severity": "HARD", "expected_sha256": digest(expected_results), "observed_sha256": digest(result_assertions)})
    if not coverage_complete:
        events.append({"class": "PARTIAL_OR_UNKNOWN", "severity": "HARD", "evidence": "coverage-incomplete"})
    state = "NO_DRIFT" if not events and coverage_complete and verification["valid"] else "DRIFT_DETECTED"
    result = {
        "schema": "BCO_PRIME_DRIFT_REPORT_V3_1",
        "state": state,
        "coverage_complete": coverage_complete,
        "baseline_verification": verification,
        "events": sorted(events, key=lambda item: (item["class"], item.get("path_token", ""))),
        "hard_veto": any(item["severity"] == "HARD" for item in events),
        "stablePromotionAuthorized": False,
        "providerEffectAuthorized": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["receipt_sha256"] = digest(result)
    return result


def regression_scoreboard(drift_report: Mapping[str, Any], *, previous_state: str | None = None) -> dict[str, Any]:
    events = list(drift_report.get("events", []))
    hard = [item for item in events if item.get("severity") == "HARD"]
    score = max(0, 100 - 20 * len(hard) - 5 * (len(events) - len(hard)))
    if previous_state == "QUARANTINED":
        state = "QUARANTINED"
        reasons = ["QUARANTINE_STICKY"]
    elif hard:
        state = "QUARANTINED"
        reasons = sorted({str(item.get("class")) for item in hard})
    elif events:
        state = "HOLD"
        reasons = sorted({str(item.get("class")) for item in events})
    else:
        state = "PASS"
        reasons = []
    result = {
        "schema": "BCO_PRIME_REGRESSION_SCOREBOARD_V3_1",
        "state": state,
        "score": score,
        "hard_veto_count": len(hard),
        "reasons": reasons,
        "baselineAdvanceAuthorized": False,
        "quarantineAutoClearAuthorized": False,
        "stablePromotionAuthorized": False,
        "providerEffectAuthorized": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["receipt_sha256"] = digest(result)
    return result


def shadow_repair_plan(drift_report: Mapping[str, Any], baseline_sha256: str) -> dict[str, Any]:
    reject_effect_escape(drift_report)
    candidates: list[dict[str, Any]] = []
    for index, event in enumerate(drift_report.get("events", []), 1):
        action = {
            "SOURCE_DELETE": "PROPOSE_RESTORE_FROM_SEALED_BASELINE",
            "SOURCE_MODIFY": "PROPOSE_RESTORE_FROM_SEALED_BASELINE",
            "POLICY_DRIFT": "PROPOSE_POLICY_RECONCILIATION",
            "CAPABILITY_DNA_CHANGE": "PROPOSE_CAPABILITY_REQUALIFICATION",
            "TEST_REGRESSION": "PROPOSE_ROUTE_QUARANTINE_AND_RETEST",
            "RESULT_DRIFT": "PROPOSE_RESULT_CONTRACT_REVIEW",
            "PARTIAL_OR_UNKNOWN": "PROPOSE_COMPLETE_COVERAGE",
            "BASELINE_INTEGRITY": "PROPOSE_TRUSTED_BASELINE_RESTORE",
        }.get(str(event.get("class")), "PROPOSE_BOUNDED_REVIEW")
        candidate = {
            "candidate_id": f"repair-{index:03d}-{digest(event)[:16]}",
            "action": action,
            "drift_event_sha256": digest(event),
            "base_sha256": baseline_sha256,
            "path_token": event.get("path_token"),
            "format": "DECLARATIVE_JSON",
            "executable": False,
            "effect_class": "LOCAL_SHADOW",
            "rollback_plan": "retain current source and select last verified signed baseline",
            "independent_tests_required": True,
        }
        reject_effect_escape(candidate)
        candidates.append(candidate)
    result = {
        "schema": "BCO_PRIME_SHADOW_REPAIR_PLAN_V3_1",
        "state": "SHADOW_CANDIDATES" if candidates else "NO_REPAIR_REQUIRED",
        "base_sha256": baseline_sha256,
        "candidates": candidates,
        "sourceMutationAuthorized": False,
        "stablePromotionAuthorized": False,
        "providerEffectAuthorized": False,
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["receipt_sha256"] = digest(result)
    return result


__all__ = [
    "DriftHarvestError",
    "IncrementalCapabilityScanner",
    "detect_drift",
    "diff_capability_scans",
    "digest",
    "regression_scoreboard",
    "reject_effect_escape",
    "secret_hold",
    "shadow_repair_plan",
    "sign_cursor",
    "verify_cursor",
]
