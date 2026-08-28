#!/usr/bin/env python3
"""SOVARA Sovereign Intelligence Court v2.

Durable orchestration layer around the v1 OpenRouter code-review evaluator.

Design goals:
- Chat/MCP is an ingress terminal, not the system of record.
- External models are proposal-only intelligence suppliers.
- A provider refusal, timeout, outage or policy boundary is a lane event, not a
  mission rewrite or silent terminal failure.
- Mission state is checkpointed after every material transition.
- No model output can directly modify canonical source.
- The incumbent remains authoritative until a challenger passes independent
  validation, regression and zero-dilution gates.

This module intentionally does not attempt to bypass provider safeguards. It
makes provider-specific boundaries survivable through explicit degradation,
checkpointing and alternate lanes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable, Iterable, Mapping, Sequence

from sovara_openrouter_code_eval_v1 import (
    EvalError,
    evaluate_panel as _evaluate_external_panel,
)

SCHEMA = "SOVARA-SOVEREIGN-INTELLIGENCE-COURT-V2"
RECEIPT_SCHEMA = "SOVARA-SOVEREIGN-INTELLIGENCE-COURT-RECEIPT-V2"
MISSION_SCHEMA = "SOVARA-SOVEREIGN-INTELLIGENCE-COURT-MISSION-V2"


class MissionState(str, Enum):
    RECEIVED = "RECEIVED"
    HASHED = "HASHED"
    PRIVACY_PREFLIGHT = "PRIVACY_PREFLIGHT"
    PANEL_SELECTED = "PANEL_SELECTED"
    ROUND_1 = "ROUND_1"
    ROUND_1_CHECKPOINTED = "ROUND_1_CHECKPOINTED"
    DISAGREEMENTS_COMPILED = "DISAGREEMENTS_COMPILED"
    ROUND_2 = "ROUND_2"
    ROUND_2_CHECKPOINTED = "ROUND_2_CHECKPOINTED"
    AO5_COURT = "AO5_COURT"
    OMEGA_SCIENTIST = "OMEGA_SCIENTIST"
    CFBE = "CFBE"
    ZERO_DILUTION = "ZERO_DILUTION"
    RESULT_SEALED = "RESULT_SEALED"
    RETURNED_TO_USER = "RETURNED_TO_USER"
    CHECKPOINT_ONLY = "CHECKPOINT_ONLY"


class DegradationMode(str, Enum):
    FULL = "FULL"
    DEGRADED_EXTERNAL_PARTIAL = "DEGRADED_EXTERNAL_PARTIAL"
    DEGRADED_LOCAL_ONLY = "DEGRADED_LOCAL_ONLY"
    DEGRADED_DETERMINISTIC_ONLY = "DEGRADED_DETERMINISTIC_ONLY"
    CHECKPOINT_ONLY = "CHECKPOINT_ONLY"


class LaneStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PROVIDER_BOUNDARY = "PROVIDER_BOUNDARY"
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    SKIPPED = "SKIPPED"


@dataclass(slots=True)
class LaneReceipt:
    lane_id: str
    lane_type: str
    status: str
    provider: str | None = None
    model: str | None = None
    output_sha256: str | None = None
    error_class: str | None = None
    error_message: str | None = None
    proposal: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MissionSnapshot:
    schema: str
    mission_id: str
    created_at_utc: str
    updated_at_utc: str
    state: str
    source_sha256: str
    source_bytes: int
    language: str
    objective: str
    mode: str
    degradation_mode: str
    checkpoint_seq: int
    completed_states: list[str]
    boundary_events: list[dict[str, Any]]
    lane_receipts: list[dict[str, Any]]
    result_sha256: str | None = None


@dataclass(slots=True)
class CourtResult:
    schema: str
    mission_id: str
    source_sha256: str
    terminal_state: str
    degradation_mode: str
    panel_summary: dict[str, Any]
    consensus_findings: list[str]
    material_disagreements: list[str]
    novel_ideas: list[str]
    adversarial_findings: list[str]
    ao5_assessment: dict[str, Any]
    scientist_assessment: dict[str, Any]
    cfbe_ranking: list[dict[str, Any]]
    zero_dilution: dict[str, Any]
    recommendation: str
    unresolved_unknowns: list[str]
    receipts: list[dict[str, Any]]
    result_sha256: str | None = None


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _mission_id(source_sha256: str, objective: str, mode: str) -> str:
    stable = _sha256_text(f"{source_sha256}\n{objective.strip()}\n{mode.strip().upper()}")[:20]
    return f"SOV-EVAL-{stable.upper()}"


_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("OPENAI_KEY", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("OPENROUTER_KEY", re.compile(r"\bsk-or-v1-[A-Za-z0-9_-]{20,}\b")),
    ("AWS_ACCESS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("BEARER_TOKEN", re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._~+/=-]{20,}")),
)


def privacy_preflight(code: str) -> dict[str, Any]:
    findings: list[str] = []
    for name, pattern in _SECRET_PATTERNS:
        if pattern.search(code):
            findings.append(name)
    return {
        "status": "BLOCK_EXTERNAL_TRANSMISSION" if findings else "PASS",
        "secret_shape_findings": sorted(set(findings)),
        "external_transmission_allowed": not findings,
        "raw_secret_persisted": False,
    }


class MissionStore:
    """Filesystem-backed durable mission store with atomic checkpoint writes."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, mission_id: str) -> Path:
        return self.root / f"{mission_id}.json"

    def save(self, snapshot: MissionSnapshot) -> Path:
        path = self.path(snapshot.mission_id)
        payload = asdict(snapshot)
        data = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(self.root))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        finally:
            try:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
            except OSError:
                pass
        return path

    def load(self, mission_id: str) -> MissionSnapshot | None:
        path = self.path(mission_id)
        if not path.exists():
            return None
        return MissionSnapshot(**json.loads(path.read_text(encoding="utf-8")))


