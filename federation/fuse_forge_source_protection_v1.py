"""FUSE Forge sovereign source protection v1.

Provider-neutral, effect-free source admission logic for Forge. It emits a merge
permit only after fresh-main CAS, an active fencing lease, signed head and
required proof courts pass. Repository mutation remains outside this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Iterable, Sequence

SCHEMA = "FUSE-FORGE-SOVEREIGN-SOURCE-PROTECTION-V1"
VERSION = "1.0.0"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _digest(value: object) -> str:
    raw=json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()
    return sha256(raw).hexdigest()


def _valid_sha(value: str) -> bool:
    return bool(_SHA_RE.fullmatch(str(value)))


@dataclass(frozen=True, slots=True)
class ProtectionPolicy:
    required_checks: tuple[str,...]=("admission","contract","scan")
    require_signed_head: bool=True
    forbid_direct_main: bool=True
    require_active_fence: bool=True
    require_fresh_main_cas: bool=True
    max_changed_paths: int=1000

    def validate(self) -> "ProtectionPolicy":
        if not self.required_checks or len(set(self.required_checks)) != len(self.required_checks):
            raise ValueError("FORGE_REQUIRED_CHECKS_INVALID")
        if self.max_changed_paths < 1:
            raise ValueError("FORGE_MAX_CHANGED_PATHS_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class LeaseFence:
    lease_id: str
    fencing_token: int
    state: str
    source_head: str

    def validate(self) -> "LeaseFence":
        if not self.lease_id.strip() or self.fencing_token < 1:
            raise ValueError("FORGE_FENCE_ID_TOKEN_REQUIRED")
        if not _valid_sha(self.source_head):
            raise ValueError("FORGE_FENCE_SOURCE_HEAD_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class CheckResult:
    check_id: str
    state: str
    evidence_ref: str

    def passed(self) -> bool:
        return self.state.upper() in {"PASS","SUCCESS","GREEN","VERIFIED"} and bool(self.evidence_ref.strip())


@dataclass(frozen=True, slots=True)
class SourceProposal:
    proposal_id: str
    base_sha: str
    head_sha: str
    author: str
    changed_paths: tuple[str,...]
    signed_head: bool
    direct_main_write: bool=False
    dependencies: tuple[str,...]=()

    def validate(self) -> "SourceProposal":
        if not self.proposal_id.strip() or not self.author.strip():
            raise ValueError("FORGE_PROPOSAL_ID_AUTHOR_REQUIRED")
        if not _valid_sha(self.base_sha) or not _valid_sha(self.head_sha) or self.base_sha == self.head_sha:
            raise ValueError("FORGE_PROPOSAL_SHA_INVALID")
        if not self.changed_paths or len(set(self.changed_paths)) != len(self.changed_paths):
            raise ValueError("FORGE_CHANGED_PATHS_INVALID")
        if self.proposal_id in self.dependencies:
            raise ValueError("FORGE_SELF_DEPENDENCY")
        return self


@dataclass(frozen=True, slots=True)
class MergePermit:
    schema: str
    proposal_id: str
    expected_main_sha: str
    expected_head_sha: str
    lease_id: str
    fencing_token: int
    required_checks: tuple[str,...]
    changed_paths_sha256: str
    external_effect_authorized: bool
    permit_sha256: str


@dataclass(frozen=True, slots=True)
class ProtectionDecision:
    state: str
    allowed: bool
    reasons: tuple[str,...]
    permit: MergePermit | None
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class MergeReadback:
    state: str
    verified: bool
    rollback_target_sha: str
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class QueueCandidate:
    proposal_id: str
    priority: int
    created_seq: int
    dependencies: tuple[str,...]=()


class SovereignSourceProtection:
    def __init__(self, policy: ProtectionPolicy | None=None) -> None:
        self.policy=(policy or ProtectionPolicy()).validate()

    def evaluate(
        self,
        *,
        current_main_sha: str,
        proposal: SourceProposal,
        lease: LeaseFence,
        checks: Sequence[CheckResult],
    ) -> ProtectionDecision:
        proposal=proposal.validate()
        lease=lease.validate()
        if not _valid_sha(current_main_sha):
            raise ValueError("FORGE_CURRENT_MAIN_INVALID")

        reasons:list[str]=[]
        if self.policy.forbid_direct_main and proposal.direct_main_write:
            reasons.append("DIRECT_MAIN_WRITE_FORBIDDEN")
        if self.policy.require_signed_head and not proposal.signed_head:
            reasons.append("SIGNED_HEAD_REQUIRED")
        if self.policy.require_fresh_main_cas and proposal.base_sha != current_main_sha:
            reasons.append("STALE_MAIN_CAS")
        if self.policy.require_active_fence and lease.state.upper() != "ACTIVE":
            reasons.append("ACTIVE_FENCE_REQUIRED")
        if lease.source_head != current_main_sha:
            reasons.append("FENCE_SOURCE_HEAD_MISMATCH")
        if len(proposal.changed_paths) > self.policy.max_changed_paths:
            reasons.append("CHANGED_PATH_LIMIT_EXCEEDED")

        by_id={c.check_id:c for c in checks}
        for required in self.policy.required_checks:
            row=by_id.get(required)
            if row is None:
                reasons.append(f"MISSING_CHECK:{required}")
            elif not row.passed():
                reasons.append(f"FAILED_CHECK:{required}")

        permit=None
        if not reasons:
            body={
                "schema":SCHEMA,
                "proposal_id":proposal.proposal_id,
                "expected_main_sha":current_main_sha,
                "expected_head_sha":proposal.head_sha,
                "lease_id":lease.lease_id,
                "fencing_token":lease.fencing_token,
                "required_checks":self.policy.required_checks,
                "changed_paths_sha256":_digest(sorted(proposal.changed_paths)),
                "external_effect_authorized":False,
            }
            permit=MergePermit(**body,permit_sha256=_digest(body))

        receipt={
            "state":"PERMIT_READY" if permit else "HOLD",
            "allowed":permit is not None,
            "reasons":reasons,
            "permit_sha256":permit.permit_sha256 if permit else None,
        }
        return ProtectionDecision(
            state=receipt["state"],
            allowed=receipt["allowed"],
            reasons=tuple(reasons),
            permit=permit,
            receipt_sha256=_digest(receipt),
        )

    @staticmethod
    def verify_permit(permit: MergePermit) -> bool:
        body=asdict(permit)
        digest=body.pop("permit_sha256")
        return digest == _digest(body) and permit.external_effect_authorized is False

    @staticmethod
    def order_queue(candidates: Sequence[QueueCandidate]) -> tuple[str,...]:
        if not candidates:
            return ()
        rows={c.proposal_id:c for c in candidates}
        if len(rows) != len(candidates):
            raise ValueError("FORGE_QUEUE_DUPLICATE_PROPOSAL")
        for c in candidates:
            if set(c.dependencies) - set(rows):
                raise ValueError("FORGE_QUEUE_UNKNOWN_DEPENDENCY")

        indegree={k:0 for k in rows}
        children={k:set() for k in rows}
        for c in candidates:
            for dep in c.dependencies:
                indegree[c.proposal_id]+=1
                children[dep].add(c.proposal_id)

        ready=[rows[k] for k,v in indegree.items() if v == 0]
        out:list[str]=[]
        while ready:
            ready.sort(key=lambda c:(-c.priority,c.created_seq,c.proposal_id))
            cur=ready.pop(0)
            out.append(cur.proposal_id)
            for child in sorted(children[cur.proposal_id]):
                indegree[child]-=1
                if indegree[child] == 0:
                    ready.append(rows[child])

        if len(out) != len(rows):
            raise ValueError("FORGE_QUEUE_DEPENDENCY_CYCLE")
        return tuple(out)

    @staticmethod
    def verify_merge_readback(
        *,
        permit: MergePermit,
        before_main_sha: str,
        after_main_sha: str,
        observed_head_sha: str,
        after_parent_shas: Iterable[str],
    ) -> MergeReadback:
        parents=tuple(after_parent_shas)
        exact_epoch=(
            SovereignSourceProtection.verify_permit(permit)
            and before_main_sha == permit.expected_main_sha
            and observed_head_sha == permit.expected_head_sha
            and after_main_sha != before_main_sha
        )
        fast_forward=after_main_sha == observed_head_sha and before_main_sha in parents
        merge_commit=before_main_sha in parents and observed_head_sha in parents
        verified=bool(exact_epoch and (fast_forward or merge_commit))
        body={
            "state":"MERGE_READBACK_VERIFIED" if verified else "MERGE_READBACK_HELD",
            "verified":verified,
            "rollback_target_sha":before_main_sha,
            "permit_sha256":permit.permit_sha256,
            "after_main_sha":after_main_sha,
            "observed_head_sha":observed_head_sha,
            "parents":parents,
        }
        return MergeReadback(
            state=body["state"],
            verified=verified,
            rollback_target_sha=before_main_sha,
            receipt_sha256=_digest(body),
        )
