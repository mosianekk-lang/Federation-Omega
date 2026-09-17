#!/usr/bin/env python3
"""BCO-Prime Chat Forensics v2.

This module is a local, fail-closed composition layer.  It preserves the v1
and canonical 100-capability interfaces, adds the v1.1 truth repair, exposes a
typed meta-executive route, and loads the harvested CFF v2 engine only through
an explicitly configured, hash-verifiable adapter.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, Sequence

try:
    from . import bco_prime_capability_fabric_v1 as core
    from . import bco_prime_chat_forensics_v1 as legacy
except ImportError:  # direct script execution from the module directory
    import bco_prime_capability_fabric_v1 as core
    import bco_prime_chat_forensics_v1 as legacy


SCHEMA = "BCO_PRIME_CHAT_FORENSICS_V2"
VERSION = "2.0.0"
TRUTH_REPAIR_SCHEMA = "BCO_PRIME_CHAT_FORENSICS_V1_1"
TRUTH_REPAIR_VERSION = "1.1.0"
AUTHORITY = "A1_LOCAL_INTERNAL"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
META_SOURCE_SHA256 = "0f04e5a1e08159325563432695ce3c6d1faec294324c45df327b831f9fdb1902"
META_RUNTIME_FAILURES = (
    "federation_autopilot_metacognition_v1:MISSING",
    "bubbles.chat_governor_omega3.continuity:MISSING",
    "formation_omega.reconciliation_fabric_v2:MISSING",
)

META_OPERATIONS = (
    "BCO-PRIME-META-MANIFEST",
    "BCO-PRIME-META-STRATEGY-TOURNAMENT",
)
ENGINE_OPERATIONS = (
    "CFF-V2-SEMANTIC",
    "CFF-V2-JSD",
    "CFF-V2-ENTROPY",
    "CFF-V2-ENSEMBLE",
    "CFF-V2-SHIELD",
    "CFF-V2-VALIDATE-LEDGER",
    "CFF-V2-VALIDATE-CAPSULE",
    "CFF-V2-RUN-NATIVE-AUDIT",
)
METHODOLOGY_SOURCE_KINDS = {
    "forensic_engine",
    "forensic_engine_dependency",
    "forensic_method",
    "tooling",
    "tooling_asset",
}
EXTERNAL_EFFECT_KEYS = {
    "external_effect",
    "external_mutation",
    "send",
    "publish",
    "deploy",
    "merge",
    "register",
    "financial_effect",
    "approval_effect",
}


class ContractError(ValueError):
    """Raised when a typed v2 contract is violated."""


class EngineUnavailable(RuntimeError):
    """Raised when the optional CFF engine is absent or fails verification."""


@dataclass(frozen=True, slots=True)
class MetaStrategyCandidate:
    """Exact safe subset of the v1 meta-executive StrategyCandidate."""

    strategy_id: str
    failure_domain: str
    expected_quality: float
    evidence_strength: float
    reliability: float
    reversibility: float
    information_gain: float
    failure_domain_diversity: float
    latency_cost: float
    monetary_cost: float
    owner_burden: float
    risk: float
    external_effect: bool = False
    proof_refs: tuple[str, ...] = ()

    def validate(self) -> "MetaStrategyCandidate":
        if not self.strategy_id.strip():
            raise ContractError("STRATEGY_ID_REQUIRED")
        if not self.failure_domain.strip():
            raise ContractError("STRATEGY_FAILURE_DOMAIN_REQUIRED")
        for field_name in (
            "expected_quality",
            "evidence_strength",
            "reliability",
            "reversibility",
            "information_gain",
            "failure_domain_diversity",
            "latency_cost",
            "monetary_cost",
            "owner_burden",
            "risk",
        ):
            value = float(getattr(self, field_name))
            if not 0.0 <= value <= 1.0:
                raise ContractError(f"STRATEGY_{field_name.upper()}_OUT_OF_RANGE")
        if self.external_effect:
            raise ContractError("META_SAFE_SUBSET_EXTERNAL_EFFECT_REJECTED")
        return self

    def fitness(self) -> float:
        self.validate()
        benefit = (
            0.24 * self.expected_quality
            + 0.18 * self.evidence_strength
            + 0.17 * self.reliability
            + 0.10 * self.reversibility
            + 0.12 * self.information_gain
            + 0.08 * self.failure_domain_diversity
        )
        burden = (
            0.04 * self.latency_cost
            + 0.02 * self.monetary_cost
            + 0.03 * self.owner_burden
            + 0.08 * self.risk
        )
        return round(benefit - burden, 9)


@dataclass(frozen=True, slots=True)
class MetaStrategyTournamentResult:
    champion_strategy_id: str
    challenger_strategy_ids: tuple[str, ...]
    fallback_strategy_id: str | None
    ranked_strategy_ids: tuple[str, ...]
    fitness_by_strategy: tuple[tuple[str, float], ...]
    reason_codes: tuple[str, ...]


def rank_meta_strategies(
    candidates: Sequence[MetaStrategyCandidate],
) -> MetaStrategyTournamentResult:
    """Exact v1 ordering/fallback algorithm, bound to META_SOURCE_SHA256."""
    if not candidates:
        raise ContractError("PRIME_STRATEGY_CANDIDATE_REQUIRED")
    ids = [candidate.strategy_id.strip() for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise ContractError("PRIME_DUPLICATE_STRATEGY_ID")
    validated = [candidate.validate() for candidate in candidates]
    ranked = sorted(validated, key=lambda item: (-item.fitness(), item.strategy_id))
    champion = ranked[0]
    challengers = tuple(item.strategy_id for item in ranked[1:3])
    fallback = next(
        (
            item.strategy_id
            for item in ranked[1:]
            if item.failure_domain != champion.failure_domain
        ),
        ranked[1].strategy_id if len(ranked) > 1 else None,
    )
    reasons = ["FITNESS_WEIGHTED_STRATEGY_TOURNAMENT"]
    if fallback is not None:
        reasons.append("FALLBACK_PRESERVED")
    if any(item.failure_domain != champion.failure_domain for item in ranked[1:]):
        reasons.append("FAILURE_DOMAIN_DIVERSITY_PRESERVED")
    return MetaStrategyTournamentResult(
        champion.strategy_id,
        challengers,
        fallback,
        tuple(item.strategy_id for item in ranked),
        tuple((item.strategy_id, item.fitness()) for item in ranked),
        tuple(reasons),
    )


def meta_safe_manifest() -> dict[str, Any]:
    return {
        "schema": "BCO_PRIME_META_EXECUTIVE_V1_SAFE_SUBSET",
        "source_sha256": META_SOURCE_SHA256,
        "safe_subset_operations": ("rank_strategies", "prime_capability_manifest"),
        "full_runtime_ready": False,
        "full_runtime_failures": META_RUNTIME_FAILURES,
        "v1_mode": "SHADOW_ONLY",
        "external_effect_authority": False,
        "new_authority_planes": 0,
        "new_schedulers": 0,
        "new_memory_roots": 0,
        "new_provider_executors": 0,
        "capability_fabric": "BCO_PRIME_CAPABILITY_FABRIC_V1",
        "zero_manual_capability_functions": 100,
        "capability_fabric_external_effect_authority": False,
    }


def _normalize(value: Any, path: str = "$") -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractError(f"{path}: non-finite number")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractError(f"{path}: object keys must be strings")
            result[key] = _normalize(item, f"{path}.{key}")
        return result
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [_normalize(item, f"{path}[{index}]") for index, item in enumerate(value)]
    raise ContractError(f"{path}: unsupported type {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        _normalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{path}: expected object")
    return dict(value)


def _bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{path}: expected boolean")
    return value


def _reject_external_effects(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in EXTERNAL_EFFECT_KEYS and item is True:
                raise ContractError(f"{path}.{key}: external effect is not authorized")
            _reject_external_effects(item, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        for index, item in enumerate(value):
            _reject_external_effects(item, f"{path}[{index}]")


def validate_incident_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a normalized, detached incident bundle."""
    clean = _normalize(_mapping(bundle, "$"))
    _reject_external_effects(clean)

    conversation = _mapping(clean.get("conversation"), "$.conversation")
    expected_id = conversation.get("expected_id")
    observed_id = conversation.get("observed_id")
    if not isinstance(expected_id, str) or not expected_id.strip():
        raise ContractError("$.conversation.expected_id: non-empty string required")
    if not isinstance(observed_id, str) or not observed_id.strip():
        raise ContractError("$.conversation.observed_id: non-empty string required")
    if expected_id != observed_id:
        raise ContractError("$.conversation: expected_id and observed_id differ")
    expected_title = conversation.get("expected_title")
    observed_title = conversation.get("observed_title")
    if expected_title is not None:
        if not isinstance(expected_title, str) or not expected_title.strip():
            raise ContractError("$.conversation.expected_title: invalid title")
        if observed_title != expected_title:
            raise ContractError("$.conversation: expected_title and observed_title differ")

    sources = clean.get("sources")
    if not isinstance(sources, list):
        raise ContractError("$.sources: expected list")
    source_ids: set[str] = set()
    for index, raw_source in enumerate(sources):
        source = _mapping(raw_source, f"$.sources[{index}]")
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ContractError(f"$.sources[{index}].source_id: non-empty string required")
        if source_id in source_ids:
            raise ContractError(f"$.sources[{index}].source_id: duplicate {source_id}")
        source_ids.add(source_id)
        accessible = _bool(source.get("accessible"), f"$.sources[{index}].accessible")
        captured = _bool(source.get("captured"), f"$.sources[{index}].captured")
        if captured and not accessible:
            raise ContractError(f"$.sources[{index}]: captured source cannot be inaccessible")
        if captured:
            sha256 = source.get("sha256")
            if not isinstance(sha256, str) or not SHA256_RE.fullmatch(sha256):
                raise ContractError(f"$.sources[{index}].sha256: lowercase SHA-256 required")
            size = source.get("bytes")
            if size is not None and (not isinstance(size, int) or isinstance(size, bool) or size < 0):
                raise ContractError(f"$.sources[{index}].bytes: non-negative integer required")

    observations = _mapping(clean.get("observations", {}), "$.observations")
    lifecycle_keys = (
        "working_indicator_present",
        "assistant_terminal_content_present",
        "final_tool_action_present",
        "final_response_commit_observed",
        "user_stop_observed",
        "client_disconnect_observed",
        "terminal_window_elapsed",
    )
    for key in lifecycle_keys:
        if key in observations:
            _bool(observations[key], f"$.observations.{key}")

    provider = clean.get("provider_durability")
    if provider is not None:
        _mapping(provider, "$.provider_durability")
    return clean


