#!/usr/bin/env python3
"""Hash-bound Phoenix cutover candidate generator, validator and apply launcher.

Candidate manifests are generated after source merge and artifact production.
They never assert permanent currentness. Runtime validation computes whether the
candidate is CURRENT_VERIFIED or superseded before the guarded provider route
may create authorization state or invoke a provider.
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
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
SCHEMA = "FEDOMEGA-PHOENIX-CUTOVER-CANDIDATE-1"
VALIDITY_SCHEMA = "FEDOMEGA-PHOENIX-CUTOVER-CANDIDATE-VALIDITY-1"
HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


class CandidateValidityError(RuntimeError):
    """Fail-closed candidate schema, integrity or binding error."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateValidityError(f"{label} is missing or invalid JSON") from exc
    if not isinstance(payload, dict):
        raise CandidateValidityError(f"{label} must be a JSON object")
    return payload


def _receipt_field_sha(receipt: dict[str, Any]) -> str:
    claimed = receipt.get("receipt_sha256")
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    actual = canonical_sha256(body)
    if not isinstance(claimed, str) or not HEX64.fullmatch(claimed) or claimed != actual:
        raise CandidateValidityError("export receipt embedded SHA-256 is invalid")
    return claimed


def build_candidate(
    *,
    source_sha: str,
    core_archive: Path,
    ops_archive: Path,
    export_receipt_path: Path,
    issue_number: int,
    provider_run_id: int,
    cutover_artifact_id: int,
    freeze_artifact_id: int,
    generated_at: datetime | None = None,
    supersedes_candidate_sha256: str | None = None,
) -> dict[str, Any]:
    if not HEX40.fullmatch(source_sha):
        raise CandidateValidityError("source_sha is invalid")
    if issue_number <= 0 or provider_run_id <= 0:
        raise CandidateValidityError("issue_number and provider_run_id must be positive")
    if cutover_artifact_id <= 0 or freeze_artifact_id <= 0:
        raise CandidateValidityError("artifact IDs must be positive")
    receipt = load_json(export_receipt_path, "export receipt")
    if receipt.get("schema") != "FEDOMEGA-PHOENIX-EXPORT-MANIFEST-1":
        raise CandidateValidityError("export receipt schema is invalid")
    if receipt.get("status") != "VERIFIED":
        raise CandidateValidityError("export receipt is not VERIFIED")
    if receipt.get("source_sha") != source_sha.lower():
        raise CandidateValidityError("export receipt source_sha does not match candidate")
    receipt_sha = _receipt_field_sha(receipt)
    core_sha = sha256_file(core_archive)
    ops_sha = sha256_file(ops_archive)
    if receipt.get("core", {}).get("sha256") != core_sha:
        raise CandidateValidityError("export receipt Core SHA-256 does not match archive")
    if receipt.get("ops", {}).get("sha256") != ops_sha:
        raise CandidateValidityError("export receipt Ops SHA-256 does not match archive")
    if supersedes_candidate_sha256 is not None and not HEX64.fullmatch(supersedes_candidate_sha256):
        raise CandidateValidityError("supersedes_candidate_sha256 is invalid")
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "candidate_state": "PROPOSED_FOR_PROVIDER_APPLY",
        "validity_semantics": "COMPUTED_NOT_STORED",
        "source_repository": "mosianekk-lang/Federation-Omega",
        "source_branch": "main",
        "source_sha": source_sha.lower(),
        "core_archive_sha256": core_sha,
        "ops_archive_sha256": ops_sha,
        "export_receipt_sha256": receipt_sha,
        "export_receipt_file_sha256": sha256_file(export_receipt_path),
        "issue_number": issue_number,
        "provider_run_id": provider_run_id,
        "cutover_artifact_id": cutover_artifact_id,
        "freeze_artifact_id": freeze_artifact_id,
        "generated_at": (generated_at or datetime.now(timezone.utc)).isoformat(),
        "provider_apply_performed": False,
        "credential_value_recorded": False,
        "supersedes_candidate_sha256": supersedes_candidate_sha256,
    }
    payload["candidate_sha256"] = canonical_sha256(payload)
    return payload


