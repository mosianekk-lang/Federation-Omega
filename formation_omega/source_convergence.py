"""Source convergence and admission-train primitives for Formation Ω MCE v1.

Provider-neutral: GitHub/provider adapters supply current/base/candidate blob
identities and check receipts. This module classifies concurrency and decides
whether a candidate may be losslessly re-anchored.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Iterable, Mapping


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256(value: Any) -> str:
    payload = value if isinstance(value, str) else _canonical_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


class SourceConvergenceClass(str, Enum):
    CURRENT_BASE = "CURRENT_BASE"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    DISJOINT_STALE_BY_ANCESTRY = "DISJOINT_STALE_BY_ANCESTRY"
    STRUCTURALLY_COMPATIBLE = "STRUCTURALLY_COMPATIBLE"
    SEMANTIC_CONFLICT = "SEMANTIC_CONFLICT"


class AdmissionState(str, Enum):
    CANDIDATE = "CANDIDATE"
    EXACT_HEAD_CHECKS_REQUIRED = "EXACT_HEAD_CHECKS_REQUIRED"
    CHECKS_PASSED = "CHECKS_PASSED"
    MAIN_RECHECK_REQUIRED = "MAIN_RECHECK_REQUIRED"
    READY_TO_MERGE = "READY_TO_MERGE"
    STALE_RECLASSIFY = "STALE_RECLASSIFY"
    MERGED_READBACK_REQUIRED = "MERGED_READBACK_REQUIRED"
    ADMITTED = "ADMITTED"


@dataclass(frozen=True)
class ChangeCapsule:
    change_id: str
    mission_id: str
    base_sha: str
    candidate_head_sha: str
    candidate_blobs: Mapping[str, str | None]
    base_blobs: Mapping[str, str | None]
    semantic_domains: tuple[str, ...]
    required_checks: tuple[str, ...]
    proof_boundary: str
    rollback_ref: str
    capsule_sha256: str

    @classmethod
    def create(
        cls,
        *,
        change_id: str,
        mission_id: str,
        base_sha: str,
        candidate_head_sha: str,
        candidate_blobs: Mapping[str, str | None],
        base_blobs: Mapping[str, str | None],
        semantic_domains: Iterable[str],
        required_checks: Iterable[str],
        proof_boundary: str,
        rollback_ref: str,
    ) -> "ChangeCapsule":
        change_id = str(change_id).strip()
        mission_id = str(mission_id).strip()
        base_sha = str(base_sha).strip()
        candidate_head_sha = str(candidate_head_sha).strip()
        if not all((change_id, mission_id, base_sha, candidate_head_sha)):
            raise ValueError("change identity, mission, base and candidate head are required")
        candidate_blobs = dict(sorted((str(path), blob) for path, blob in candidate_blobs.items()))
        base_blobs = dict(sorted((str(path), blob) for path, blob in base_blobs.items()))
        if not candidate_blobs:
            raise ValueError("candidate_blobs cannot be empty")
        if set(base_blobs) != set(candidate_blobs):
            raise ValueError("base_blobs must cover exactly candidate paths")
        body = {
            "change_id": change_id,
            "mission_id": mission_id,
            "base_sha": base_sha,
            "candidate_head_sha": candidate_head_sha,
            "candidate_blobs": candidate_blobs,
            "base_blobs": base_blobs,
            "semantic_domains": _clean(semantic_domains),
            "required_checks": _clean(required_checks),
            "proof_boundary": " ".join(str(proof_boundary).split()),
            "rollback_ref": str(rollback_ref).strip(),
        }
        if not body["proof_boundary"] or not body["rollback_ref"]:
            raise ValueError("proof_boundary and rollback_ref are required")
        return cls(capsule_sha256=_sha256(body), **body)


@dataclass(frozen=True)
class PathConvergence:
    path: str
    base_blob: str | None
    candidate_blob: str | None
    current_blob: str | None
    state: str
    safe_to_overlay: bool
    reason: str


@dataclass(frozen=True)
class SourceConvergenceDecision:
    change_id: str
    mission_id: str
    classification: SourceConvergenceClass
    current_main_sha: str
    capsule_sha256: str
    path_decisions: tuple[PathConvergence, ...]
    conflicting_paths: tuple[str, ...]
    compatible_overlap_paths: tuple[str, ...]
    already_applied_paths: tuple[str, ...]
    overlay_paths: tuple[str, ...]
    safe_auto_reanchor: bool
    reason: str
    decision_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdmissionPlan:
    change_id: str
    mission_id: str
    expected_main_sha: str
    candidate_head_sha: str
    required_checks: tuple[str, ...]
    state: AdmissionState
    passed_checks: tuple[str, ...] = ()
    merge_sha: str | None = None
    admission_sha256: str = ""

    @classmethod
    def create(cls, *, capsule: ChangeCapsule, decision: SourceConvergenceDecision, reanchored_candidate_head_sha: str) -> "AdmissionPlan":
        if not decision.safe_auto_reanchor:
            raise ValueError("unsafe convergence decision cannot enter automatic admission")
        body = {
            "change_id": capsule.change_id,
            "mission_id": capsule.mission_id,
            "expected_main_sha": decision.current_main_sha,
            "candidate_head_sha": str(reanchored_candidate_head_sha),
            "required_checks": capsule.required_checks,
            "state": AdmissionState.EXACT_HEAD_CHECKS_REQUIRED,
            "passed_checks": (),
            "merge_sha": None,
        }
        return cls(admission_sha256=_sha256({**body, "state": body["state"].value}), **body)

    def with_checks(self, passed_checks: Iterable[str]) -> "AdmissionPlan":
        passed = _clean(passed_checks)
        missing = sorted(set(self.required_checks) - set(passed))
        state = AdmissionState.CHECKS_PASSED if not missing else AdmissionState.EXACT_HEAD_CHECKS_REQUIRED
        body = {
            "change_id": self.change_id,
            "mission_id": self.mission_id,
            "expected_main_sha": self.expected_main_sha,
            "candidate_head_sha": self.candidate_head_sha,
            "required_checks": self.required_checks,
            "state": state,
            "passed_checks": passed,
            "merge_sha": self.merge_sha,
        }
        return AdmissionPlan(admission_sha256=_sha256({**body, "state": state.value}), **body)

    def recheck_main(self, observed_main_sha: str) -> "AdmissionPlan":
        checks_ok = set(self.required_checks).issubset(self.passed_checks)
        if not checks_ok:
            raise ValueError("cannot recheck main before required checks pass")
        state = AdmissionState.READY_TO_MERGE if observed_main_sha == self.expected_main_sha else AdmissionState.STALE_RECLASSIFY
        body = {
            "change_id": self.change_id,
            "mission_id": self.mission_id,
            "expected_main_sha": self.expected_main_sha,
            "candidate_head_sha": self.candidate_head_sha,
            "required_checks": self.required_checks,
            "state": state,
            "passed_checks": self.passed_checks,
            "merge_sha": self.merge_sha,
        }
        return AdmissionPlan(admission_sha256=_sha256({**body, "state": state.value}), **body)

    def merged(self, *, merge_sha: str) -> "AdmissionPlan":
        if self.state != AdmissionState.READY_TO_MERGE:
            raise ValueError("merge may only follow READY_TO_MERGE")
        body = {
            "change_id": self.change_id,
            "mission_id": self.mission_id,
            "expected_main_sha": self.expected_main_sha,
            "candidate_head_sha": self.candidate_head_sha,
            "required_checks": self.required_checks,
            "state": AdmissionState.MERGED_READBACK_REQUIRED,
            "passed_checks": self.passed_checks,
            "merge_sha": str(merge_sha),
        }
        return AdmissionPlan(admission_sha256=_sha256({**body, "state": body["state"].value}), **body)

    def readback(self, *, observed_main_sha: str) -> "AdmissionPlan":
        if self.state != AdmissionState.MERGED_READBACK_REQUIRED:
            raise ValueError("readback requires MERGED_READBACK_REQUIRED")
        state = AdmissionState.ADMITTED if observed_main_sha == self.merge_sha else AdmissionState.STALE_RECLASSIFY
        body = {
            "change_id": self.change_id,
            "mission_id": self.mission_id,
            "expected_main_sha": self.expected_main_sha,
            "candidate_head_sha": self.candidate_head_sha,
            "required_checks": self.required_checks,
            "state": state,
            "passed_checks": self.passed_checks,
            "merge_sha": self.merge_sha,
        }
        return AdmissionPlan(admission_sha256=_sha256({**body, "state": state.value}), **body)


def classify_convergence(
    capsule: ChangeCapsule,
    *,
    current_main_sha: str,
    current_blobs: Mapping[str, str | None],
    semantic_compatibility: Mapping[str, bool] | None = None,
) -> SourceConvergenceDecision:
    """Classify candidate portability against the current main tree.

    `current_blobs` must contain every candidate path. `None` means absent.
    Semantic compatibility is explicit evidence; it is never inferred.
    """

    semantic_compatibility = dict(semantic_compatibility or {})
    missing = sorted(set(capsule.candidate_blobs) - set(current_blobs))
    if missing:
        raise ValueError(f"current_blobs missing candidate paths: {missing}")

    paths: list[PathConvergence] = []
    conflicts: list[str] = []
    compatible: list[str] = []
    already: list[str] = []
    overlays: list[str] = []

    for path in sorted(capsule.candidate_blobs):
        base_blob = capsule.base_blobs[path]
        candidate_blob = capsule.candidate_blobs[path]
        current_blob = current_blobs[path]

        if current_blob == candidate_blob:
            state, safe, reason = "ALREADY_APPLIED", True, "Current main already contains the candidate blob."
            already.append(path)
        elif current_blob == base_blob:
            state, safe, reason = "UNCHANGED_SINCE_BASE", True, "Current main retained the candidate's base blob; overlay is lossless."
            overlays.append(path)
        elif base_blob is None and current_blob is None:
            state, safe, reason = "NEW_PATH_STILL_ABSENT", True, "Candidate adds a path that remains absent on current main."
            overlays.append(path)
        elif bool(semantic_compatibility.get(path)):
            state, safe, reason = "COMPATIBLE_OVERLAP_EXPLICIT", True, "Overlapping path was explicitly classified compatible; semantic reconciliation is required."
            compatible.append(path)
            overlays.append(path)
        else:
            state, safe, reason = "SEMANTIC_CONFLICT_UNRESOLVED", False, "Current main changed the same path to a third blob; no compatibility proof exists."
            conflicts.append(path)

        paths.append(PathConvergence(path, base_blob, candidate_blob, current_blob, state, safe, reason))

    if conflicts:
        classification, safe_auto = SourceConvergenceClass.SEMANTIC_CONFLICT, False
        reason = "At least one candidate path changed independently on current main without compatibility proof."
    elif len(already) == len(paths):
        classification, safe_auto = SourceConvergenceClass.ALREADY_APPLIED, True
        reason = "All candidate blobs are already present on current main."
    elif compatible:
        classification, safe_auto = SourceConvergenceClass.STRUCTURALLY_COMPATIBLE, False
        reason = "No hard conflict exists, but overlapping paths require a reconciled candidate and affected tests."
    elif current_main_sha == capsule.base_sha:
        classification, safe_auto = SourceConvergenceClass.CURRENT_BASE, True
        reason = "Candidate base is still current."
    else:
        classification, safe_auto = SourceConvergenceClass.DISJOINT_STALE_BY_ANCESTRY, True
        reason = "Main advanced, but candidate paths remain unchanged or absent; exact candidate blobs can be overlaid losslessly."

    body = {
        "change_id": capsule.change_id,
        "mission_id": capsule.mission_id,
        "classification": classification.value,
        "current_main_sha": str(current_main_sha),
        "capsule_sha256": capsule.capsule_sha256,
        "path_decisions": [asdict(item) for item in paths],
        "conflicting_paths": _clean(conflicts),
        "compatible_overlap_paths": _clean(compatible),
        "already_applied_paths": _clean(already),
        "overlay_paths": _clean(overlays),
        "safe_auto_reanchor": safe_auto,
        "reason": reason,
    }
    return SourceConvergenceDecision(
        change_id=capsule.change_id,
        mission_id=capsule.mission_id,
        classification=classification,
        current_main_sha=str(current_main_sha),
        capsule_sha256=capsule.capsule_sha256,
        path_decisions=tuple(paths),
        conflicting_paths=_clean(conflicts),
        compatible_overlap_paths=_clean(compatible),
        already_applied_paths=_clean(already),
        overlay_paths=_clean(overlays),
        safe_auto_reanchor=safe_auto,
        reason=reason,
        decision_sha256=_sha256(body),
    )


def reanchor_manifest(capsule: ChangeCapsule, decision: SourceConvergenceDecision) -> dict[str, str | None]:
    """Return exact candidate blobs to overlay on the decision's current main."""

    if not decision.safe_auto_reanchor:
        raise ValueError("automatic reanchor is not allowed for this convergence decision")
    return {path: capsule.candidate_blobs[path] for path in decision.overlay_paths}


def required_admission_actions(plan: AdmissionPlan) -> tuple[str, ...]:
    if plan.state == AdmissionState.EXACT_HEAD_CHECKS_REQUIRED:
        return tuple(f"RUN_CHECK:{name}" for name in plan.required_checks)
    if plan.state == AdmissionState.CHECKS_PASSED:
        return ("RECHECK_CURRENT_MAIN",)
    if plan.state == AdmissionState.READY_TO_MERGE:
        return ("MERGE_WITH_EXPECTED_HEAD_AND_EXPECTED_MAIN",)
    if plan.state == AdmissionState.STALE_RECLASSIFY:
        return ("RECLASSIFY_AGAINST_FRESH_MAIN",)
    if plan.state == AdmissionState.MERGED_READBACK_REQUIRED:
        return ("READBACK_SIGNED_MAIN",)
    if plan.state == AdmissionState.ADMITTED:
        return ()
    return ("PREPARE_CANDIDATE",)
