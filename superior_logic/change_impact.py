from __future__ import annotations

import fnmatch
import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence


class ImpactDecision(str, Enum):
    IGNORE_UNRELATED = "IGNORE_UNRELATED"
    RETEST_ONLY = "RETEST_ONLY"
    REBASE_REQUIRED = "REBASE_REQUIRED"


def _digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class MissionSnapshot:
    mission_id: str
    base_revision: str
    protected_paths: tuple[str, ...]
    retest_paths: tuple[str, ...]
    contract_paths: tuple[str, ...]
    source_epoch: int
    snapshot_sha256: str

    @classmethod
    def build(
        cls,
        *,
        mission_id: str,
        base_revision: str,
        protected_paths: Sequence[str],
        retest_paths: Sequence[str] = (),
        contract_paths: Sequence[str] = (),
        source_epoch: int,
    ) -> "MissionSnapshot":
        if not mission_id.strip() or not base_revision.strip():
            raise ValueError("mission_id and base_revision are required")
        body = {
            "mission_id": mission_id,
            "base_revision": base_revision,
            "protected_paths": tuple(sorted(set(protected_paths))),
            "retest_paths": tuple(sorted(set(retest_paths))),
            "contract_paths": tuple(sorted(set(contract_paths))),
            "source_epoch": int(source_epoch),
        }
        return cls(**body, snapshot_sha256=_digest(body))


@dataclass(frozen=True)
class ChangeImpactResult:
    decision: ImpactDecision
    changed_paths: tuple[str, ...]
    protected_hits: tuple[str, ...]
    retest_hits: tuple[str, ...]
    contract_hits: tuple[str, ...]
    ignored_paths: tuple[str, ...]
    reason: str


def _matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


class ChangeImpactCompiler:
    """Avoids unnecessary rebases while preserving contract-sensitive safety.

    Contract/protected changes require a rebase. Changes to test/assurance paths
    relevant to the mission require only a fresh proof court. Everything else is
    explicitly unrelated and may be ignored for mission-base continuity.
    """

    def evaluate(self, snapshot: MissionSnapshot, changed_paths: Sequence[str]) -> ChangeImpactResult:
        changed = tuple(sorted({str(item) for item in changed_paths if str(item).strip()}))
        protected: list[str] = []
        retest: list[str] = []
        contracts: list[str] = []
        ignored: list[str] = []
        for path in changed:
            if _matches(path, snapshot.contract_paths):
                contracts.append(path)
            elif _matches(path, snapshot.protected_paths):
                protected.append(path)
            elif _matches(path, snapshot.retest_paths):
                retest.append(path)
            else:
                ignored.append(path)

        if contracts or protected:
            decision = ImpactDecision.REBASE_REQUIRED
            reason = "mission source or compatibility contract changed"
        elif retest:
            decision = ImpactDecision.RETEST_ONLY
            reason = "mission-adjacent assurance/test surface changed without source-contract mutation"
        else:
            decision = ImpactDecision.IGNORE_UNRELATED
            reason = "all changes are outside the mission source, contract and proof surfaces"

        return ChangeImpactResult(
            decision=decision,
            changed_paths=changed,
            protected_hits=tuple(protected),
            retest_hits=tuple(retest),
            contract_hits=tuple(contracts),
            ignored_paths=tuple(ignored),
            reason=reason,
        )


__all__ = ["ChangeImpactCompiler", "ChangeImpactResult", "ImpactDecision", "MissionSnapshot"]
