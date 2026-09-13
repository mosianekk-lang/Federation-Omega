from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable, Sequence


def _sha(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


class AcceptanceDomain(str, Enum):
    TEST = "TEST"
    PROOF = "PROOF"
    READBACK = "READBACK"
    ROLLBACK = "ROLLBACK"
    SECURITY = "SECURITY"


@dataclass(frozen=True, slots=True)
class AcceptanceWitness:
    witness_id: str
    domain: AcceptanceDomain
    actor_id: str
    trust_domain: str
    passed: bool
    evidence_refs: tuple[str, ...]
    relation_to_implementation: str = "INDEPENDENT"

    def validate(self) -> None:
        if not self.witness_id.strip() or not self.actor_id.strip() or not self.trust_domain.strip():
            raise ValueError("ACCEPTANCE_WITNESS_IDENTITY_REQUIRED")
        AcceptanceDomain(self.domain)
        if self.relation_to_implementation not in {"INDEPENDENT", "SAME_LANE"}:
            raise ValueError("ACCEPTANCE_RELATION_INVALID")
        if self.passed and not self.evidence_refs:
            raise ValueError("ACCEPTANCE_PASS_REQUIRES_EVIDENCE")


@dataclass(frozen=True, slots=True)
class AcceptanceIntegrityVerdict:
    status: str
    accepted: bool
    covered_domains: tuple[str, ...]
    missing_domains: tuple[str, ...]
    failed_domains: tuple[str, ...]
    non_independent_witnesses: tuple[str, ...]
    verdict_sha256: str


class AcceptanceIntegrityCourt:
    """Prevents the implementation lane from grading its own acceptance.

    The court only evaluates supplied evidence. It does not create proof, execute
    provider readback, or mutate source. Required domains remain caller-selected so
    provider/readback/rollback requirements can stay receiver-specific.
    """

    DEFAULT_REQUIRED = (
        AcceptanceDomain.TEST,
        AcceptanceDomain.PROOF,
        AcceptanceDomain.READBACK,
    )

    def evaluate(
        self,
        *,
        implementation_actor_id: str,
        witnesses: Sequence[AcceptanceWitness],
        required_domains: Iterable[AcceptanceDomain | str] = DEFAULT_REQUIRED,
    ) -> AcceptanceIntegrityVerdict:
        if not implementation_actor_id.strip():
            raise ValueError("IMPLEMENTATION_ACTOR_REQUIRED")
        required = tuple(sorted({AcceptanceDomain(value).value for value in required_domains}))
        if not required:
            raise ValueError("AT_LEAST_ONE_ACCEPTANCE_DOMAIN_REQUIRED")

        by_id: dict[str, AcceptanceWitness] = {}
        for row in witnesses:
            row.validate()
            if row.witness_id in by_id:
                raise ValueError("DUPLICATE_ACCEPTANCE_WITNESS")
            by_id[row.witness_id] = row

        independent = [
            row
            for row in witnesses
            if row.actor_id != implementation_actor_id and row.relation_to_implementation == "INDEPENDENT"
        ]
        non_independent = tuple(
            sorted(
                row.witness_id
                for row in witnesses
                if row.actor_id == implementation_actor_id or row.relation_to_implementation != "INDEPENDENT"
            )
        )
        covered = tuple(sorted({AcceptanceDomain(row.domain).value for row in independent if row.passed}))
        failed = tuple(
            sorted(
                {
                    AcceptanceDomain(row.domain).value
                    for row in independent
                    if AcceptanceDomain(row.domain).value in set(required) and not row.passed
                }
            )
        )
        missing = tuple(sorted(set(required) - set(covered)))

        accepted = not missing and not failed
        if failed:
            status = "HOLD_ACCEPTANCE_FAILURE"
        elif missing:
            status = "HOLD_INDEPENDENT_ACCEPTANCE_INCOMPLETE"
        else:
            status = "ACCEPTANCE_INTEGRITY_PASSED"

        body = {
            "implementation_actor_id": implementation_actor_id,
            "required_domains": required,
            "witnesses": tuple(sorted((row.witness_id, asdict(row)) for row in witnesses)),
            "covered": covered,
            "missing": missing,
            "failed": failed,
            "non_independent": non_independent,
            "status": status,
        }
        return AcceptanceIntegrityVerdict(
            status=status,
            accepted=accepted,
            covered_domains=covered,
            missing_domains=missing,
            failed_domains=failed,
            non_independent_witnesses=non_independent,
            verdict_sha256=_sha(body),
        )


__all__ = [
    "AcceptanceDomain",
    "AcceptanceIntegrityCourt",
    "AcceptanceIntegrityVerdict",
    "AcceptanceWitness",
]
