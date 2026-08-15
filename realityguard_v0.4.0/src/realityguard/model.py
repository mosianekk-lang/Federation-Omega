"""Typed domain model for claim-versus-proof analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum, IntEnum
from typing import Any


class LifecycleState(IntEnum):
    DESCRIBED = 0
    BUILT = 1
    TESTED = 2
    STORED = 3
    REGISTERED = 4
    INSTALLED = 5
    BOUND = 6
    DEPLOYED = 7
    RUNNING = 8
    READ_BACK = 9
    ACCEPTED = 10


class EvidenceGrade(IntEnum):
    NONE = 0
    SELF_REPORTED = 1
    ARTIFACT = 2
    TEST_RESULT = 3
    PROVIDER_RECEIPT = 4
    INDEPENDENT_READBACK = 5
    OWNER_ACCEPTED = 6


class Verdict(str, Enum):
    ALLOW_BOUNDED = "ALLOW_BOUNDED"
    REWRITE_REQUIRED = "REWRITE_REQUIRED"
    BLOCK_COMPLETION = "BLOCK_COMPLETION"
    BLOCK_FALSE_REALITY = "BLOCK_FALSE_REALITY"
    REQUIRE_OWNER_DECISION = "REQUIRE_OWNER_DECISION"


@dataclass(frozen=True)
class Evidence:
    kind: str
    supports_state: LifecycleState
    grade: EvidenceGrade
    reference: str = ""
    scope: tuple[str, ...] = ()
    passed: bool = True
    current: bool = True
    semantic: bool = False
    independent: bool = False


@dataclass(frozen=True)
class Claim:
    text: str
    claimed_state: LifecycleState
    subject: str = "unspecified"
    scope: tuple[str, ...] = ()
    completion_asserted: bool = False
    ownership_asserted: bool = False
    capability_asserted: bool = False


@dataclass(frozen=True)
class Finding:
    code: str
    title: str
    severity: str
    explanation: str
    evidence_refs: tuple[str, ...] = ()
    mitigation: tuple[str, ...] = ()


@dataclass
class ScanResult:
    schema_version: str
    correlation_id: str
    verdict: Verdict
    claimed_state: LifecycleState
    proven_state: LifecycleState
    proof_grade: EvidenceGrade
    state_gap: int
    findings: list[Finding] = field(default_factory=list)
    safe_statement: str = ""
    missing_proof_gates: list[str] = field(default_factory=list)
    evidence_used: list[str] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["verdict"] = self.verdict.value
        value["claimed_state"] = self.claimed_state.name
        value["proven_state"] = self.proven_state.name
        value["proof_grade"] = self.proof_grade.name
        return value
