"""Read a local Git worktree identity without Git execution or network access."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ..contracts import BlockerCode, CapabilityStatus
from ..errors import ContractError
from .common import Observation, make_observation, read_local_text, safe_root

GIT_OBJECT = re.compile(r"[0-9a-f]{40}")
GIT_REF_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def contained_git_reference(git_dir: Path, reference: str) -> Path:
    """Resolve a symbolic ref without permitting traversal or symlink escape."""
    parts = reference.split("/") if isinstance(reference, str) else []
    if (
        len(reference) > 200
        or len(parts) < 3
        or parts[0] != "refs"
        or any(
            not part
            or part in {".", ".."}
            or part.startswith(".")
            or part.endswith(".")
            or ".." in part
            or GIT_REF_SEGMENT.fullmatch(part) is None
            for part in parts
        )
    ):
        raise ContractError("INVALID_GIT_REFERENCE")
    git_real = git_dir.resolve(strict=True)
    current = git_real
    for index, part in enumerate(parts):
        candidate = current / part
        if candidate.is_symlink():
            raise ContractError("GIT_REFERENCE_SYMLINK_PROHIBITED")
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise ContractError("GIT_REFERENCE_UNAVAILABLE") from exc
        if not resolved.is_relative_to(git_real):
            raise ContractError("GIT_REFERENCE_ESCAPES_GIT_DIRECTORY")
        if index < len(parts) - 1 and not resolved.is_dir():
            raise ContractError("GIT_REFERENCE_PARENT_NOT_DIRECTORY")
        current = resolved
    if not current.is_file() or current.stat().st_size > 256:
        raise ContractError("GIT_REFERENCE_UNAVAILABLE")
    return current


def read_local_repo(
    root: str | Path,
    *,
    node_id: str,
    owner_code: str,
    matter_code: str,
    observed_at: str,
) -> Observation:
    repository = safe_root(root)
    git_dir = repository / ".git"
    if git_dir.is_symlink() or not git_dir.is_dir():
        raise ContractError("PLAIN_GIT_DIRECTORY_REQUIRED")
    head = read_local_text(git_dir, "HEAD").strip()
    reference_code = "DETACHED"
    if head.startswith("ref: "):
        reference = head[5:]
        target = contained_git_reference(git_dir, reference)
        head = target.read_text(encoding="ascii").strip()
        reference_code = "SYMBOLIC"
    if GIT_OBJECT.fullmatch(head) is None:
        raise ContractError("INVALID_GIT_OBJECT_ID")
    return make_observation(
        source_code="LOCAL_REPO",
        node_id=node_id,
        owner_code=owner_code,
        matter_code=matter_code,
        capability_code="LOCAL_REPO_STATE",
        status=CapabilityStatus.AVAILABLE,
        confidence_bp=9000,
        freshness_seconds=0,
        evidence_count=2,
        blocker_code=BlockerCode.NONE,
        observed_at=observed_at,
        semantic_value={"head_hash": "sha256:" + hashlib.sha256(head.encode("ascii")).hexdigest(), "reference_code": reference_code},
    )