def source_accounting(sources: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    methodology: list[str] = []
    incident_captured: list[str] = []
    incident_blocked: list[str] = []
    incident_accessible_not_captured: list[str] = []
    for source in sources:
        source_id = str(source["source_id"])
        kind = str(source.get("kind", "incident_artifact")).strip().lower()
        if kind in METHODOLOGY_SOURCE_KINDS:
            methodology.append(source_id)
        elif not source["accessible"]:
            incident_blocked.append(source_id)
        elif source["captured"]:
            incident_captured.append(source_id)
        else:
            incident_accessible_not_captured.append(source_id)
    return {
        "methodology_asset_count": len(methodology),
        "incident_source_count": len(incident_captured) + len(incident_blocked)
        + len(incident_accessible_not_captured),
        "incident_captured_count": len(incident_captured),
        "incident_blocked_count": len(incident_blocked),
        "incident_accessible_not_captured_count": len(incident_accessible_not_captured),
        "methodology_source_ids": sorted(methodology),
        "incident_captured_source_ids": sorted(incident_captured),
        "incident_blocked_source_ids": sorted(incident_blocked),
        "incident_accessible_not_captured_source_ids": sorted(
            incident_accessible_not_captured
        ),
    }


def terminal_lifecycle(observations: Mapping[str, Any]) -> dict[str, Any]:
    working = bool(observations.get("working_indicator_present", False))
    terminal_content = bool(
        observations.get("assistant_terminal_content_present", False)
    )
    final_tool = bool(observations.get("final_tool_action_present", False))
    commit = bool(observations.get("final_response_commit_observed", False))
    user_stop = bool(observations.get("user_stop_observed", False))
    disconnect = bool(observations.get("client_disconnect_observed", False))
    elapsed = bool(observations.get("terminal_window_elapsed", False))

    if commit and terminal_content:
        state = "COMMITTED"
    elif user_stop:
        state = "ABORTED_USER"
    elif disconnect:
        state = "DISCONNECTED"
    elif working and not elapsed:
        state = "WORKING"
    elif final_tool and not commit and elapsed:
        state = "FAILED_FINALIZATION"
    else:
        state = "INDETERMINATE"
    return {
        "state": state,
        "workingIndicatorPresent": working,
        "assistantTerminalContentPresent": terminal_content,
        "finalToolActionPresent": final_tool,
        "finalResponseCommitObserved": commit,
        "terminalWindowElapsed": elapsed,
    }


def provider_durability(provider: Mapping[str, Any] | None) -> dict[str, Any]:
    provider = dict(provider or {})
    failures: list[str] = []
    pinned_ref = provider.get("pinned_ref")
    if not isinstance(pinned_ref, str) or not pinned_ref.strip():
        failures.append("PINNED_REF_MISSING")
    artifacts = provider.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        failures.append("ARTIFACT_PROOFS_MISSING")
        artifacts = []
    verified_paths: list[str] = []
    for index, raw in enumerate(artifacts):
        if not isinstance(raw, Mapping):
            failures.append(f"ARTIFACT_{index}_INVALID")
            continue
        path = raw.get("path")
        expected = raw.get("expected_sha256")
        observed = raw.get("observed_sha256")
        readback = raw.get("readback_verified")
        if not isinstance(path, str) or not path.strip():
            failures.append(f"ARTIFACT_{index}_PATH_MISSING")
        if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
            failures.append(f"ARTIFACT_{index}_EXPECTED_HASH_INVALID")
        if observed != expected:
            failures.append(f"ARTIFACT_{index}_HASH_MISMATCH")
        if readback is not True:
            failures.append(f"ARTIFACT_{index}_READBACK_UNVERIFIED")
        if (
            isinstance(path, str)
            and path.strip()
            and isinstance(expected, str)
            and SHA256_RE.fullmatch(expected)
            and observed == expected
            and readback is True
        ):
            verified_paths.append(path)
    return {
        "state": "PROVEN" if not failures else "UNPROVEN",
        "pinned_ref": pinned_ref if isinstance(pinned_ref, str) else None,
        "verified_artifact_count": len(verified_paths),
        "verified_paths": sorted(verified_paths),
        "failures": sorted(set(failures)),
    }


def contradiction_registry(
    incident: Mapping[str, Any], lifecycle: Mapping[str, Any]
) -> list[dict[str, str]]:
    contradictions: list[dict[str, str]] = []
    metrics = incident.get("capture_metrics")
    if not isinstance(metrics, Mapping):
        metrics = incident.get("observations", {}).get("capture_metrics", {})
    terminal_blank = metrics.get("terminalBlankTurn") if isinstance(metrics, Mapping) else None
    if (
        terminal_blank is False
        and lifecycle["assistantTerminalContentPresent"] is False
    ):
        contradictions.append(
            {
                "id": "TERMINAL_BLANK_CONTRADICTION",
                "left": "capture_metrics.terminalBlankTurn=false",
                "right": "assistant_terminal_content_present=false",
                "disposition": "UNRESOLVED",
            }
        )
    if (
        lifecycle["state"] == "FAILED_FINALIZATION"
        and lifecycle["workingIndicatorPresent"]
    ):
        contradictions.append(
            {
                "id": "WORKING_VS_FINAL_FAILURE",
                "left": "working_indicator_present=true",
                "right": "terminal lifecycle=FAILED_FINALIZATION",
                "disposition": "UNRESOLVED",
            }
        )
    return contradictions


def calibrated_confidence(
    lifecycle: Mapping[str, Any],
    accounting: Mapping[str, Any],
    contradictions: Sequence[Mapping[str, Any]],
    observations: Mapping[str, Any],
) -> dict[str, Any]:
    score = 0.0
    signals: list[str] = []
    if lifecycle["state"] == "FAILED_FINALIZATION":
        score += 0.35
        signals.append("TERMINAL_STATE_FAILED_FINALIZATION")
    if lifecycle["finalToolActionPresent"]:
        score += 0.15
        signals.append("FINAL_TOOL_ACTION_PRESENT")
    if not lifecycle["assistantTerminalContentPresent"]:
        score += 0.15
        signals.append("TERMINAL_ASSISTANT_CONTENT_ABSENT")
    if lifecycle["terminalWindowElapsed"]:
        score += 0.15
        signals.append("TERMINAL_WINDOW_ELAPSED")
    incident_count = int(accounting["incident_captured_count"])
    if incident_count >= 3:
        score += 0.15
        signals.append("THREE_OR_MORE_INCIDENT_SOURCES_CAPTURED")
    if observations.get("native_terminal_event_verified") is True:
        score += 0.15
        signals.append("NATIVE_TERMINAL_EVENT_VERIFIED")
    score = max(0.0, min(1.0, score - 0.2 * len(contradictions)))
    if score >= 0.8:
        label = "HIGH"
    elif score >= 0.55:
        label = "MODERATE"
    elif score >= 0.3:
        label = "LOW"
    else:
        label = "INSUFFICIENT"
    if (
        observations.get("native_terminal_event_verified") is True
        and not contradictions
        and lifecycle["state"] == "FAILED_FINALIZATION"
    ):
        state = "EVENT_VERIFIED"
    elif signals:
        state = "SOURCE_SUPPORTED_PARTIAL"
    else:
        state = "UNVERIFIED"
    return {
        "state": state,
        "label": label,
        "score": round(score, 3),
        "signals": signals,
        "contradiction_penalty": round(0.2 * len(contradictions), 3),
    }


def audit_incident_v1_1(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Repair v1 truth semantics while retaining the original v1 result."""
    clean = validate_incident_bundle(bundle)
    observations = clean.get("observations", {})
    lifecycle = terminal_lifecycle(observations)
    accounting = source_accounting(clean["sources"])
    contradictions = contradiction_registry(clean, lifecycle)
    confidence = calibrated_confidence(
        lifecycle, accounting, contradictions, observations
    )
    durability = provider_durability(clean.get("provider_durability"))
    try:
        legacy_result = legacy.audit_incident(clean)
        legacy_error = None
    except Exception as exc:  # v1 is retained as evidence, never as the v2 gate
        legacy_result = None
        legacy_error = f"{type(exc).__name__}:{exc}"

    if lifecycle["state"] == "FAILED_FINALIZATION":
        finding = "FINAL_RESPONSE_COMMIT_FAILURE"
    elif lifecycle["state"] == "COMMITTED":
        finding = "NO_FINALIZATION_FAILURE_OBSERVED"
    else:
        finding = "FINALIZATION_FAILURE_SUSPECTED"
    audit_state = (
        "PARTIAL_CHECKPOINTED"
        if accounting["incident_captured_count"] > 0
        else "INSUFFICIENT_EVIDENCE"
    )
    result = {
        "schema": TRUTH_REPAIR_SCHEMA,
        "version": TRUTH_REPAIR_VERSION,
        "audit_state": audit_state,
        "primary_finding": finding,
        "backend_cause": "UNVERIFIED",
        "terminal_lifecycle": lifecycle,
        "confidence": confidence,
        "source_accounting": accounting,
        "provider_durability": durability,
        "contradictions": contradictions,
        "legacy_v1": {
            "available": legacy_result is not None,
            "result_sha256": digest(legacy_result) if legacy_result is not None else None,
            "error": legacy_error,
        },
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["receipt_sha256"] = digest(result)
    return result


@dataclass(frozen=True)
class CFFEngineSpec:
    engine_path: Path
    dependency_root: Path
    expected_engine_sha256: str | None = None
    expected_dependency_sha256: str | None = None


class CFFEngineAdapter:
    """Hash-aware adapter over the harvested CFF v2 engine."""

    def __init__(self, spec: CFFEngineSpec):
        self.spec = spec
        self._module: ModuleType | None = None

    @property
    def dependency_path(self) -> Path:
        return self.spec.dependency_root / "restored_v1" / "app_mentions_forensic_audit.py"

    def probe(self) -> dict[str, Any]:
        engine_exists = self.spec.engine_path.is_file()
        dependency_exists = self.dependency_path.is_file()
        engine_hash = file_sha256(self.spec.engine_path) if engine_exists else None
        dependency_hash = file_sha256(self.dependency_path) if dependency_exists else None
        failures: list[str] = []
        if not engine_exists:
            failures.append("ENGINE_PATH_MISSING")
        if not dependency_exists:
            failures.append("DEPENDENCY_PATH_MISSING")
        if (
            self.spec.expected_engine_sha256
            and engine_hash != self.spec.expected_engine_sha256
        ):
            failures.append("ENGINE_HASH_MISMATCH")
        if (
            self.spec.expected_dependency_sha256
            and dependency_hash != self.spec.expected_dependency_sha256
        ):
            failures.append("DEPENDENCY_HASH_MISMATCH")
        return {
            "ready": not failures,
            "engine_exists": engine_exists,
            "dependency_exists": dependency_exists,
            "engine_sha256": engine_hash,
            "dependency_sha256": dependency_hash,
            "failures": failures,
        }

    def load(self) -> ModuleType:
        if self._module is not None:
            return self._module
        probe = self.probe()
        if not probe["ready"]:
            raise EngineUnavailable("|".join(probe["failures"]))
        module_name = f"_bco_cff_v2_{probe['engine_sha256'][:12]}"
        spec = importlib.util.spec_from_file_location(module_name, self.spec.engine_path)
        if spec is None or spec.loader is None:
            raise EngineUnavailable("ENGINE_IMPORT_SPEC_FAILED")
        module = importlib.util.module_from_spec(spec)
        root = str(self.spec.dependency_root)
        added = root not in sys.path
        if added:
            sys.path.insert(0, root)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise EngineUnavailable(f"ENGINE_IMPORT_FAILED:{type(exc).__name__}:{exc}") from exc
        finally:
            if added and root in sys.path:
                sys.path.remove(root)
        self._module = module
        return module

    def execute(self, operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        _reject_external_effects(payload)
        module = self.load()
        data = _mapping(payload, "$.payload")
        if operation == "CFF-V2-SEMANTIC":
            output = module.semantic(str(data.get("left", "")), str(data.get("right", "")))
        elif operation == "CFF-V2-JSD":
            output = module.jsd(
                _mapping(data.get("left", {}), "$.payload.left"),
                _mapping(data.get("right", {}), "$.payload.right"),
            )
        elif operation == "CFF-V2-ENTROPY":
            texts = data.get("texts", [])
            if not isinstance(texts, list):
                raise ContractError("$.payload.texts: expected list")
            output = module.entropy([str(item) for item in texts])
        elif operation == "CFF-V2-ENSEMBLE":
            values = data.get("values", [])
            if not isinstance(values, list):
                raise ContractError("$.payload.values: expected list")
            output = module.ensemble([float(item) for item in values])
        elif operation == "CFF-V2-SHIELD":
            output = module.shield(float(data.get("ratio", 0.0)))
        elif operation == "CFF-V2-VALIDATE-LEDGER":
            events = data.get("events", [])
            if not isinstance(events, list):
                raise ContractError("$.payload.events: expected list")
            output = module.validate_ledger(events)
        elif operation == "CFF-V2-VALIDATE-CAPSULE":
            output = module.validate_capsule(str(data.get("text", "")))
        else:
            raise ContractError(f"unsupported pure engine operation: {operation}")
        return {
            "schema": "CFF_V2_ADAPTER_RECEIPT",
            "operation": operation,
            "engine_sha256": self.probe()["engine_sha256"],
            "input_sha256": digest(data),
            "output": _normalize(output),
            "manualUserTasks": [],
            "ownerActionRequired": False,
        }

    def run_native_audit(
        self,
        source: Path,
        title: str,
        output_dir: Path,
        output_prefix: str,
        config_path: Path | None = None,
    ) -> dict[str, Any]:
        if not source.is_file():
            raise ContractError("native audit source does not exist")
        if not title.strip() or not output_prefix.strip():
            raise ContractError("title and output_prefix are required")
        output_dir.mkdir(parents=True, exist_ok=True)
        module = self.load()
        result = module.run(source, title, config_path, output_dir, output_prefix)
        if (
            not isinstance(result, tuple)
            or len(result) != 2
            or not isinstance(result[0], Mapping)
            or not isinstance(result[1], Mapping)
        ):
            raise ContractError("CFF engine returned an unsupported run contract")
        report, returned_paths = result
        paths = {str(key): str(value) for key, value in returned_paths.items()}
        validation = validate_cff_output_set(paths, self)
        return {
            "schema": "CFF_V2_NATIVE_AUDIT_RECEIPT",
            "engine_sha256": self.probe()["engine_sha256"],
            "source_sha256": file_sha256(source),
            "result_sha256": digest({"report": report, "paths": paths}),
            "audit_state": report.get("audit", {}).get("state", "UNAVAILABLE"),
            "output_paths": paths,
            "output_validation": validation,
            "manualUserTasks": [],
            "ownerActionRequired": False,
        }


OUTPUT_SUFFIXES = {
    "json": "_forensic_audit_v2.json",
    "markdown": "_forensic_audit_v2.md",
    "csv": "_exchange_metrics_v2.csv",
    "html": "_forensic_dashboard_v2.html",
    "ledger": "_event_ledger_v2.jsonl",
    "transaction": "_transaction_manifest_v2.json",
}
OUTPUT_KEYS = (*OUTPUT_SUFFIXES, "capsule")


def discover_output_paths(output_dir: Path, prefix: str) -> dict[str, str]:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", prefix.strip()).strip("._-")
    safe = safe or "conversation"
    paths = {
        name: str(output_dir / f"{safe}{suffix}")
        for name, suffix in OUTPUT_SUFFIXES.items()
    }
    bridge_key = f"{safe.replace('_', '-')}-forensics"
    paths["capsule"] = str(output_dir / f"CHATBRIDGE-{bridge_key}-CURRENT.md")
    return paths


def validate_cff_output_set(
    paths: Mapping[str, Any], adapter: CFFEngineAdapter | None = None
) -> dict[str, Any]:
    failures: list[str] = []
    hashes: dict[str, str] = {}
    for name in OUTPUT_KEYS:
        raw_path = paths.get(name)
        if not isinstance(raw_path, str) or not raw_path:
            failures.append(f"{name.upper()}_PATH_MISSING")
            continue
        path = Path(raw_path)
        if not path.is_file() or path.stat().st_size == 0:
            failures.append(f"{name.upper()}_FILE_MISSING_OR_EMPTY")
            continue
        hashes[name] = file_sha256(path)
    if "ledger" in hashes and adapter is not None:
        try:
            ledger_text = Path(str(paths["ledger"])).read_text(encoding="utf-8")
            events = [
                json.loads(line)
                for line in ledger_text.splitlines()
                if line.strip()
            ]
            receipt = adapter.execute("CFF-V2-VALIDATE-LEDGER", {"events": events})
            if receipt["output"] is not True:
                failures.append("LEDGER_VALIDATION_FAILED")
        except Exception as exc:
            failures.append(f"LEDGER_VALIDATION_ERROR:{type(exc).__name__}")
    if "capsule" in hashes and adapter is not None:
        try:
            text = Path(str(paths["capsule"])).read_text(encoding="utf-8")
            receipt = adapter.execute("CFF-V2-VALIDATE-CAPSULE", {"text": text})
            output = receipt["output"]
            valid = output[0] if isinstance(output, list) and output else bool(output)
            if not valid:
                failures.append("CHATBRIDGE_VALIDATION_FAILED")
        except Exception as exc:
            failures.append(f"CHATBRIDGE_VALIDATION_ERROR:{type(exc).__name__}")
    return {
        "complete": not failures and len(hashes) == len(OUTPUT_KEYS),
        "validated_file_count": len(hashes),
        "required_file_count": len(OUTPUT_KEYS),
        "sha256": hashes,
        "failures": failures,
    }


def _strategy_tournament(payload: Mapping[str, Any]) -> dict[str, Any]:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ContractError("$.payload.candidates: non-empty list required")
    typed = []
    field_names = set(MetaStrategyCandidate.__dataclass_fields__)
    for index, candidate in enumerate(candidates):
        data = _mapping(candidate, f"$.payload.candidates[{index}]")
        unknown = sorted(set(data) - field_names)
        if unknown:
            raise ContractError(
                f"$.payload.candidates[{index}]: unknown fields {','.join(unknown)}"
            )
        try:
            typed.append(MetaStrategyCandidate(**data))
        except TypeError as exc:
            raise ContractError(f"$.payload.candidates[{index}]: {exc}") from exc
    result = rank_meta_strategies(typed)
    output = _normalize(asdict(result))
    output["meta_source_sha256"] = META_SOURCE_SHA256
    output["full_meta_runtime_ready"] = False
    return output


class UnifiedRegistry:
    """Single dispatch and observability surface for all harvested components."""

    def __init__(self, engine: CFFEngineAdapter | None = None):
        self.engine = engine

    def health(self) -> dict[str, Any]:
        engine_probe = (
            self.engine.probe()
            if self.engine is not None
            else {
                "ready": False,
                "engine_exists": False,
                "dependency_exists": False,
                "engine_sha256": None,
                "dependency_sha256": None,
                "failures": ["ENGINE_NOT_CONFIGURED"],
            }
        )
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "authority": AUTHORITY,
            "core_count": len(core.CAPABILITY_SPECS),
            "legacy_extension_count": len(legacy.CAPABILITY_SPECS),
            "meta_operation_count": len(META_OPERATIONS),
            "engine_operation_count": len(ENGINE_OPERATIONS),
            "total_registered_count": len(core.CAPABILITY_SPECS)
            + len(legacy.CAPABILITY_SPECS)
            + len(META_OPERATIONS)
            + len(ENGINE_OPERATIONS),
            "engine": engine_probe,
            "meta": {
                "safe_subset_ready": True,
                "full_runtime_ready": False,
                "source_sha256": META_SOURCE_SHA256,
                "failures": list(META_RUNTIME_FAILURES),
            },
            "external_mutation_authorized": False,
            "manualUserTasks": [],
            "ownerActionRequired": False,
        }

    def manifest(self) -> dict[str, Any]:
        core_ids = sorted(core.FUNCTION_REGISTRY)
        legacy_ids = sorted(legacy.FUNCTION_REGISTRY)
        result = self.health()
        result["namespaces"] = {
            "core": core_ids,
            "legacy_chat_forensics": legacy_ids,
            "meta": list(META_OPERATIONS),
            "cff_engine": list(ENGINE_OPERATIONS),
        }
        result["manifest_sha256"] = digest(result)
        return result

    def execute(self, operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(operation, str) or not operation:
            raise ContractError("operation must be a non-empty string")
        clean = _normalize(_mapping(payload, "$.payload"))
        _reject_external_effects(clean)
        if operation in core.FUNCTION_REGISTRY:
            output = core.execute_capability(operation, clean)
            namespace = "core"
        elif operation in legacy.FUNCTION_REGISTRY:
            output = legacy.execute_capability(operation, clean)
            namespace = "legacy_chat_forensics"
        elif operation == "BCO-PRIME-META-MANIFEST":
            output = meta_safe_manifest()
            namespace = "meta"
        elif operation == "BCO-PRIME-META-STRATEGY-TOURNAMENT":
            output = _strategy_tournament(clean)
            namespace = "meta"
        elif operation == "CFF-V2-RUN-NATIVE-AUDIT":
            if self.engine is None:
                raise EngineUnavailable("ENGINE_NOT_CONFIGURED")
            output = self.engine.run_native_audit(
                Path(str(clean.get("source", ""))),
                str(clean.get("title", "")),
                Path(str(clean.get("output_dir", ""))),
                str(clean.get("output_prefix", "")),
                Path(str(clean["config_path"])) if clean.get("config_path") else None,
            )
            namespace = "cff_engine"
        elif operation in ENGINE_OPERATIONS:
            if self.engine is None:
                raise EngineUnavailable("ENGINE_NOT_CONFIGURED")
            output = self.engine.execute(operation, clean)
            namespace = "cff_engine"
        else:
            raise ContractError(f"unknown operation: {operation}")
        receipt = {
            "schema": "BCO_PRIME_UNIFIED_EXECUTION_RECEIPT_V2",
            "version": VERSION,
            "namespace": namespace,
            "operation": operation,
            "input_sha256": digest(clean),
            "output": _normalize(output),
            "manualUserTasks": [],
            "ownerActionRequired": False,
        }
        receipt["receipt_sha256"] = digest(receipt)
        return receipt


CORE_PROFILE_IDS = (
    "BCO-PRIME-CAP-002",
    "BCO-PRIME-CAP-013",
    "BCO-PRIME-CAP-025",
    "BCO-PRIME-CAP-031",
    "BCO-PRIME-CAP-050",
    "BCO-PRIME-CAP-060",
    "BCO-PRIME-CAP-061",
    "BCO-PRIME-CAP-071",
    "BCO-PRIME-CAP-089",
    "BCO-PRIME-CAP-096",
)


def _core_domain_profile(registry: UnifiedRegistry) -> dict[str, Any]:
    receipts: list[dict[str, Any]] = []
    failures: list[str] = []
    for capability_id in CORE_PROFILE_IDS:
        try:
            receipt = registry.execute(capability_id, {})
            receipts.append(
                {
                    "capability_id": capability_id,
                    "receipt_sha256": receipt["receipt_sha256"],
                }
            )
        except Exception as exc:
            failures.append(f"{capability_id}:{type(exc).__name__}:{exc}")
    return {
        "requested_domain_count": 10,
        "executed_domain_count": len(receipts),
        "receipts": receipts,
        "failures": failures,
    }


def audit_incident_v2(
    bundle: Mapping[str, Any], registry: UnifiedRegistry | None = None
) -> dict[str, Any]:
    clean = validate_incident_bundle(bundle)
    active_registry = registry or UnifiedRegistry()
    repaired = audit_incident_v1_1(clean)
    core_profile = _core_domain_profile(active_registry)
    output_validation = None
    native_paths = clean.get("native_cff_output_paths")
    if isinstance(native_paths, Mapping):
        output_validation = validate_cff_output_set(
            native_paths, active_registry.engine
        )
    native_complete = bool(output_validation and output_validation["complete"])
    audit_state = "COMPLETE_VERIFIED" if native_complete else repaired["audit_state"]
    result = {
        "schema": SCHEMA,
        "version": VERSION,
        "authority": AUTHORITY,
        "correlation_id": f"bco-v2-{digest(clean)[:20]}",
        "audit_state": audit_state,
        "primary_finding": repaired["primary_finding"],
        "backend_cause": "UNVERIFIED",
        "truth_repair_v1_1": repaired,
        "core_domain_profile": core_profile,
        "registry": active_registry.health(),
        "native_cff_output_validation": output_validation,
        "claims": {
            "designed": True,
            "implemented": True,
            "tested": False,
            "registered": False,
            "authorized": True,
            "ready": False,
            "deployed": False,
            "proven": False,
        },
        "manualUserTasks": [],
        "ownerActionRequired": False,
    }
    result["receipt_sha256"] = digest(result)
    return result


def _engine_from_args(args: argparse.Namespace) -> CFFEngineAdapter | None:
    if not getattr(args, "engine_path", None):
        return None
    if not getattr(args, "dependency_root", None):
        raise ContractError("--dependency-root is required with --engine-path")
    return CFFEngineAdapter(
        CFFEngineSpec(
            Path(args.engine_path),
            Path(args.dependency_root),
            getattr(args, "engine_sha256", None),
            getattr(args, "dependency_sha256", None),
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-path")
    parser.add_argument("--dependency-root")
    parser.add_argument("--engine-sha256")
    parser.add_argument("--dependency-sha256")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("operation")
    run_parser.add_argument("--payload-json", required=True)
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--payload-json", required=True)
    native_parser = sub.add_parser("engine-audit")
    native_parser.add_argument("--source", required=True)
    native_parser.add_argument("--title", required=True)
    native_parser.add_argument("--output-dir", required=True)
    native_parser.add_argument("--output-prefix", required=True)
    native_parser.add_argument("--config-path")
    validate_parser = sub.add_parser("validate-outputs")
    validate_parser.add_argument("--paths-json", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    engine = _engine_from_args(args)
    registry = UnifiedRegistry(engine)
    if args.command == "list":
        output = registry.manifest()
    elif args.command == "run":
        output = registry.execute(args.operation, json.loads(args.payload_json))
    elif args.command == "audit":
        output = audit_incident_v2(json.loads(args.payload_json), registry)
    elif args.command == "engine-audit":
        if engine is None:
            raise ContractError("--engine-path is required for engine-audit")
        output = engine.run_native_audit(
            Path(args.source),
            args.title,
            Path(args.output_dir),
            args.output_prefix,
            Path(args.config_path) if args.config_path else None,
        )
    elif args.command == "validate-outputs":
        output = validate_cff_output_set(json.loads(args.paths_json), engine)
    else:  # pragma: no cover
        raise ContractError(f"unsupported command: {args.command}")
    print(json.dumps(_normalize(output), ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
