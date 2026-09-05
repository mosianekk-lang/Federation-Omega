"""Structured CI failure triage for CFBE/FUSE.

The triage layer separates candidate-owned regressions from environment, packaging
and pre-existing baseline failures without weakening admission: every unresolved
failure still blocks promotion. The separation exists to shorten diagnosis and
choose the smallest repair route.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
import json
import re
from typing import Iterable


def _stable_hash(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return sha256(body.encode("utf-8")).hexdigest()


def _normalise(value: str) -> str:
    return " ".join((value or "").replace("\\", "/").split())


@dataclass(frozen=True)
class CIFailureFinding:
    test_id: str
    failure_kind: str
    signature: str
    candidate_owned: bool
    repair_hint: str
    evidence_excerpt: str


@dataclass(frozen=True)
class CIFailureReceipt:
    receipt_id: str
    base_sha: str
    head_sha: str
    run_id: str
    job_id: str
    admission_blocked: bool
    candidate_failures: tuple[CIFailureFinding, ...]
    baseline_failures: tuple[CIFailureFinding, ...]
    unknown_failures: tuple[CIFailureFinding, ...]
    repair_order: tuple[str, ...]

    @property
    def failure_count(self) -> int:
        return len(self.candidate_failures) + len(self.baseline_failures) + len(self.unknown_failures)


class CIFailureTriage:
    """Parse Python unittest-style CI logs into an admission-safe failure receipt."""

    _HEADER = re.compile(r"^(ERROR|FAIL):\s+(.+)$", re.MULTILINE)
    _SEP = re.compile(r"\n={20,}\n")

    def triage(
        self,
        log_text: str,
        *,
        candidate_paths: Iterable[str] = (),
        base_sha: str = "",
        head_sha: str = "",
        run_id: str = "",
        job_id: str = "",
    ) -> CIFailureReceipt:
        candidate_tokens = self._candidate_tokens(candidate_paths)
        blocks = self._failure_blocks(log_text)
        candidate: list[CIFailureFinding] = []
        baseline: list[CIFailureFinding] = []
        unknown: list[CIFailureFinding] = []

        for block in blocks:
            header = self._HEADER.search(block)
            if not header:
                continue
            test_id = _normalise(header.group(2))
            owned = any(token and token in block.replace("\\", "/") for token in candidate_tokens)
            kind, signature, repair_hint, bucket = self._classify(block, owned)
            excerpt = self._excerpt(block)
            finding = CIFailureFinding(
                test_id=test_id,
                failure_kind=kind,
                signature=signature,
                candidate_owned=owned,
                repair_hint=repair_hint,
                evidence_excerpt=excerpt,
            )
            if bucket == "candidate":
                candidate.append(finding)
            elif bucket == "baseline":
                baseline.append(finding)
            else:
                unknown.append(finding)

        repair_order = tuple(
            item
            for item, present in (
                ("REPAIR_CANDIDATE_REGRESSIONS", bool(candidate)),
                ("REPAIR_TEST_ENVIRONMENT_OR_PACKAGING", bool(baseline)),
                ("INVESTIGATE_UNCLASSIFIED_FAILURES", bool(unknown)),
                ("RERUN_EXACT_HEAD_FULL_COURT", bool(candidate or baseline or unknown)),
            )
            if present
        )
        material = {
            "base_sha": base_sha,
            "head_sha": head_sha,
            "run_id": run_id,
            "job_id": job_id,
            "candidate": [(x.test_id, x.failure_kind, x.signature) for x in candidate],
            "baseline": [(x.test_id, x.failure_kind, x.signature) for x in baseline],
            "unknown": [(x.test_id, x.failure_kind, x.signature) for x in unknown],
        }
        return CIFailureReceipt(
            receipt_id="ci_" + _stable_hash(material)[:20],
            base_sha=base_sha,
            head_sha=head_sha,
            run_id=run_id,
            job_id=job_id,
            admission_blocked=bool(candidate or baseline or unknown),
            candidate_failures=tuple(candidate),
            baseline_failures=tuple(baseline),
            unknown_failures=tuple(unknown),
            repair_order=repair_order,
        )

    def _failure_blocks(self, log_text: str) -> tuple[str, ...]:
        text = "\n" + (log_text or "")
        parts = self._SEP.split(text)
        return tuple(part for part in parts if self._HEADER.search(part))

    @staticmethod
    def _candidate_tokens(candidate_paths: Iterable[str]) -> tuple[str, ...]:
        tokens: set[str] = set()
        for raw in candidate_paths:
            path = raw.replace("\\", "/").strip()
            if not path:
                continue
            tokens.add(path)
            tokens.add(PurePosixPath(path).name)
            if path.endswith(".py"):
                tokens.add(path[:-3].replace("/", "."))
        return tuple(sorted(tokens, key=lambda item: (-len(item), item)))

    @staticmethod
    def _classify(block: str, candidate_owned: bool) -> tuple[str, str, str, str]:
        lowered = block.lower()

        if "mission_ir_proof_requirements_required" in lowered:
            return (
                "CANONICAL_CONTRACT_DRIFT",
                "MISSION_IR_PROOF_REQUIREMENTS_REQUIRED",
                "Use one canonical valid MissionIR factory/fixture; do not maintain ad-hoc constructors.",
                "candidate",
            )
        if "hold_uas" in lowered and "complete" in lowered:
            return (
                "PROOF_STATE_CONFLATION",
                "EFFECT_VERIFIED_BUT_MISSION_OR_PROMOTION_HELD",
                "Separate effect state, mission state and promotion/UAS state in receipts and assertions.",
                "candidate",
            )
        if "nonetype" in lowered and "failed_uncertain" in lowered:
            return (
                "EFFECT_STATE_PERSISTENCE_GAP",
                "EXPECTED_FAILED_UNCERTAIN_EFFECT_NOT_READ_BACK",
                "Trace the durable effect key through intent, transition and readback; preserve uncertain state on mismatch.",
                "candidate",
            )
        if candidate_owned:
            return (
                "CANDIDATE_REGRESSION",
                "CANDIDATE_" + _stable_hash(_normalise(block))[:16],
                "Patch the smallest candidate-owned cause and bind a regression before rerunning the exact-head court.",
                "candidate",
            )
        if "modulenotfounderror" in lowered or "no module named" in lowered:
            match = re.search(r"No module named ['\"]([^'\"]+)", block, re.IGNORECASE)
            module = match.group(1) if match else "UNKNOWN_MODULE"
            return (
                "ENVIRONMENT_DEPENDENCY",
                f"MISSING_MODULE:{module}",
                "Reconcile the CI dependency contract with the tests; do not quarantine a missing required dependency as a passing baseline.",
                "baseline",
            )
        if "filenotfounderror" in lowered:
            return (
                "PACKAGING_OR_FIXTURE_CONTRACT",
                "MISSING_REQUIRED_TEST_FILE",
                "Align extraction/packaging with the files the test contract requires, or remove the invalid dependency from the test.",
                "baseline",
            )
        if "assertionerror" in lowered or "valueerror" in lowered or "typeerror" in lowered:
            return (
                "BASELINE_TEST_FAILURE",
                "BASELINE_" + _stable_hash(_normalise(block))[:16],
                "Establish whether the failure exists on current main, then repair it or bind an explicit time-bounded baseline exception without weakening admission.",
                "baseline",
            )
        return (
            "UNCLASSIFIED_CI_FAILURE",
            "UNKNOWN_" + _stable_hash(_normalise(block))[:16],
            "Preserve the complete failure evidence and form a new diagnostic route before retrying.",
            "unknown",
        )

    @staticmethod
    def _excerpt(block: str, *, limit: int = 700) -> str:
        compact = _normalise(block)
        return compact if len(compact) <= limit else compact[: limit - 3] + "..."


__all__ = ["CIFailureFinding", "CIFailureReceipt", "CIFailureTriage"]
