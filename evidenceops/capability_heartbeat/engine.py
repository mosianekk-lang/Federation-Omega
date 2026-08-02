"""Read-only catalogue facade governed exclusively by verified-v4 authority."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .authority import VerifiedV4Authority
from .foundation.adapters.common import Observation
from .foundation.contracts import BlockerCode, CapabilityStatus, digest
from .foundation.errors import ContractError, HeartbeatError
from .foundation.privacy import strict_json_loads

SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{2,128}$")
SAFE_TAG = re.compile(r"^[a-z0-9-]{2,48}$")
PROOF_CONFIDENCE = {
    "NONE": 0,
    "DESIGNED": 2500,
    "TESTED": 7000,
    "LEDGER_READBACK": 7600,
    "CONNECTOR_READBACK": 8000,
    "INDEPENDENT_READBACK": 8800,
    "MULTI_SOURCE_VERIFIED": 9200,
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def capability_code(value: str) -> str:
    compact = re.sub(r"[^A-Z0-9]", "", value.upper())
    if not compact:
        raise HeartbeatError("catalogue capability code is empty")
    return "CAP-" + compact[:40]


@dataclass(frozen=True, slots=True)
class Candidate:
    source_id: str
    system: str
    capability_id: str
    authority_code: str
    tags: tuple[str, ...]
    route: str
    state: str
    proof_level: str
    authority_class: str
    external_effect: bool
    catalogue_present: bool
    source_fingerprint: str
    solution_fingerprint: str
    confidence_bp: int
    evidence_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "system": self.system,
            "capability_id": self.capability_id,
            "authority_code": self.authority_code,
            "tags": list(self.tags),
            "route": self.route,
            "state": self.state,
            "proof_level": self.proof_level,
            "authority_class": self.authority_class,
            "external_effect": self.external_effect,
            "catalogue_present": self.catalogue_present,
            "source_fingerprint": self.source_fingerprint,
            "solution_fingerprint": self.solution_fingerprint,
            "confidence_bp": self.confidence_bp,
            "evidence_count": self.evidence_count,
            "ingress_authorized": False,
        }


class CapabilityHeartbeatEngine:
    """Inventory facade; all recommendations come from ``VerifiedV4Authority``."""

    def __init__(
        self,
        root: str | Path,
        registry_path: str | Path,
        bible_node_path: str | Path | None = None,
        *,
        authority: VerifiedV4Authority | None = None,
    ):
        self.root = Path(root).resolve(strict=True)
        self.registry_path = self._resolve_path(registry_path)
        self.registry = self._load_json(self.registry_path)
        self.bible_node_path = self._resolve_path(bible_node_path) if bible_node_path else None
        self.authority = authority
        self._validate_registry()

    def _resolve_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            unresolved = candidate
        else:
            unresolved = self.root / candidate
        try:
            unresolved.relative_to(self.root)
        except ValueError as exc:
            raise HeartbeatError("path escapes repository root") from exc
        current = self.root
        for segment in unresolved.relative_to(self.root).parts:
            if segment in {"", ".", ".."}:
                raise HeartbeatError("unsafe repository path segment")
            current = current / segment
            if current.is_symlink():
                raise HeartbeatError("symlink repository path prohibited")
        resolved = unresolved.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise HeartbeatError("path escapes repository root") from exc
        return resolved

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        try:
            value = strict_json_loads(path.read_text(encoding="utf-8"), field=path.name)
        except (OSError, ValueError, ContractError) as exc:
            raise HeartbeatError(f"cannot load strict JSON contract: {path.name}") from exc
        if not isinstance(value, dict):
            raise HeartbeatError("JSON contract must be an object")
        return value

    def _validate_registry(self) -> None:
        if self.registry.get("schema") != "EVIDENCEOPS-CAPABILITY-HEARTBEAT-2":
            raise HeartbeatError("unsupported heartbeat registry schema")
        if self.registry.get("fixture_mode") != "SYNTHETIC_STATIC_CATALOGUE":
            raise HeartbeatError("static catalogue must be explicitly synthetic")
        for field in ("owner_code", "matter_code"):
            if not isinstance(self.registry.get(field), str):
                raise HeartbeatError(f"catalogue {field} is required")
        sources = self.registry.get("sources")
        if not isinstance(sources, list) or not sources:
            raise HeartbeatError("heartbeat sources are required")
        seen_sources: set[str] = set()
        seen_codes: set[str] = set()
        for source in sources:
            source_id = source.get("source_id", "")
            if not SAFE_ID.fullmatch(source_id) or source_id in seen_sources:
                raise HeartbeatError("source_id is invalid or duplicated")
            seen_sources.add(source_id)
            paths = source.get("evidence_paths")
            if not isinstance(paths, list) or not paths:
                raise HeartbeatError(f"evidence paths are required for {source_id}")
            for path in paths:
                if not isinstance(path, str) or Path(path).is_absolute() or ".." in Path(path).parts:
                    raise HeartbeatError(f"unsafe evidence path for {source_id}")
            capabilities = source.get("capabilities")
            if not isinstance(capabilities, list) or not capabilities:
                raise HeartbeatError(f"capabilities are required for {source_id}")
            for item in capabilities:
                capability_id = item.get("capability_id", "")
                code = capability_code(capability_id)
                if not SAFE_ID.fullmatch(capability_id) or code in seen_codes:
                    raise HeartbeatError("capability identifier is invalid or collides after normalization")
                seen_codes.add(code)
                if item.get("proof_level") not in PROOF_CONFIDENCE:
                    raise HeartbeatError(f"unknown proof level for {capability_id}")
                if item.get("authority_class") != "A0":
                    raise HeartbeatError("catalogue authority ceiling must be A0")
                tags = item.get("tags")
                if not isinstance(tags, list) or any(not isinstance(tag, str) or not SAFE_TAG.fullmatch(tag) for tag in tags):
                    raise HeartbeatError("catalogue tags must be controlled codes")

    def _repository_version(self) -> str:
        value = os.getenv("GITHUB_SHA", "").strip()
        if value:
            return value
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.root,
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return "UNVERSIONED"

    def collect(self) -> tuple[list[dict[str, Any]], list[Candidate]]:
        heartbeats: list[dict[str, Any]] = []
        candidates: list[Candidate] = []
        for source in self.registry["sources"]:
            evidence: list[dict[str, Any]] = []
            all_present = True
            for relative in source["evidence_paths"]:
                path = self._resolve_path(relative)
                present = path.is_file()
                all_present = all_present and present
                evidence.append({
                    "path_code": "PATH-" + sha256_bytes(relative.encode("utf-8"))[:16].upper(),
                    "present": present,
                    "sha256": "sha256:" + sha256_bytes(path.read_bytes()) if present else None,
                })
            source_fingerprint = digest(evidence)
            heartbeats.append({
                "source_id": source["source_id"],
                "system_code": source["system_code"],
                "status": "CURRENT" if all_present else "DEGRADED",
                "source_fingerprint": source_fingerprint,
                "evidence": evidence,
                "catalogue_only": True,
                "ingress_authorized": False,
                "private_values_persisted": False,
            })
            for item in source["capabilities"]:
                tags = tuple(sorted(set(item.get("tags") or [])))
                code = capability_code(item["capability_id"])
                solution_fingerprint = digest({
                    "authority_code": code,
                    "tags": tags,
                    "route_code": item["route_code"],
                    "external_effect": bool(item.get("external_effect")),
                })
                candidates.append(Candidate(
                    source_id=source["source_id"],
                    system=source["system_code"],
                    capability_id=item["capability_id"],
                    authority_code=code,
                    tags=tags,
                    route=item["route_code"],
                    state=item["state"],
                    proof_level=item["proof_level"],
                    authority_class="A0",
                    external_effect=bool(item.get("external_effect")),
                    catalogue_present=all_present,
                    source_fingerprint=source_fingerprint,
                    solution_fingerprint=solution_fingerprint,
                    confidence_bp=PROOF_CONFIDENCE[item["proof_level"]],
                    evidence_count=sum(1 for value in evidence if value["present"]),
                ))
        return heartbeats, candidates

    def _observation(self, candidate: Candidate, *, now: str) -> Observation:
        eligible = (
            candidate.catalogue_present
            and candidate.state in {"EXECUTABLE_NOW", "VERIFY_ONLY"}
            and not candidate.external_effect
            and candidate.authority_class == "A0"
        )
        blocker = BlockerCode.NONE if eligible else (
            BlockerCode.AUTHORITY_UNAVAILABLE if candidate.external_effect else BlockerCode.CAPABILITY_ABSENT
        )
        status = CapabilityStatus.AVAILABLE if eligible else CapabilityStatus.UNAVAILABLE
        semantic = {
            "source_fingerprint": candidate.source_fingerprint,
            "solution_fingerprint": candidate.solution_fingerprint,
            "catalogue_present": candidate.catalogue_present,
            "state": candidate.state,
            "external_effect": candidate.external_effect,
        }
        return Observation(
            source_code="LOCAL_REPO",
            node_id=self.authority.policy.root_node_id if self.authority else "NODE-ROOT",
            owner_code=self.registry["owner_code"],
            matter_code=self.registry["matter_code"],
            capability_code=candidate.authority_code,
            status=status,
            confidence_bp=candidate.confidence_bp,
            freshness_seconds=0,
            evidence_count=candidate.evidence_count,
            blocker_code=blocker,
            capability_hash=digest({"capability": candidate.authority_code, "semantic": semantic}),
            observed_at=now,
            semantic_receipt=digest({"observed_at": now, "semantic": semantic}),
        )

    def _route_requirement(self, requirement: dict[str, Any], candidates: list[Candidate], *, now: str) -> dict[str, Any]:
        if self.authority is None:
            raise HeartbeatError("VERIFIED_V4_AUTHORITY_REQUIRED")
        allowed = {
            "requirement_id", "tags", "minimum_proof", "maximum_authority",
            "baseline_score", "baseline_safety", "improvement_threshold", "effectful_permit",
        }
        if set(requirement) - allowed:
            raise HeartbeatError("unknown requirement field")
        requirement_id = requirement.get("requirement_id", "")
        if not SAFE_ID.fullmatch(requirement_id):
            raise HeartbeatError("requirement_id is invalid")
        tags = requirement.get("tags")
        if not isinstance(tags, list) or not tags or any(not isinstance(tag, str) or not SAFE_TAG.fullmatch(tag) for tag in tags):
            raise HeartbeatError("requirement tags are required controlled codes")
        if requirement.get("maximum_authority", "A0") != "A0" or requirement.get("effectful_permit", False):
            raise HeartbeatError("heartbeat recommendation authority is A0 only")
        matches = [item for item in candidates if set(tags).intersection(item.tags)]
        observations = tuple(self._observation(item, now=now) for item in matches)
        result = self.authority.recommend(observations=observations, now=now)
        by_code = {item.authority_code: item for item in matches}
        mapped = []
        for recommendation in result.recommendations:
            candidate = by_code[recommendation.capability_code]
            mapped.append({
                **candidate.to_dict(),
                "score": recommendation.score,
                "role": recommendation.role.value,
                "blocker_code": recommendation.blocker_code.value,
                "authority_source": "VERIFIED_V4_FOUNDATION",
            })
        primary = next((item for item in mapped if item["role"] == "PREFERRED"), None)
        assistants = [item for item in mapped if item["role"] == "BACKUP"]
        escalation = next((item for item in mapped if item["role"] == "ESCALATION"), None)
        held = [
            {
                "source_id": item.source_id,
                "capability_id": item.capability_id,
                "reasons": [
                    "CATALOGUE_ONLY_CANNOT_AUTHORIZE_INGRESS",
                    "EFFECTFUL_ROUTE_PROHIBITED" if item.external_effect else "FOUNDATION_SCORE_BELOW_THRESHOLD",
                ],
            }
            for item in matches
            if item.authority_code not in {value["authority_code"] for value in mapped}
        ]
        return {
            "requirement_id": requirement_id,
            "decision": "FOUNDATION_RECOMMENDATION" if primary else "GAP_OR_HELD",
            "primary": primary,
            "assistants": assistants,
            "escalation": escalation,
            "held": held,
            "effectful_path_count": 0,
            "authority_ceiling": "A0",
            "policy_hash": self.authority.policy.policy_hash,
            "input_digest": result.input_digest,
        }

    def route_requirements(self, requirements: list[dict[str, Any]], *, now: str | None = None) -> list[dict[str, Any]]:
        if not isinstance(requirements, list):
            raise HeartbeatError("requirements must be a list")
        _, candidates = self.collect()
        observed_at = now or utcnow()
        return [self._route_requirement(item, candidates, now=observed_at) for item in requirements]

    def run(self, context_path: str | Path, *, now: str | None = None) -> dict[str, Any]:
        context = self._load_json(self._resolve_path(context_path))
        if context.get("schema") != "EVIDENCEOPS-CURRENT-WORKFLOW-2":
            raise HeartbeatError("unsupported current-workflow schema")
        if context.get("fixture_mode") != "SYNTHETIC_STATIC_WORKFLOW":
            raise HeartbeatError("workflow fixture must be explicitly synthetic")
        requirements = context.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            raise HeartbeatError("current workflow requirements are required")
        observed_at = now or utcnow()
        heartbeats, candidates = self.collect()
        decisions = [self._route_requirement(item, candidates, now=observed_at) for item in requirements]
        body = {
            "schema": "EVIDENCEOPS-CAPABILITY-HEARTBEAT-REPORT-2",
            "workflow_code": context.get("workflow_code"),
            "workflow_version": context.get("workflow_version"),
            "repository_version": self._repository_version(),
            "runtime_state": "ON_INPUT_READ_ONLY_RECOMMENDATION",
            "source_count": len(heartbeats),
            "candidate_count": len(candidates),
            "heartbeats": heartbeats,
            "decisions": decisions,
            "authority_ceiling": "A0",
            "authority_source": "VERIFIED_V4_FOUNDATION",
            "scheduler_authority": False,
            "external_execution_attempted": False,
            "private_values_persisted": False,
            "live_awareness_flags": self.authority.live_awareness_flags if self.authority else {},
            "truth_boundary": (
                "The facade inventories local catalogue evidence and delegates every recommendation to "
                "verified-v4. It does not authorize ingress, execute routes, schedule work, or infer live chats."
            ),
        }
        return {**body, "generated_at": observed_at, "report_sha256": digest(body)}


__all__ = [
    "Candidate", "CapabilityHeartbeatEngine", "HeartbeatError", "SAFE_ID",
    "canonical_json", "sha256_value", "utcnow",
]
