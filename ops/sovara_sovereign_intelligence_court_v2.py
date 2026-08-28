#!/usr/bin/env python3
"""SOVARA Sovereign Intelligence Court v2.

Durable, incumbent-preserving orchestration for chat-native external code review.

The chat client is an ingress terminal, not the system of record. External model
outputs are proposal-only intelligence. Provider refusal, timeout, outage or
policy boundaries are recorded as lane events; they never grant permission to
bypass provider safeguards and never silently redefine the mission.
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
import sys
import tempfile
from typing import Any, Callable, Mapping, Protocol, Sequence

OPS_DIR = Path(__file__).resolve().parent
REPO_ROOT = OPS_DIR.parent
for _path in (OPS_DIR, REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from sovara_openrouter_code_eval_v1 import (  # noqa: E402
    EvalError,
    evaluate_panel,
    fetch_model_catalog,
    resolve_panel,
)

SCHEMA = "SOVARA-SOVEREIGN-INTELLIGENCE-COURT-V2"
MISSION_SCHEMA = "SOVARA-SOVEREIGN-INTELLIGENCE-COURT-MISSION-V2"
RECEIPT_SCHEMA = "SOVARA-SOVEREIGN-INTELLIGENCE-COURT-RECEIPT-V2"
DEFAULT_OBJECTIVE = (
    "Find defects, hidden failure modes and materially better architectures "
    "without changing intended behavior."
)
SUPPORTED_MODES = {
    "AUTO",
    "CREATIVE",
    "RED_TEAM",
    "ARCHITECTURE",
    "ZERO_DILUTION",
    "PERFORMANCE",
    "SECURITY",
    "10X",
}


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
    proposal: str | None = None
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
    max_models: int
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
    cfbe_assessment: dict[str, Any]
    zero_dilution: dict[str, Any]
    recommendation: str
    unresolved_unknowns: list[str]
    receipts: list[dict[str, Any]]
    result_sha256: str | None = None


class Store(Protocol):
    def load_snapshot(self, mission_id: str) -> MissionSnapshot | None: ...
    def save_snapshot(self, snapshot: MissionSnapshot) -> None: ...
    def load_result(self, mission_id: str) -> CourtResult | None: ...
    def save_result(self, result: CourtResult) -> None: ...


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _mission_id(source_sha256: str, language: str, objective: str, mode: str, max_models: int) -> str:
    material = f"{SCHEMA}\n{source_sha256}\n{language}\n{objective.strip()}\n{mode}\n{max_models}"
    return f"SOV-EVAL-{_sha256_text(material)[:24].upper()}"


class FileMissionStore:
    """Atomic filesystem store for local/CI use.

    Production must place this directory on a durable volume or replace this
    implementation with a provider-backed Store. Container-local ephemeral disk
    alone is not sufficient evidence of durable recovery.
    """

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _snapshot_path(self, mission_id: str) -> Path:
        return self.root / mission_id / "snapshot.json"

    def _result_path(self, mission_id: str) -> Path:
        return self.root / mission_id / "sealed-result.json"

    def load_snapshot(self, mission_id: str) -> MissionSnapshot | None:
        path = self._snapshot_path(mission_id)
        if not path.exists():
            return None
        return MissionSnapshot(**json.loads(path.read_text(encoding="utf-8")))

    def save_snapshot(self, snapshot: MissionSnapshot) -> None:
        _atomic_write(self._snapshot_path(snapshot.mission_id), asdict(snapshot))

    def load_result(self, mission_id: str) -> CourtResult | None:
        path = self._result_path(mission_id)
        if not path.exists():
            return None
        result = CourtResult(**json.loads(path.read_text(encoding="utf-8")))
        expected = result.result_sha256
        material = asdict(result)
        material["result_sha256"] = None
        actual = _sha256_text(_canonical_json(material))
        if not expected or expected != actual:
            raise RuntimeError("SEALED_RESULT_HASH_MISMATCH")
        return result

    def save_result(self, result: CourtResult) -> None:
        _atomic_write(self._result_path(result.mission_id), asdict(result))


_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("OPENAI_KEY", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("OPENROUTER_KEY", re.compile(r"\bsk-or-v1-[A-Za-z0-9_-]{20,}\b")),
    ("AWS_ACCESS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("BEARER_TOKEN", re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._~+/=-]{20,}")),
)


def privacy_preflight(code: str) -> dict[str, Any]:
    findings = sorted({name for name, pattern in _SECRET_PATTERNS if pattern.search(code)})
    return {
        "status": "BLOCK_EXTERNAL_TRANSMISSION" if findings else "PASS",
        "secret_shape_findings": findings,
        "external_transmission_allowed": not findings,
        "raw_secret_persisted": False,
    }


def deterministic_source_reviewer(code: str, language: str, objective: str) -> LaneReceipt:
    """Non-executing static fallback that remains useful without any model API."""
    lines = code.splitlines()
    patterns = {
        "dynamic_execution": r"\b(eval|exec)\s*\(",
        "shell_true": r"shell\s*=\s*True",
        "bare_except": r"(?m)^\s*except\s*:\s*$",
        "todo_markers": r"(?i)\b(TODO|FIXME|HACK)\b",
        "broad_exception": r"except\s+(Exception|BaseException)\b",
    }
    hits = {name: len(re.findall(pattern, code)) for name, pattern in patterns.items()}
    hits = {name: count for name, count in hits.items() if count}
    proposal_obj = {
        "summary": "Deterministic non-executing source scan completed.",
        "strengths": ["Exact source preserved; no code execution performed."],
        "defects": [f"pattern:{name}:count={count}" for name, count in sorted(hits.items())],
        "hidden_risks": [],
        "unconventional_ideas": [],
        "redesign_options": [],
        "tests_to_add": ["Run language-native tests/static analysis in an isolated challenger sandbox before promotion."],
        "confidence": "BOUNDED_STATIC_ONLY",
        "assumptions": [f"declared_language={language}", f"line_count={len(lines)}", f"objective={objective}"],
    }
    proposal = _canonical_json(proposal_obj)
    return LaneReceipt(
        lane_id="deterministic-static-1",
        lane_type="DETERMINISTIC_STATIC",
        status=LaneStatus.SUCCESS.value,
        provider="SOVARA_LOCAL",
        model=None,
        output_sha256=_sha256_text(proposal),
        proposal=proposal,
        metadata={"code_executed": False, "static_pattern_count": len(hits)},
    )


def run_openrouter_panel(
    code: str,
    *,
    api_key: str,
    language: str,
    objective: str,
    max_models: int,
    temperature: float = 0.85,
    max_tokens: int = 2500,
) -> dict[str, Any]:
    catalog = fetch_model_catalog(api_key=api_key)
    models = resolve_panel(catalog, max_models=max(1, min(max_models, 8)))
    return evaluate_panel(
        code,
        api_key=api_key,
        models=models,
        language=language,
        objective=objective,
        temperature=max(0.0, min(temperature, 1.5)),
        max_tokens=max(256, min(max_tokens, 8000)),
    )


def _proposal_json(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.I)
        candidate = re.sub(r"\s*```$", "", candidate)
    try:
        value = json.loads(candidate)
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _normalize_finding(value: str) -> str:
    return " ".join(value.strip().lower().split())


def synthesize_proposals(proposals: Sequence[str]) -> tuple[list[str], list[str], list[str]]:
    parsed = [_proposal_json(p) for p in proposals]
    parsed = [p for p in parsed if p is not None]
    counters: dict[str, tuple[str, int]] = {}
    novel: list[str] = []
    summaries: list[str] = []
    for review in parsed:
        if isinstance(review.get("summary"), str):
            summaries.append(review["summary"].strip())
        for key in ("defects", "hidden_risks"):
            values = review.get(key, [])
            if isinstance(values, list):
                for item in values:
                    if isinstance(item, str) and item.strip():
                        norm = _normalize_finding(item)
                        original, count = counters.get(norm, (item.strip(), 0))
                        counters[norm] = (original, count + 1)
        for key in ("unconventional_ideas", "redesign_options"):
            values = review.get(key, [])
            if isinstance(values, list):
                novel.extend(item.strip() for item in values if isinstance(item, str) and item.strip())
    consensus = [original for original, count in counters.values() if count >= 2]
    disagreements: list[str] = []
    unique_summaries = {_normalize_finding(s) for s in summaries if s}
    if len(unique_summaries) > 1:
        disagreements.append(f"Independent reviewers produced {len(unique_summaries)} materially distinct summaries.")
    if len({_sha256_text(p) for p in proposals}) > 1:
        disagreements.append("Proposal payloads are non-identical; cross-examination/adjudication is required before promotion.")
    return consensus, disagreements, list(dict.fromkeys(novel))[:30]


def build_cross_exam_payload(code: str, proposals: Sequence[str]) -> str:
    blocks = []
    for index, proposal in enumerate(proposals, start=1):
        blocks.append(f"<ANONYMIZED_PROPOSAL_{index}>\n{proposal}\n</ANONYMIZED_PROPOSAL_{index}>")
    return (
        "<ORIGINAL_UNTRUSTED_CODE>\n"
        + code
        + "\n</ORIGINAL_UNTRUSTED_CODE>\n\n"
        + "\n\n".join(blocks)
    )


def bounded_ao5_binding(*, disagreements: Sequence[str], round2_success: int) -> dict[str, Any]:
    """Bind the repo-native AO5 profile without inflating it to signed SLOS authority."""
    try:
        from ao_harmonic_v3.jarvis_ao5 import JarvisAO5Engine

        contract = JarvisAO5Engine.contract()
        return {
            "status": "BOUNDED_REPO_NATIVE_AO5_PROFILE_BOUND",
            "engine_id": contract.get("engine_id"),
            "engine_version": contract.get("version"),
            "authority_ceiling": contract.get("authority_ceiling"),
            "kernel_invariant_count": len(contract.get("kernel_invariants", [])),
            "external_effect_default": contract.get("external_effect_default"),
            "open_disagreement_count": len(disagreements),
            "round2_success": round2_success,
            "signed_slos_canonical_authority_claimed": False,
            "promotion_allowed": False,
        }
    except Exception as exc:
        return {
            "status": "AO5_PROFILE_BINDING_UNAVAILABLE",
            "error_class": type(exc).__name__,
            "open_disagreement_count": len(disagreements),
            "signed_slos_canonical_authority_claimed": False,
            "promotion_allowed": False,
        }


class SovereignIntelligenceCourt:
    def __init__(
        self,
        *,
        store: Store,
        external_runner: Callable[..., dict[str, Any]] = run_openrouter_panel,
        sovereign_reviewers: Sequence[Callable[[str, str, str], LaneReceipt]] = (deterministic_source_reviewer,),
    ) -> None:
        self.store = store
        self.external_runner = external_runner
        self.sovereign_reviewers = tuple(sovereign_reviewers)

    def _checkpoint(self, snapshot: MissionSnapshot, state: MissionState) -> None:
        snapshot.state = state.value
        snapshot.updated_at_utc = _utcnow()
        snapshot.checkpoint_seq += 1
        if state.value not in snapshot.completed_states:
            snapshot.completed_states.append(state.value)
        self.store.save_snapshot(snapshot)

    def _boundary(self, snapshot: MissionSnapshot, *, lane: str, kind: str, detail: str) -> None:
        snapshot.boundary_events.append(
            {"recorded_at_utc": _utcnow(), "lane": lane, "kind": kind, "detail": detail[:1000]}
        )
        self.store.save_snapshot(snapshot)

    def _new_or_resume(
        self, code: str, language: str, objective: str, mode: str, max_models: int
    ) -> tuple[MissionSnapshot, CourtResult | None]:
        source_sha = _sha256_text(code)
        mission_id = _mission_id(source_sha, language, objective, mode, max_models)
        existing = self.store.load_snapshot(mission_id)
        if existing is not None:
            if existing.source_sha256 != source_sha:
                raise RuntimeError("MISSION_ID_COLLISION")
            sealed = self.store.load_result(mission_id)
            if sealed is not None and existing.result_sha256 == sealed.result_sha256:
                return existing, sealed
            return existing, None
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
            max_models=max_models,
            degradation_mode=DegradationMode.FULL.value,
            checkpoint_seq=0,
            completed_states=[],
            boundary_events=[],
            lane_receipts=[],
        )
        self._checkpoint(snapshot, MissionState.RECEIVED)
        return snapshot, None

    def _run_external(
        self,
        payload: str,
        *,
        language: str,
        objective: str,
        max_models: int,
        snapshot: MissionSnapshot,
        lane_prefix: str,
    ) -> tuple[list[LaneReceipt], dict[str, Any] | None]:
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            self._boundary(snapshot, lane=lane_prefix, kind="PROVIDER_AUTHORITY_MISSING", detail="OpenRouter runtime credential reference not bound")
            return [], None
        try:
            envelope = self.external_runner(
                payload,
                api_key=api_key,
                language=language,
                objective=objective,
                max_models=max_models,
            )
        except Exception as exc:
            kind = "PROVIDER_POLICY_OR_TRANSPORT_BOUNDARY" if isinstance(exc, EvalError) else "PROVIDER_FAILURE"
            self._boundary(snapshot, lane=lane_prefix, kind=kind, detail=str(exc))
            return [], None
        receipts: list[LaneReceipt] = []
        reviews = envelope.get("reviews", []) if isinstance(envelope, Mapping) else []
        for index, item in enumerate(reviews, start=1):
            if not isinstance(item, Mapping):
                continue
            provider_receipt = item.get("receipt") if isinstance(item.get("receipt"), Mapping) else {}
            proposal = item.get("proposal")
            status = str(provider_receipt.get("status", "FAILED"))
            ok = status != "FAILED" and isinstance(proposal, str) and bool(proposal.strip())
            resolved_model = provider_receipt.get("resolved_model")
            provider = None
            if isinstance(resolved_model, str) and resolved_model:
                provider = resolved_model.split("/", 1)[0]
            receipts.append(
                LaneReceipt(
                    lane_id=f"{lane_prefix}-{index}",
                    lane_type="EXTERNAL_MODEL" if lane_prefix == "round1" else "EXTERNAL_CROSS_EXAM",
                    status=LaneStatus.SUCCESS.value if ok else LaneStatus.FAILED.value,
                    provider=provider,
                    model=resolved_model if isinstance(resolved_model, str) else None,
                    output_sha256=provider_receipt.get("output_sha256"),
                    error_class=provider_receipt.get("error_class"),
                    error_message=provider_receipt.get("error_message"),
                    proposal=proposal if ok else None,
                    metadata={"provider_receipt": dict(provider_receipt)},
                )
            )
        return receipts, dict(envelope)

    def _run_sovereign(self, code: str, language: str, objective: str, snapshot: MissionSnapshot) -> list[LaneReceipt]:
        receipts: list[LaneReceipt] = []
        for index, reviewer in enumerate(self.sovereign_reviewers, start=1):
            try:
                receipt = reviewer(code, language, objective)
            except Exception as exc:
                self._boundary(snapshot, lane=f"sovereign-{index}", kind="SOVEREIGN_LANE_FAILURE", detail=str(exc))
                receipt = LaneReceipt(
                    lane_id=f"sovereign-{index}",
                    lane_type="SOVEREIGN",
                    status=LaneStatus.FAILED.value,
                    error_class=type(exc).__name__,
                    error_message=str(exc)[:1000],
                )
            receipts.append(receipt)
        return receipts

    @staticmethod
    def _degradation(external: Sequence[LaneReceipt], sovereign: Sequence[LaneReceipt]) -> DegradationMode:
        external_success = sum(r.status == LaneStatus.SUCCESS.value for r in external)
        deterministic_success = sum(
            r.status == LaneStatus.SUCCESS.value and r.lane_type == "DETERMINISTIC_STATIC" for r in sovereign
        )
        local_model_success = sum(
            r.status == LaneStatus.SUCCESS.value and r.lane_type == "LOCAL_MODEL" for r in sovereign
        )
        if external_success >= 2 and (deterministic_success + local_model_success) >= 1:
            return DegradationMode.FULL
        if external_success >= 1:
            return DegradationMode.DEGRADED_EXTERNAL_PARTIAL
        if local_model_success >= 1:
            return DegradationMode.DEGRADED_LOCAL_ONLY
        if deterministic_success >= 1:
            return DegradationMode.DEGRADED_DETERMINISTIC_ONLY
        return DegradationMode.CHECKPOINT_ONLY

    def evaluate(
        self,
        code: str,
        *,
        language: str = "text",
        objective: str = DEFAULT_OBJECTIVE,
        mode: str = "AUTO",
        max_models: int = 4,
    ) -> CourtResult:
        if not isinstance(code, str) or not code.strip():
            raise ValueError("CODE_REQUIRED")
        mode = mode.strip().upper()
        if mode not in SUPPORTED_MODES:
            raise ValueError(f"UNSUPPORTED_MODE:{mode}")
        max_models = max(1, min(int(max_models), 8))
        snapshot, sealed = self._new_or_resume(code, language, objective, mode, max_models)
        if sealed is not None:
            return sealed

        self._checkpoint(snapshot, MissionState.HASHED)
        preflight = privacy_preflight(code)
        self._checkpoint(snapshot, MissionState.PRIVACY_PREFLIGHT)
        self._checkpoint(snapshot, MissionState.PANEL_SELECTED)

        external_round1: list[LaneReceipt] = []
        round1_envelope: dict[str, Any] | None = None
        self._checkpoint(snapshot, MissionState.ROUND_1)
        if preflight["external_transmission_allowed"]:
            external_round1, round1_envelope = self._run_external(
                code,
                language=language,
                objective=f"{objective} Review mode: {mode}. Perform a blind independent review.",
                max_models=max_models,
                snapshot=snapshot,
                lane_prefix="round1",
            )
        else:
            self._boundary(snapshot, lane="round1", kind="PRIVACY_BOUNDARY", detail=f"External transmission blocked by secret-shaped input: {preflight['secret_shape_findings']}")
        self._checkpoint(snapshot, MissionState.ROUND_1_CHECKPOINTED)

        sovereign = self._run_sovereign(code, language, objective, snapshot)
        round1_all = [*external_round1, *sovereign]
        proposals = [r.proposal for r in round1_all if r.status == LaneStatus.SUCCESS.value and r.proposal]
        consensus, disagreements, novel = synthesize_proposals(proposals)
        self._checkpoint(snapshot, MissionState.DISAGREEMENTS_COMPILED)

        external_round2: list[LaneReceipt] = []
        round2_envelope: dict[str, Any] | None = None
        self._checkpoint(snapshot, MissionState.ROUND_2)
        if preflight["external_transmission_allowed"] and len(proposals) >= 2 and disagreements:
            cross_payload = build_cross_exam_payload(code, proposals)
            external_round2, round2_envelope = self._run_external(
                cross_payload,
                language="text",
                objective=(
                    "Cross-examine the anonymized competing proposals. Identify which claims survive, "
                    "which fail, hidden shared assumptions, and a stronger hybrid if justified. "
                    "Do not average the proposals and do not claim code execution."
                ),
                max_models=min(max_models, 4),
                snapshot=snapshot,
                lane_prefix="round2",
            )
        self._checkpoint(snapshot, MissionState.ROUND_2_CHECKPOINTED)

        all_receipts = [*round1_all, *external_round2]
        snapshot.lane_receipts = [asdict(r) for r in all_receipts]
        degradation = self._degradation(external_round1, sovereign)
        snapshot.degradation_mode = degradation.value
        self.store.save_snapshot(snapshot)

        adversarial_findings: list[str] = []
        round2_proposals = [r.proposal for r in external_round2 if r.status == LaneStatus.SUCCESS.value and r.proposal]
        for proposal in round2_proposals:
            parsed = _proposal_json(proposal)
            if parsed and isinstance(parsed.get("summary"), str):
                adversarial_findings.append(parsed["summary"].strip())
        if disagreements and not round2_proposals:
            adversarial_findings.append("Material disagreement remains open because no round-2 semantic cross-examination response was proven.")

        self._checkpoint(snapshot, MissionState.AO5_COURT)
        ao5 = bounded_ao5_binding(disagreements=disagreements, round2_success=len(round2_proposals))

        self._checkpoint(snapshot, MissionState.OMEGA_SCIENTIST)
        candidate_hashes = [_sha256_text(p) for p in proposals]
        scientist = {
            "status": "CHALLENGER_EXPERIMENT_REQUIRED" if candidate_hashes else "NO_MODEL_CHALLENGER",
            "candidate_hashes": candidate_hashes,
            "hypothesis_required": True,
            "falsification_required": True,
            "measured_gain_required": True,
            "rollback_required": True,
            "self_promotion_allowed": False,
        }

        self._checkpoint(snapshot, MissionState.CFBE)
        cfbe = {
            "status": "UNSCORED_EVIDENCE_REQUIRED" if candidate_hashes else "NO_CANDIDATES",
            "candidate_count": len(candidate_hashes),
            "scores": None,
            "reason": "No empirical challenger benchmark/regression court has run in this review transaction.",
            "superiority_claimed": False,
        }

        self._checkpoint(snapshot, MissionState.ZERO_DILUTION)
        zero_dilution = {
            "review_transaction_preserved_incumbent": True,
            "canonical_source_modified": False,
            "candidate_semantic_parity_proven": False if candidate_hashes else None,
            "candidate_regression_proven": False if candidate_hashes else None,
            "promotion_allowed": False,
            "status": "CANDIDATE_TEST_REQUIRED" if candidate_hashes else "NO_CHANGE_PROPOSED",
        }

        if degradation == DegradationMode.CHECKPOINT_ONLY:
            terminal = "CHECKPOINT_ONLY_NO_SAFE_REVIEW_LANE"
            recommendation = "Preserve the checkpoint and resume when an authorized review lane becomes available."
            self._checkpoint(snapshot, MissionState.CHECKPOINT_ONLY)
        else:
            terminal = "ADJUDICATED_REVIEW_RECEIPT_PROPOSALS_ONLY"
            recommendation = (
                "Preserve incumbent source. Form a challenger only from evidence-backed proposals, then run "
                "isolated tests, empirical CFBE comparison and zero-dilution regression before any promotion."
            )

        round1_external_success = sum(
            r.status == LaneStatus.SUCCESS.value for r in external_round1
        )
        panel_summary = {
            "round1_external_lanes": len(external_round1),
            "round1_external_success": round1_external_success,
            "round2_external_lanes": len(external_round2),
            "round2_external_success": sum(r.status == LaneStatus.SUCCESS.value for r in external_round2),
            "sovereign_lanes": len(sovereign),
            "sovereign_success": sum(r.status == LaneStatus.SUCCESS.value for r in sovereign),
            "privacy_preflight": preflight,
            "round1_envelope_sha256": _sha256_text(_canonical_json(round1_envelope)) if round1_envelope else None,
            "round2_envelope_sha256": _sha256_text(_canonical_json(round2_envelope)) if round2_envelope else None,
            "provider_connectivity_claimed": round1_external_success > 0,
        }

        unresolved = []
        if disagreements and not round2_proposals:
            unresolved.append("ROUND2_SEMANTIC_CROSS_EXAM_NOT_PROVEN")
        if candidate_hashes:
            unresolved.extend(["EMPIRICAL_CHALLENGER_TESTS_NOT_RUN", "CANDIDATE_ZERO_DILUTION_NOT_PROVEN"])
        if round1_external_success == 0:
            unresolved.append("EXTERNAL_PROVIDER_REVIEW_NOT_PROVEN_FOR_THIS_MISSION")

        result = CourtResult(
            schema=RECEIPT_SCHEMA,
            mission_id=snapshot.mission_id,
            source_sha256=snapshot.source_sha256,
            terminal_state=terminal,
            degradation_mode=degradation.value,
            panel_summary=panel_summary,
            consensus_findings=consensus,
            material_disagreements=disagreements,
            novel_ideas=novel,
            adversarial_findings=adversarial_findings,
            ao5_assessment=ao5,
            scientist_assessment=scientist,
            cfbe_assessment=cfbe,
            zero_dilution=zero_dilution,
            recommendation=recommendation,
            unresolved_unknowns=unresolved,
            receipts=[asdict(r) for r in all_receipts],
        )
        material = asdict(result)
        material["result_sha256"] = None
        result.result_sha256 = _sha256_text(_canonical_json(material))
        self.store.save_result(result)
        snapshot.result_sha256 = result.result_sha256
        self._checkpoint(snapshot, MissionState.RESULT_SEALED)
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SOVARA Sovereign Intelligence Court v2")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--language", default="text")
    parser.add_argument("--objective", default=DEFAULT_OBJECTIVE)
    parser.add_argument("--mode", default="AUTO", choices=sorted(SUPPORTED_MODES))
    parser.add_argument("--max-models", type=int, default=4)
    parser.add_argument("--state-dir", type=Path, default=Path(os.environ.get("SOVARA_STATE_DIR", ".sovara/sovereign-intelligence-court")))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    code = args.file.read_text(encoding="utf-8") if args.file else sys.stdin.read()
    court = SovereignIntelligenceCourt(store=FileMissionStore(args.state_dir))
    result = court.evaluate(code, language=args.language, objective=args.objective, mode=args.mode, max_models=args.max_models)
    text = json.dumps(asdict(result), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
