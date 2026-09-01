"""Deterministic, non-effect Omega-One parallel promotion court.

The module plans independent proof courts, validates their evidence DAG, and compiles
one fail-closed admission verdict.  It never performs deployment, provider calls,
credential access, branch mutation, or authority escalation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Iterable, Mapping


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class CourtStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


class AdmissionState(str, Enum):
    BLOCKED = "BLOCKED"
    ELIGIBLE_FOR_SHADOW = "ELIGIBLE_FOR_SHADOW"


@dataclass(frozen=True)
class CourtSpec:
    court_id: str
    purpose: str
    independent_lane: str


@dataclass(frozen=True)
class CourtResult:
    court_id: str
    status: CourtStatus
    candidate_sha: str
    evidence_refs: tuple[str, ...]
    verifier: str


@dataclass(frozen=True)
class EvidenceNode:
    node_id: str
    kind: str
    source_ref: str
    source_sha256: str
    depends_on: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.node_id or not self.kind or not self.source_ref:
            raise ValueError("evidence node identity, kind and source are required")
        if not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256):
            raise ValueError("evidence node requires a lowercase SHA-256")


class EvidenceDAG:
    """Validate evidence lineage without treating the graph as proof itself."""

    def __init__(self, nodes: Iterable[EvidenceNode]):
        self.nodes = tuple(nodes)

    def validate(self) -> str:
        by_id = {node.node_id: node for node in self.nodes}
        if len(by_id) != len(self.nodes):
            raise ValueError("duplicate evidence node id")
        for node in self.nodes:
            node.validate()
            unknown = set(node.depends_on) - set(by_id)
            if unknown:
                raise ValueError(f"unknown evidence dependencies: {sorted(unknown)}")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise ValueError("evidence DAG contains a cycle")
            if node_id in visited:
                return
            visiting.add(node_id)
            for dependency in by_id[node_id].depends_on:
                visit(dependency)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in sorted(by_id):
            visit(node_id)
        body = [
            {
                "node_id": node.node_id,
                "kind": node.kind,
                "source_ref": node.source_ref,
                "source_sha256": node.source_sha256,
                "depends_on": sorted(node.depends_on),
            }
            for node in sorted(self.nodes, key=lambda item: item.node_id)
        ]
        return hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


class ParallelPromotionMesh:
    """Static parallel plan; execution belongs to the external CI scheduler."""

    REQUIRED_COURTS = (
        CourtSpec("SOURCE_REGRESSION", "code, unit and regression proof", "engineering"),
        CourtSpec("SECURITY_PROVENANCE", "security and artifact lineage", "supply-chain"),
        CourtSpec("PROTOCOL_INTEROP", "MCP, A2A and OpenTelemetry conformance", "interop"),
        CourtSpec("CAPABILITY_VALUE", "capability evaluation and value boundaries", "evaluation"),
    )

    @classmethod
    def plan(cls) -> Mapping[str, object]:
        courts = [
            {
                "court_id": item.court_id,
                "purpose": item.purpose,
                "independent_lane": item.independent_lane,
                "depends_on": [],
            }
            for item in cls.REQUIRED_COURTS
        ]
        return {
            "execution_mode": "PARALLEL_NON_EFFECT",
            "courts": courts,
            "compiler_depends_on": [item.court_id for item in cls.REQUIRED_COURTS],
            "external_effect": False,
        }


@dataclass(frozen=True)
class AdmissionVerdict:
    state: AdmissionState
    reasons: tuple[str, ...]
    candidate_sha: str
    evidence_dag_sha256: str | None
    next_stage: str | None
    external_effect_authorized: bool
    verdict_sha256: str


class DeterministicAdmissionCompiler:
    """Compile only eligibility for a later shadow canary, never deployment authority."""

    @staticmethod
    def _digest(body: Mapping[str, object]) -> str:
        return hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @classmethod
    def compile(
        cls,
        *,
        candidate_sha: str,
        base_sha: str,
        reconciled_to_base: bool,
        capability_count: int,
        results: Iterable[CourtResult],
        evidence_dag: EvidenceDAG,
        provenance_ref: str | None,
        external_effect_requested: bool = False,
    ) -> AdmissionVerdict:
        reasons: list[str] = []
        if not _SHA_RE.fullmatch(candidate_sha) or not _SHA_RE.fullmatch(base_sha):
            reasons.append("INVALID_SOURCE_SHA")
        if not reconciled_to_base:
            reasons.append("NOT_RECONCILED_TO_CURRENT_BASE")
        if capability_count != 100:
            reasons.append("CAPABILITY_BASELINE_NOT_EXACTLY_100")
        if external_effect_requested:
            reasons.append("EXTERNAL_EFFECT_PROHIBITED")
        if not provenance_ref:
            reasons.append("BUILD_PROVENANCE_MISSING")

        by_id: dict[str, CourtResult] = {}
        for result in results:
            if result.court_id in by_id:
                reasons.append(f"DUPLICATE_COURT:{result.court_id}")
                continue
            by_id[result.court_id] = result
            if result.candidate_sha != candidate_sha:
                reasons.append(f"COURT_SHA_MISMATCH:{result.court_id}")
            if result.status != CourtStatus.PASS:
                reasons.append(f"COURT_NOT_PASS:{result.court_id}:{result.status.value}")
            if not result.evidence_refs:
                reasons.append(f"COURT_EVIDENCE_MISSING:{result.court_id}")
            if not result.verifier or result.verifier == result.court_id:
                reasons.append(f"INDEPENDENT_VERIFIER_MISSING:{result.court_id}")

        for spec in ParallelPromotionMesh.REQUIRED_COURTS:
            if spec.court_id not in by_id:
                reasons.append(f"REQUIRED_COURT_MISSING:{spec.court_id}")

        dag_sha: str | None = None
        try:
            dag_sha = evidence_dag.validate()
        except ValueError as exc:
            reasons.append(f"EVIDENCE_DAG_INVALID:{exc}")

        reasons = sorted(set(reasons))
        state = AdmissionState.BLOCKED if reasons else AdmissionState.ELIGIBLE_FOR_SHADOW
        next_stage = None if reasons else "SHADOW_NON_EFFECT"
        body = {
            "state": state.value,
            "reasons": reasons,
            "candidate_sha": candidate_sha,
            "base_sha": base_sha,
            "evidence_dag_sha256": dag_sha,
            "next_stage": next_stage,
            "external_effect_authorized": False,
        }
        return AdmissionVerdict(
            state=state,
            reasons=tuple(reasons),
            candidate_sha=candidate_sha,
            evidence_dag_sha256=dag_sha,
            next_stage=next_stage,
            external_effect_authorized=False,
            verdict_sha256=cls._digest(body),
        )
