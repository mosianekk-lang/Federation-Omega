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

SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{2,128}$")
PROOF_RANK = {
    "NONE": 0,
    "DESIGNED": 10,
    "TESTED": 40,
    "LEDGER_READBACK": 55,
    "CONNECTOR_READBACK": 60,
    "INDEPENDENT_READBACK": 80,
    "MULTI_SOURCE_VERIFIED": 90,
}
EXECUTABLE_STATES = {"EXECUTABLE_NOW", "VERIFY_ONLY"}


class HeartbeatError(ValueError):
    """Fail-closed validation error."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Candidate:
    source_id: str
    system: str
    capability_id: str
    name: str
    tags: tuple[str, ...]
    route: str
    state: str
    proof_level: str
    proof_rank: int
    quality: float
    safety: float
    reuse: float
    cost: float
    authority_class: str
    external_effect: bool
    available: bool
    source_fingerprint: str
    solution_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "system": self.system,
            "capability_id": self.capability_id,
            "name": self.name,
            "tags": list(self.tags),
            "route": self.route,
            "state": self.state,
            "proof_level": self.proof_level,
            "proof_rank": self.proof_rank,
            "quality": self.quality,
            "safety": self.safety,
            "reuse": self.reuse,
            "cost": self.cost,
            "authority_class": self.authority_class,
            "external_effect": self.external_effect,
            "available": self.available,
            "source_fingerprint": self.source_fingerprint,
            "solution_fingerprint": self.solution_fingerprint,
        }


class CapabilityHeartbeatEngine:
    """Read-only discovery and routing; it never executes a candidate route."""

    def __init__(
        self,
        root: str | Path,
        registry_path: str | Path,
        bible_node_path: str | Path | None = "evidenceops/capability_heartbeat/bible_node.json",
    ):
        self.root = Path(root).resolve()
        self.registry_path = self._resolve_path(registry_path)
        self.registry = self._load_json(self.registry_path)
        self.bible_node_path = self._resolve_path(bible_node_path) if bible_node_path else None
        self._validate_registry()

    def _resolve_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.root / candidate).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise HeartbeatError("path escapes repository root") from exc
        return resolved

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HeartbeatError(f"cannot load JSON contract: {path.name}") from exc
        if not isinstance(value, dict):
            raise HeartbeatError("JSON contract must be an object")
        return value

    def _validate_registry(self) -> None:
        if self.registry.get("schema") != "EVIDENCEOPS-CAPABILITY-HEARTBEAT-1":
            raise HeartbeatError("unsupported heartbeat registry schema")
        sources = self.registry.get("sources")
        if not isinstance(sources, list) or not sources:
            raise HeartbeatError("heartbeat sources are required")
        seen_sources: set[str] = set()
        seen_capabilities: set[tuple[str, str]] = set()
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
            for capability in capabilities:
                capability_id = capability.get("capability_id", "")
                key = (source_id, capability_id)
                if not SAFE_ID.fullmatch(capability_id) or key in seen_capabilities:
                    raise HeartbeatError("capability_id is invalid or duplicated within a source")
                seen_capabilities.add(key)
                proof = capability.get("proof_level")
                if proof not in PROOF_RANK:
                    raise HeartbeatError(f"unknown proof level for {capability_id}")
                for score in ("quality", "safety", "reuse"):
                    value = capability.get(score)
                    if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
                        raise HeartbeatError(f"{score} must be between zero and one")
                cost = capability.get("cost", 0)
                if not isinstance(cost, (int, float)) or float(cost) < 0:
                    raise HeartbeatError("cost must be non-negative")

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
                    "path": relative,
                    "present": present,
                    "sha256": sha256_bytes(path.read_bytes()) if present else None,
                })
            source_fingerprint = sha256_value(evidence)
            heartbeat = {
                "source_id": source["source_id"],
                "system": source["system"],
                "status": "CURRENT" if all_present else "DEGRADED",
                "source_fingerprint": source_fingerprint,
                "evidence": evidence,
                "private_values_persisted": False,
            }
            heartbeats.append(heartbeat)
            for item in source["capabilities"]:
                tags = tuple(sorted(set(item.get("tags") or [])))
                solution_fingerprint = sha256_value({
                    "tags": tags,
                    "route": item["route"],
                    "external_effect": bool(item.get("external_effect")),
                })
                candidates.append(Candidate(
                    source_id=source["source_id"],
                    system=source["system"],
                    capability_id=item["capability_id"],
                    name=item["name"],
                    tags=tags,
                    route=item["route"],
                    state=item["state"],
                    proof_level=item["proof_level"],
                    proof_rank=PROOF_RANK[item["proof_level"]],
                    quality=float(item["quality"]),
                    safety=float(item["safety"]),
                    reuse=float(item["reuse"]),
                    cost=float(item.get("cost", 0)),
                    authority_class=item.get("authority_class", "A0"),
                    external_effect=bool(item.get("external_effect")),
                    available=all_present and item["state"] in EXECUTABLE_STATES,
                    source_fingerprint=source_fingerprint,
                    solution_fingerprint=solution_fingerprint,
                ))
        return heartbeats, candidates

    @staticmethod
    def _score(candidate: Candidate, required_tags: set[str]) -> float:
        fit = len(required_tags.intersection(candidate.tags)) / max(1, len(required_tags))
        proof = candidate.proof_rank / 90
        cost_penalty = min(candidate.cost, 1.0)
        return round(
            0.28 * fit
            + 0.24 * proof
            + 0.22 * candidate.safety
            + 0.16 * candidate.quality
            + 0.10 * candidate.reuse
            - 0.10 * cost_penalty,
            6,
        )

    def _route_requirement(self, requirement: dict[str, Any], candidates: list[Candidate]) -> dict[str, Any]:
        requirement_id = requirement.get("requirement_id", "")
        if not SAFE_ID.fullmatch(requirement_id):
            raise HeartbeatError("requirement_id is invalid")
        tags = requirement.get("tags")
        if not isinstance(tags, list) or not tags or any(not isinstance(tag, str) or not tag for tag in tags):
            raise HeartbeatError("requirement tags are required")
        required_tags = set(tags)
        minimum_proof = requirement.get("minimum_proof", "TESTED")
        if minimum_proof not in PROOF_RANK:
            raise HeartbeatError("minimum_proof is invalid")
        maximum_authority = requirement.get("maximum_authority", "A1")
        if maximum_authority not in {"A0", "A1", "A2", "A3", "A4", "A5"}:
            raise HeartbeatError("maximum_authority is invalid")
        effectful_permit = bool(requirement.get("effectful_permit"))
        baseline_score = float(requirement.get("baseline_score", 0))
        baseline_safety = float(requirement.get("baseline_safety", 0))
        improvement_threshold = float(requirement.get("improvement_threshold", 0.05))
        if not 0 <= baseline_score <= 1 or not 0 <= baseline_safety <= 1:
            raise HeartbeatError("baseline values must be between zero and one")

        eligible: list[tuple[Candidate, float]] = []
        held: list[dict[str, Any]] = []
        for candidate in candidates:
            if not required_tags.intersection(candidate.tags):
                continue
            reasons: list[str] = []
            if not candidate.available:
                reasons.append("NOT_EXECUTABLE_IN_CURRENT_RUNTIME")
            if candidate.proof_rank < PROOF_RANK[minimum_proof]:
                reasons.append("PROOF_BELOW_REQUIREMENT")
            if int(candidate.authority_class[1:]) > int(maximum_authority[1:]):
                reasons.append("AUTHORITY_EXCEEDS_ENVELOPE")
            if candidate.external_effect and not effectful_permit:
                reasons.append("EFFECTFUL_PERMIT_REQUIRED")
            if candidate.cost > 0:
                reasons.append("NON_ZERO_COST")
            if candidate.safety < baseline_safety:
                reasons.append("SAFETY_REGRESSION")
            if reasons:
                held.append({
                    "source_id": candidate.source_id,
                    "capability_id": candidate.capability_id,
                    "reasons": reasons,
                })
                continue
            eligible.append((candidate, self._score(candidate, required_tags)))

        deduped: dict[str, tuple[Candidate, float]] = {}
        for candidate, score in eligible:
            prior = deduped.get(candidate.solution_fingerprint)
            if prior is None or (score, candidate.proof_rank, candidate.source_id) > (
                prior[1], prior[0].proof_rank, prior[0].source_id
            ):
                deduped[candidate.solution_fingerprint] = (candidate, score)
        ranked = sorted(
            deduped.values(),
            key=lambda item: (-item[1], -item[0].proof_rank, item[0].source_id, item[0].capability_id),
        )
        if not ranked:
            return {
                "requirement_id": requirement_id,
                "decision": "GAP_OR_HELD",
                "primary": None,
                "assistants": [],
                "held": held,
                "duplicate_candidates_removed": len(eligible),
                "effectful_path_count": 0,
            }

        primary, primary_score = ranked[0]
        assistants = []
        for candidate, score in ranked[1:]:
            if candidate.external_effect:
                continue
            if candidate.source_id == primary.source_id:
                continue
            assistants.append({**candidate.to_dict(), "score": score, "mode": "VERIFY_OR_ADVISE"})
            if len(assistants) == 3:
                break
        if primary_score >= baseline_score + improvement_threshold:
            decision = "ADOPT_SUPERIOR_VERIFIED_ROUTE"
        else:
            decision = "REUSE_CURRENT_VERIFIED_ROUTE"
        return {
            "requirement_id": requirement_id,
            "decision": decision,
            "primary": {**primary.to_dict(), "score": primary_score, "mode": "PRIMARY"},
            "assistants": assistants,
            "held": held,
            "duplicate_candidates_removed": len(eligible) - len(deduped),
            "effectful_path_count": 1 if primary.external_effect else 0,
        }

    def route_requirements(self, requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Route dynamic turn requirements without executing the selected route."""
        if not isinstance(requirements, list):
            raise HeartbeatError("requirements must be a list")
        _, candidates = self.collect()
        decisions = [self._route_requirement(requirement, candidates) for requirement in requirements]
        if any(item["effectful_path_count"] > 1 for item in decisions):
            raise HeartbeatError("multiple effectful paths are prohibited")
        return decisions

    def run(self, context_path: str | Path) -> dict[str, Any]:
        context = self._load_json(self._resolve_path(context_path))
        if context.get("schema") != "EVIDENCEOPS-CURRENT-WORKFLOW-1":
            raise HeartbeatError("unsupported current-workflow schema")
        requirements = context.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            raise HeartbeatError("current workflow requirements are required")
        heartbeats, candidates = self.collect()
        decisions = [self._route_requirement(requirement, candidates) for requirement in requirements]
        if any(item["effectful_path_count"] > 1 for item in decisions):
            raise HeartbeatError("multiple effectful paths are prohibited")
        body = {
            "schema": "EVIDENCEOPS-CAPABILITY-HEARTBEAT-REPORT-1",
            "workflow_id": context.get("workflow_id"),
            "workflow_version": context.get("workflow_version"),
            "repository_version": self._repository_version(),
            "runtime_state": "ON_DEMAND_GOVERNED",
            "source_count": len(heartbeats),
            "candidate_count": len(candidates),
            "heartbeats": heartbeats,
            "decisions": decisions,
            "single_effectful_path_enforced": True,
            "external_execution_attempted": False,
            "private_values_persisted": False,
            "truth_boundary": (
                "The heartbeat discovers and ranks current verified repository capabilities. "
                "It does not grant authority, execute external effects, or inject messages into an inactive chat."
            ),
        }
        generated_at = utcnow()
        result = {
            **body,
            "generated_at": generated_at,
            "report_sha256": sha256_value(body),
        }
        if self.bible_node_path and self.bible_node_path.is_file():
            from .bible_federation import BibleFederation

            federation = BibleFederation(self._load_json(self.bible_node_path))
            result["bible_node_heartbeat"] = federation.make_heartbeat(
                f"report:{result['report_sha256']}",
                emitted_at=generated_at,
                active_workflow_ids=[str(context.get("workflow_id"))],
            )
        return result