def verify_candidate_integrity(candidate: dict[str, Any]) -> None:
    if candidate.get("schema") != SCHEMA:
        raise CandidateValidityError("candidate schema is invalid")
    claimed = candidate.get("candidate_sha256")
    body = dict(candidate)
    body.pop("candidate_sha256", None)
    if not isinstance(claimed, str) or not HEX64.fullmatch(claimed):
        raise CandidateValidityError("candidate_sha256 is invalid")
    if claimed != canonical_sha256(body):
        raise CandidateValidityError("candidate embedded SHA-256 verification failed")
    if candidate.get("candidate_state") != "PROPOSED_FOR_PROVIDER_APPLY":
        raise CandidateValidityError("candidate state is not eligible for apply")
    if candidate.get("validity_semantics") != "COMPUTED_NOT_STORED":
        raise CandidateValidityError("candidate validity semantics are unsafe")
    if candidate.get("provider_apply_performed") is not False:
        raise CandidateValidityError("candidate incorrectly claims provider apply")
    if candidate.get("credential_value_recorded") is not False:
        raise CandidateValidityError("candidate records credential material")
    if not isinstance(candidate.get("source_sha"), str) or not HEX40.fullmatch(candidate["source_sha"]):
        raise CandidateValidityError("candidate source_sha is invalid")
    for field in (
        "core_archive_sha256", "ops_archive_sha256", "export_receipt_sha256",
        "export_receipt_file_sha256",
    ):
        if not isinstance(candidate.get(field), str) or not HEX64.fullmatch(candidate[field]):
            raise CandidateValidityError(f"candidate {field} is invalid")


def validate_candidate(
    candidate: dict[str, Any],
    *,
    core_archive: Path,
    ops_archive: Path,
    decision: dict[str, Any] | None = None,
    observed_source_sha: str | None = None,
) -> dict[str, Any]:
    verify_candidate_integrity(candidate)
    checks = {
        "core_archive": sha256_file(core_archive) == candidate["core_archive_sha256"],
        "ops_archive": sha256_file(ops_archive) == candidate["ops_archive_sha256"],
    }
    if decision is not None:
        checks.update({
            "decision_source": decision.get("source_sha") == candidate["source_sha"],
            "decision_core": decision.get("core_archive_sha256") == candidate["core_archive_sha256"],
            "decision_ops": decision.get("ops_archive_sha256") == candidate["ops_archive_sha256"],
        })
    if observed_source_sha is not None:
        if not isinstance(observed_source_sha, str) or not HEX40.fullmatch(observed_source_sha):
            raise CandidateValidityError("observed source SHA is invalid")
        checks["live_source"] = observed_source_sha.lower() == candidate["source_sha"]
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        reason_map = {
            "live_source": "SUPERSEDED_SOURCE_CHANGED",
            "core_archive": "SUPERSEDED_CORE_ARCHIVE_CHANGED",
            "ops_archive": "SUPERSEDED_OPS_ARCHIVE_CHANGED",
            "decision_source": "INVALID_DECISION_SOURCE_BINDING",
            "decision_core": "INVALID_DECISION_CORE_BINDING",
            "decision_ops": "INVALID_DECISION_OPS_BINDING",
        }
        return {
            "schema": VALIDITY_SCHEMA,
            "status": reason_map[failed[0]],
            "candidate_sha256": candidate["candidate_sha256"],
            "checks": checks,
            "failed_checks": failed,
            "provider_apply_allowed": False,
            "credential_value_recorded": False,
        }
    return {
        "schema": VALIDITY_SCHEMA,
        "status": "CURRENT_VERIFIED",
        "candidate_sha256": candidate["candidate_sha256"],
        "source_sha": candidate["source_sha"],
        "core_archive_sha256": candidate["core_archive_sha256"],
        "ops_archive_sha256": candidate["ops_archive_sha256"],
        "checks": checks,
        "failed_checks": [],
        "provider_apply_allowed": True,
        "credential_value_recorded": False,
    }