class SovereignIntelligenceCourt:
    def __init__(
        self,
        *,
        mission_store: MissionStore,
        external_panel: Callable[..., Mapping[str, Any]] = _evaluate_external_panel,
        local_reviewers: Sequence[Callable[[str, str, str], LaneReceipt]] = (),
        deterministic_reviewers: Sequence[Callable[[str, str, str], LaneReceipt]] = (),
    ) -> None:
        self.store = mission_store
        self.external_panel = external_panel
        self.local_reviewers = tuple(local_reviewers)
        self.deterministic_reviewers = tuple(deterministic_reviewers)

    def _checkpoint(self, snapshot: MissionSnapshot, state: MissionState) -> None:
        snapshot.state = state.value
        snapshot.updated_at_utc = _utcnow()
        snapshot.checkpoint_seq += 1
        if state.value not in snapshot.completed_states:
            snapshot.completed_states.append(state.value)
        self.store.save(snapshot)

    def _boundary(self, snapshot: MissionSnapshot, *, lane: str, kind: str, detail: str) -> None:
        snapshot.boundary_events.append({
            "recorded_at_utc": _utcnow(),
            "lane": lane,
            "kind": kind,
            "detail": detail[:1000],
        })
        self.store.save(snapshot)

    def _new_or_resume(self, code: str, language: str, objective: str, mode: str) -> MissionSnapshot:
        source_sha = _sha256_text(code)
        mission_id = _mission_id(source_sha, objective, mode)
        existing = self.store.load(mission_id)
        if existing is not None:
            if existing.source_sha256 != source_sha:
                raise RuntimeError("mission identity collision with different source")
            return existing
        now = _utcnow()
        snapshot = MissionSnapshot(
            schema=MISSION_SCHEMA,
            mission_id=mission_id,
            created_at_utc=now,
            updated_at_utc=now,
            state=MissionState.RECEIVED.value,
            source_sha256=source_sha,
            source_bytes=len(code.encode("utf-8")),
            language=language,
            objective=objective,
            mode=mode,
            degradation_mode=DegradationMode.FULL.value,
            checkpoint_seq=0,
            completed_states=[],
            boundary_events=[],
            lane_receipts=[],
        )
        self._checkpoint(snapshot, MissionState.RECEIVED)
        return snapshot

    def _run_local_and_deterministic(
        self,
        code: str,
        language: str,
        objective: str,
        snapshot: MissionSnapshot,
    ) -> list[LaneReceipt]:
        receipts: list[LaneReceipt] = []
        for index, reviewer in enumerate((*self.local_reviewers, *self.deterministic_reviewers), start=1):
            lane_id = f"sovereign-{index}"
            try:
                receipt = reviewer(code, language, objective)
            except Exception as exc:  # local lane is isolated; mission continues
                receipt = LaneReceipt(
                    lane_id=lane_id,
                    lane_type="SOVEREIGN",
                    status=LaneStatus.FAILED.value,
                    error_class=type(exc).__name__,
                    error_message=str(exc)[:1000],
                )
                self._boundary(snapshot, lane=lane_id, kind="LOCAL_LANE_FAILURE", detail=str(exc))
            receipts.append(receipt)
        return receipts

    def _external_round(
        self,
        code: str,
        language: str,
        objective: str,
        snapshot: MissionSnapshot,
        *,
        mode: str,
        max_models: int,
    ) -> tuple[list[LaneReceipt], dict[str, Any] | None]:
        if not os.environ.get("OPENROUTER_API_KEY"):
            self._boundary(
                snapshot,
                lane="openrouter",
                kind="PROVIDER_UNAVAILABLE",
                detail="OPENROUTER_API_KEY not bound in runtime environment",
            )
            return [], None
        try:
            envelope = self.external_panel(
                code,
                api_key=os.environ["OPENROUTER_API_KEY"],
                language=language,
                objective=objective,
                max_models=max_models,
            )
        except Exception as exc:
            kind = "PROVIDER_BOUNDARY" if isinstance(exc, EvalError) else "PROVIDER_FAILURE"
            self._boundary(snapshot, lane="openrouter", kind=kind, detail=str(exc))
            return [], None

        receipts: list[LaneReceipt] = []
        for index, item in enumerate(envelope.get("reviews", []) if isinstance(envelope, Mapping) else [], start=1):
            if not isinstance(item, Mapping):
                continue
            provider_receipt = item.get("receipt") if isinstance(item.get("receipt"), Mapping) else {}
            output = item.get("output")
            status = str(provider_receipt.get("status", "FAILED"))
            ok = status != "FAILED" and isinstance(output, str) and bool(output.strip())
            receipts.append(LaneReceipt(
                lane_id=f"external-{index}",
                lane_type="EXTERNAL_MODEL",
                status=LaneStatus.SUCCESS.value if ok else LaneStatus.FAILED.value,
                provider=(str(provider_receipt.get("resolved_model", "")).split("/", 1)[0] or None),
                model=provider_receipt.get("resolved_model"),
                output_sha256=provider_receipt.get("output_sha256"),
                error_class=provider_receipt.get("error_class"),
                error_message=provider_receipt.get("error_message"),
                proposal=output if ok else None,
                metadata={"provider_receipt": dict(provider_receipt)},
            ))
        return receipts, dict(envelope)

    @staticmethod
    def _classify_degradation(external: Sequence[LaneReceipt], sovereign: Sequence[LaneReceipt]) -> DegradationMode:
        external_success = sum(r.status == LaneStatus.SUCCESS.value for r in external)
        sovereign_success = sum(r.status == LaneStatus.SUCCESS.value for r in sovereign)
        if external_success >= 2 and sovereign_success >= 1:
            return DegradationMode.FULL
        if external_success >= 1:
            return DegradationMode.DEGRADED_EXTERNAL_PARTIAL
        if sovereign_success >= 1:
            return DegradationMode.DEGRADED_LOCAL_ONLY
        return DegradationMode.CHECKPOINT_ONLY

    @staticmethod
    def _extract_proposals(receipts: Sequence[LaneReceipt]) -> list[str]:
        return [str(r.proposal) for r in receipts if r.status == LaneStatus.SUCCESS.value and r.proposal]

    @staticmethod
    def _simple_synthesis(proposals: Sequence[str]) -> tuple[list[str], list[str], list[str]]:
        """Conservative deterministic synthesis fallback.

        This intentionally avoids pretending to semantically adjudicate prose.
        It preserves distinct proposal digests and exposes disagreement for a
        later model/ΑΩ5 synthesis lane.
        """
        if not proposals:
            return [], [], []
        digests = [_sha256_text(p)[:12] for p in proposals]
        consensus = [f"{len(proposals)} independent proposal payload(s) received and preserved by hash."]
        disagreements = [] if len(set(digests)) <= 1 else [
            f"Proposal payloads are materially non-identical ({len(set(digests))} unique content hashes); semantic adjudication required."
        ]
        novel = [f"proposal:{digest}" for digest in digests]
        return consensus, disagreements, novel

    def evaluate(
        self,
        code: str,
        *,
        language: str = "text",
        objective: str = "Find defects and propose materially better architectures without changing intended behavior.",
        mode: str = "AUTO",
        max_models: int = 4,
    ) -> CourtResult:
        snapshot = self._new_or_resume(code, language, objective, mode)
        self._checkpoint(snapshot, MissionState.HASHED)

        preflight = privacy_preflight(code)
        self._checkpoint(snapshot, MissionState.PRIVACY_PREFLIGHT)

        external: list[LaneReceipt] = []
        external_envelope: dict[str, Any] | None = None
        self._checkpoint(snapshot, MissionState.PANEL_SELECTED)

        if preflight["external_transmission_allowed"]:
            self._checkpoint(snapshot, MissionState.ROUND_1)
            external, external_envelope = self._external_round(
                code,
                language,
                objective,
                snapshot,
                mode=mode,
                max_models=max_models,
            )
        else:
            self._boundary(
                snapshot,
                lane="external-panel",
                kind="PRIVACY_BOUNDARY",
                detail=f"secret-shaped source blocked from external transmission: {preflight['secret_shape_findings']}",
            )
        self._checkpoint(snapshot, MissionState.ROUND_1_CHECKPOINTED)

        sovereign = self._run_local_and_deterministic(code, language, objective, snapshot)
        all_receipts = [*external, *sovereign]
        snapshot.lane_receipts = [asdict(r) for r in all_receipts]
        degradation = self._classify_degradation(external, sovereign)
        snapshot.degradation_mode = degradation.value
        self.store.save(snapshot)

        proposals = self._extract_proposals(all_receipts)
        consensus, disagreements, novel = self._simple_synthesis(proposals)
        self._checkpoint(snapshot, MissionState.DISAGREEMENTS_COMPILED)

        # Round 2 is a durable state even when the dedicated cross-examination
        # provider lane has not yet been attached. This prevents a caller from
        # confusing a missing optional lane with completed adversarial proof.
        self._checkpoint(snapshot, MissionState.ROUND_2)
        adversarial = []
        if disagreements:
            adversarial.append("Material proposal disagreement remains open; a semantic cross-examination lane is required before promotion.")
        self._checkpoint(snapshot, MissionState.ROUND_2_CHECKPOINTED)

        self._checkpoint(snapshot, MissionState.AO5_COURT)
        ao5 = {
            "status": "BOUNDED_LOCAL_CONTRACT",
            "external_outputs_proposal_only": True,
            "provider_authority_inherited": False,
            "adversarial_semantic_round_complete": not bool(disagreements),
            "promotion_allowed": False,
        }

        self._checkpoint(snapshot, MissionState.OMEGA_SCIENTIST)
        scientist = {
            "status": "CHALLENGER_FORMATION_REQUIRED" if proposals else "NO_CHALLENGER",
            "falsification_required": True,
            "measured_gain_required": True,
            "rollback_required": True,
        }

        self._checkpoint(snapshot, MissionState.CFBE)
        cfbe = [
            {
                "candidate_id": f"proposal-{index}",
                "state": "PROPOSAL_ONLY",
                "content_sha256": _sha256_text(proposal),
                "score": None,
                "reason": "No empirical benchmark has been run yet.",
            }
            for index, proposal in enumerate(proposals, start=1)
        ]

        self._checkpoint(snapshot, MissionState.ZERO_DILUTION)
        zero_dilution = {
            "status": "NOT_YET_PROVEN" if proposals else "NO_CHANGE_PROPOSED",
            "canonical_source_modified": False,
            "incumbent_preserved": True,
            "regression_required_before_promotion": True,
            "promotion_allowed": False,
        }

        terminal = (
            "CHECKPOINT_ONLY_NO_EXECUTABLE_REVIEW_LANE"
            if degradation == DegradationMode.CHECKPOINT_ONLY
            else "PROPOSALS_RECEIVED_REQUIRES_INDEPENDENT_VALIDATION"
        )
        recommendation = (
            "Preserve incumbent source. Attach semantic round-2/AΩ5 adjudication and empirical regression before any candidate promotion."
            if proposals
            else "Preserve mission checkpoint and resume when an authorized review lane becomes available."
        )

        result = CourtResult(
            schema=RECEIPT_SCHEMA,
            mission_id=snapshot.mission_id,
            source_sha256=snapshot.source_sha256,
            terminal_state=terminal,
            degradation_mode=degradation.value,
            panel_summary={
                "external_lanes": len(external),
                "external_success": sum(r.status == LaneStatus.SUCCESS.value for r in external),
                "sovereign_lanes": len(sovereign),
                "sovereign_success": sum(r.status == LaneStatus.SUCCESS.value for r in sovereign),
                "privacy_preflight": preflight,
                "external_envelope_sha256": (
                    _sha256_text(_canonical_json(external_envelope)) if external_envelope is not None else None
                ),
            },
            consensus_findings=consensus,
            material_disagreements=disagreements,
            novel_ideas=novel,
            adversarial_findings=adversarial,
            ao5_assessment=ao5,
            scientist_assessment=scientist,
            cfbe_ranking=cfbe,
            zero_dilution=zero_dilution,
            recommendation=recommendation,
            unresolved_unknowns=[
                "Round-2 semantic cross-examination is not yet provider-bound." if disagreements else "",
                "Empirical challenger benchmark has not yet run." if proposals else "",
            ],
            receipts=[asdict(r) for r in all_receipts],
        )
        result.unresolved_unknowns = [item for item in result.unresolved_unknowns if item]
        result.result_sha256 = _sha256_text(_canonical_json({k: v for k, v in asdict(result).items() if k != "result_sha256"}))

        snapshot.result_sha256 = result.result_sha256
        self._checkpoint(snapshot, MissionState.RESULT_SEALED)
        return result


def _main() -> int:
    parser = argparse.ArgumentParser(description="SOVARA Sovereign Intelligence Court v2")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--language", default="text")
    parser.add_argument("--objective", default="Find defects and propose materially better architectures without changing intended behavior.")
    parser.add_argument("--mode", default="AUTO")
    parser.add_argument("--max-models", type=int, default=4)
    parser.add_argument("--state-dir", type=Path, default=Path(".sovara/sovereign-intelligence-court"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    code = args.file.read_text(encoding="utf-8") if args.file else __import__("sys").stdin.read()
    court = SovereignIntelligenceCourt(mission_store=MissionStore(args.state_dir))
    result = court.evaluate(
        code,
        language=args.language,
        objective=args.objective,
        mode=args.mode,
        max_models=args.max_models,
    )
    text = json.dumps(asdict(result), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
