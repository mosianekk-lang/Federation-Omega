"""Select explicit source or portable-archive test scope without missing-file skips."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any

SOURCE_COURT = "tests/test_phoenix_core_workflow_source_contracts.py"
WORKFLOW_PATHS = [
    ".github/workflows/fuse-localllm-desktop-windows-build-v1.yml",
    ".github/workflows/sovara-ai-studio-semantic-canary.yml",
]
PROFILE = {
    "schema": "PHOENIX_PORTABLE_CORE_TEST_PROFILE_V1",
    "source_workflow_court": SOURCE_COURT,
    "workflow_paths": WORKFLOW_PATHS,
    "source_admission_required": True,
}
PORTABLE_LOADERS = [
    "tests/phoenix_core_test_profile.py",
    "tests/test_fuse_localllm_desktop_source_v1.py",
    "tests/test_fuse_localllm_gemini_provider_v1.py",
    "tests/test_sovara_google_interactions_v2_canary.py",
]


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise AssertionError("PHOENIX_TEST_PROFILE_INVALID:" + reason)


def _records(payload: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    values = payload.get(key)
    _require(isinstance(values, list), key)
    records: dict[str, dict[str, Any]] = {}
    for item in values:
        _require(isinstance(item, dict), key + ":record")
        path = item.get("path")
        _require(isinstance(path, str) and path not in records, key + ":path")
        records[path] = item
    return records


def collection_profile(root: Path) -> str:
    """Validate the generated archive declaration; source admission is still required.

    This checks package consistency, not a signature or evidence that source tests
    passed. A source checkout always requires its real workflow court and files.
    """
    marker = root / "PHOENIX_CORE_MANIFEST.json"
    if not marker.exists():
        for relative in [SOURCE_COURT, *WORKFLOW_PATHS]:
            _require((root / relative).is_file(), "SOURCE_DEPENDENCY_MISSING:" + relative)
        return "SOURCE"

    _require(not marker.is_symlink(), "manifest_symlink")
    _require(not (root / ".git").exists(), "source_checkout_has_archive_marker")
    payload = json.loads(marker.read_text(encoding="utf-8"))
    _require(isinstance(payload, dict), "manifest_object")
    _require(payload.get("schema") == "FEDOMEGA-PHOENIX-EXPORT-MANIFEST-1", "manifest_schema")
    _require(payload.get("target") == "Federation-Omega-Core", "target")
    _require(payload.get("repository_role") == "CANONICAL_SOURCE_ONLY", "repository_role")
    _require(payload.get("test_profile") == PROFILE, "test_profile")
    _require(payload["test_profile"].get("source_admission_required") is True, "source_admission_required")
    invariants = payload.get("invariants", {})
    for key in ("workflow_count", "runtime_state_count", "migration_control_test_count", "secret_marker_count"):
        _require(type(invariants.get(key)) is int and invariants[key] == 0, "invariant:" + key)
    included = _records(payload, "files")
    excluded = _records(payload, "excluded")
    _require(not set(included).intersection(excluded), "overlapping_records")
    for relative in [SOURCE_COURT, *WORKFLOW_PATHS]:
        path = root / relative
        _require(not path.exists() and not path.is_symlink(), "excluded_path_present:" + relative)
        record = excluded.get(relative, {})
        reason = "MIGRATION_CONTROL_TEST_NOT_CORE_SOURCE" if relative == SOURCE_COURT else "GITHUB_WORKFLOW_NOT_CORE_SOURCE"
        _require(record.get("classification") == "CORE_EXCLUDED" and record.get("reason") == reason, "excluded_record:" + relative)
        _require(isinstance(record.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is not None, "excluded_hash:" + relative)
        _require(type(record.get("size")) is int and record["size"] > 0, "excluded_size:" + relative)
    for relative in PORTABLE_LOADERS:
        path = root / relative
        record = included.get(relative, {})
        _require(path.is_file() and not path.is_symlink(), "portable_loader_missing:" + relative)
        _require(record.get("classification") == "CORE_INCLUDED" and record.get("reason") == "APPROVED_SOURCE_FILE", "included_record:" + relative)
        data = path.read_bytes()
        _require(record.get("size") == len(data) and record.get("sha256") == hashlib.sha256(data).hexdigest(), "included_hash:" + relative)
    return "PORTABLE_CORE"


def attach_source_case(namespace: dict[str, Any], root: Path, class_name: str) -> None:
    """Expose the real TestCase to both unittest and pytest in existing courts."""
    if collection_profile(root) == "PORTABLE_CORE":
        return
    path = root / SOURCE_COURT
    name = "_phoenix_source_workflow_court_" + hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:16]
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, path)
        _require(spec is not None and spec.loader is not None, "source_court_loader")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[name] = module
    case = getattr(module, class_name)
    namespace[class_name] = case