def _load_guarded() -> Any:
    path = HERE / "provider_cutover_guarded.py"
    if not path.is_file():
        raise CandidateValidityError("guarded provider launcher is missing")
    spec = importlib.util.spec_from_file_location("phoenix_candidate_guarded_base", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def execute_candidate_cutover(
    candidate: dict[str, Any],
    decision: dict[str, Any],
    *,
    state_dir: Path,
    execution_id: str,
    core_archive: Path,
    ops_archive: Path,
    provider_receipt_path: Path,
    owner: str = "mosianekk-lang",
    legacy: str = "Federation-Omega",
    core: str = "Federation-Omega-Core",
    ops: str = "Federation-Omega-Ops",
    now: datetime | None = None,
    provider_authority_available: bool | None = None,
    source_head_reader: Callable[[str, str], str] | None = None,
) -> dict[str, Any]:
    guarded = _load_guarded()
    authority = (
        bool(__import__("os").getenv("GH_ADMIN_TOKEN"))
        if provider_authority_available is None else provider_authority_available
    )
    observed = None
    if authority:
        reader = source_head_reader or guarded.live_source_head
        observed = reader(owner, legacy)
    validity = validate_candidate(
        candidate,
        core_archive=core_archive,
        ops_archive=ops_archive,
        decision=decision,
        observed_source_sha=observed,
    )
    if validity["status"] != "CURRENT_VERIFIED":
        return {
            "status": "CANDIDATE_INVALIDATED",
            "candidate_validity": validity,
            "provider_apply_invoked": False,
            "authorization_state_created": state_dir.exists(),
            "credential_value_recorded": False,
        }
    result = guarded.execute_guarded_cutover(
        decision,
        state_dir=state_dir,
        execution_id=execution_id,
        source_sha=candidate["source_sha"],
        core_archive=core_archive,
        ops_archive=ops_archive,
        provider_receipt_path=provider_receipt_path,
        owner=owner,
        legacy=legacy,
        core=core,
        ops=ops,
        now=now,
        provider_authority_available=authority,
        source_head_reader=source_head_reader or guarded.live_source_head,
    )
    result["candidate_validity"] = validity
    result["canonical_apply_entrypoint"] = "provider_cutover_candidate.py"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate-candidate", action="store_true")
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--candidate-output", type=Path)
    parser.add_argument("--decision", type=Path)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--execution-id")
    parser.add_argument("--core-archive", type=Path, required=True)
    parser.add_argument("--ops-archive", type=Path, required=True)
    parser.add_argument("--export-receipt", type=Path)
    parser.add_argument("--source-sha")
    parser.add_argument("--issue-number", type=int, default=166)
    parser.add_argument("--provider-run-id", type=int)
    parser.add_argument("--cutover-artifact-id", type=int)
    parser.add_argument("--freeze-artifact-id", type=int)
    parser.add_argument("--supersedes-candidate-sha256")
    parser.add_argument("--provider-receipt", type=Path, default=Path("phoenix-provider-cutover-v3-receipt.json"))
    parser.add_argument("--owner", default="mosianekk-lang")
    parser.add_argument("--legacy", default="Federation-Omega")
    parser.add_argument("--core", default="Federation-Omega-Core")
    parser.add_argument("--ops", default="Federation-Omega-Ops")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if args.generate_candidate:
        required = {
            "--candidate-output": args.candidate_output,
            "--export-receipt": args.export_receipt,
            "--source-sha": args.source_sha,
            "--provider-run-id": args.provider_run_id,
            "--cutover-artifact-id": args.cutover_artifact_id,
            "--freeze-artifact-id": args.freeze_artifact_id,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise CandidateValidityError(f"generation arguments missing: {missing}")
        candidate = build_candidate(
            source_sha=args.source_sha,
            core_archive=args.core_archive,
            ops_archive=args.ops_archive,
            export_receipt_path=args.export_receipt,
            issue_number=args.issue_number,
            provider_run_id=args.provider_run_id,
            cutover_artifact_id=args.cutover_artifact_id,
            freeze_artifact_id=args.freeze_artifact_id,
            supersedes_candidate_sha256=args.supersedes_candidate_sha256,
        )
        args.candidate_output.parent.mkdir(parents=True, exist_ok=True)
        args.candidate_output.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(candidate, indent=2, sort_keys=True))
        return 0

    if not args.candidate or not args.decision or not args.state_dir or not args.execution_id:
        raise CandidateValidityError("--candidate, --decision, --state-dir and --execution-id are required")
    candidate = load_json(args.candidate, "candidate manifest")
    decision = load_json(args.decision, "authorization decision")

    if not args.apply:
        validity = validate_candidate(
            candidate,
            core_archive=args.core_archive,
            ops_archive=args.ops_archive,
            decision=decision,
        )
        print(json.dumps(validity, indent=2, sort_keys=True))
        return 0 if validity["status"] == "CURRENT_VERIFIED" else 2

    result = execute_candidate_cutover(
        candidate,
        decision,
        state_dir=args.state_dir,
        execution_id=args.execution_id,
        core_archive=args.core_archive,
        ops_archive=args.ops_archive,
        provider_receipt_path=args.provider_receipt,
        owner=args.owner,
        legacy=args.legacy,
        core=args.core,
        ops=args.ops,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if str(result.get("status", "")).startswith("VERIFIED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
