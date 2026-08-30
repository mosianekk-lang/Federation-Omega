"""Effect-free runtime composition for CFBE closure cells C03, C05, C07 and C12.

The module reuses Living State, the admitted closure matrix scheduler, empirical
measurement normalization and the v4 Foundry readiness gate.  It creates no
provider, financial or deployment authority and never turns DATA_READY into a
promotion claim.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from federation.living_state.store import StoreReceipt
from federation.living_state.world_model import LivingWorldModel, ProofMaturity

from .closure_matrix_v1 import ClosureWaveReceipt, plan_wave, validate_matrix
from .empirical_measurement_fabric import (
    DimensionBound,
    FederationObservationPacket,
    MeasurementFabricReport,
    compile_measurement_rows,
)
from .measurement_sheet_ingestion import assemble_observed_experiment_rows
from .observed_experiment_normalization import evaluate_observed_experiment
from .v4_capability_foundry import (
    CapabilityFoundryInput,
    ConfidenceEvidence,
    ExperimentEvidence,
    GapObservation,
    RegressionBaselineEvidence,
    evaluate_capability_foundry_readiness,
)


PREREGISTRATION_PATH = Path(__file__).with_name(
    "convergence_closure_observation_preregistration_v1.json"
)
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_OBSERVED_EXPERIMENT = "OBSERVED_FEDERATION_EXPERIMENT"
_ALLOWED_AUTHORITY = frozenset({"A0", "A0_READ", "A1", "A1_INTERNAL"})
_MIN_PROOF = frozenset(
    {
        ProofMaturity.SOURCE_READBACK.value,
        ProofMaturity.DETERMINISTIC_TESTED.value,
        ProofMaturity.RUNTIME_READBACK.value,
        ProofMaturity.PROVIDER_READBACK.value,
        ProofMaturity.RECEIPT_VERIFIED.value,
    }
)


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _clean_refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({" ".join(str(value).split()) for value in values if str(value).strip()}))


def _number(value: Any, blocker: str, blockers: list[str]) -> float:
    if isinstance(value, bool):
        blockers.append(blocker)
        return 0.0
    try:
        result = float(value)
    except (TypeError, ValueError):
        blockers.append(blocker)
        return 0.0
    if not math.isfinite(result) or result < 0.0:
        blockers.append(blocker)
        return 0.0
    return result


@dataclass(frozen=True, slots=True)
class CapabilityProjection:
    capability_id: str
    node_id: str
    current_main_sha: str
    source_main_sha: str
    state: str
    fresh: bool
    split_brain: bool
    proof_maturity: str
    proof_rank: int
    confidence: float
    authority_ceiling: str
    latency_ms: float
    cost_units: float
    failure_domains: tuple[str, ...]
    proof_refs: tuple[str, ...]
    schedulable: bool
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CapabilityRegistryReceipt:
    schema: str
    state: str
    current_main_sha: str
    matrix_sha256: str
    graph_sha256: str
    event_head_digest: str
    store_receipt_sha256: str
    store_readback_verified: bool
    current_head_verified: bool
    projections: tuple[CapabilityProjection, ...]
    external_effects: int
    receipt_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "state": self.state,
            "current_main_sha": self.current_main_sha,
            "matrix_sha256": self.matrix_sha256,
            "graph_sha256": self.graph_sha256,
            "event_head_digest": self.event_head_digest,
            "store_receipt_sha256": self.store_receipt_sha256,
            "store_readback_verified": self.store_readback_verified,
            "current_head_verified": self.current_head_verified,
            "projections": [item.to_dict() for item in self.projections],
            "external_effects": self.external_effects,
            "receipt_sha256": self.receipt_sha256,
        }


def project_capability_registry(
    matrix: Mapping[str, Any],
    model: LivingWorldModel,
    *,
    now: str,
    current_main_sha: str,
    store_receipt: StoreReceipt | None,
    capability_ids: Iterable[str] | None = None,
) -> CapabilityRegistryReceipt:
    """Project Living State into a current-head CFBE scheduler registry."""

    validate_matrix(matrix)
    if not _SHA40.fullmatch(current_main_sha):
        raise ValueError("CFBE_REGISTRY_CURRENT_MAIN_SHA40_REQUIRED")
    row_ids = tuple(str(row["id"]) for row in matrix["rows"])
    requested = row_ids if capability_ids is None else tuple(sorted(set(str(x) for x in capability_ids)))
    unknown = set(requested) - set(row_ids)
    if unknown:
        raise ValueError("CFBE_REGISTRY_UNKNOWN_CAPABILITY:" + ",".join(sorted(unknown)))

    nodes = model.current_nodes(now=now)
    projections: list[CapabilityProjection] = []
    for capability_id in requested:
        node_id = f"capability:{capability_id}"
        estimate = model.state_estimate(node_id, now=now)
        node = nodes.get(node_id)
        blockers: list[str] = []
        source_main_sha = ""
        authority = ""
        latency_ms = 0.0
        cost_units = 0.0
        failure_domains: tuple[str, ...] = ()
        proof_refs: tuple[str, ...] = ()
        if node is None:
            blockers.append("LIVING_STATE_NODE_MISSING")
        else:
            payload = dict(node.payload)
            source_main_sha = str(payload.get("source_main_sha", ""))
            if not _SHA40.fullmatch(source_main_sha):
                blockers.append("SOURCE_MAIN_SHA40_REQUIRED")
            elif source_main_sha != current_main_sha:
                blockers.append("STALE_MAIN_PROJECTION")
            authority = str(node.provenance.authority_ceiling)
            if authority not in _ALLOWED_AUTHORITY:
                blockers.append("AUTHORITY_CEILING_EXCEEDED")
            if "latency_ms" not in payload:
                blockers.append("LATENCY_OBSERVATION_REQUIRED")
            latency_ms = _number(payload.get("latency_ms"), "LATENCY_OBSERVATION_INVALID", blockers)
            if "cost_units" not in payload:
                blockers.append("COST_OBSERVATION_REQUIRED")
            cost_units = _number(payload.get("cost_units"), "COST_OBSERVATION_INVALID", blockers)
            domains = payload.get("failure_domains")
            if not isinstance(domains, (list, tuple)):
                blockers.append("FAILURE_DOMAINS_OBSERVATION_REQUIRED")
            else:
                failure_domains = tuple(sorted({str(item) for item in domains if str(item)}))
            proof_refs = _clean_refs(
                (estimate.proof_ref, *tuple(payload.get("proof_refs") or ()))
            )
            if not proof_refs:
                blockers.append("CAPABILITY_PROOF_REQUIRED")
            if node.state.upper() in {"INACTIVE", "FAILED", "DOWN", "HELD", "UNKNOWN"}:
                blockers.append("CAPABILITY_STATE_NOT_SCHEDULABLE")
        if not estimate.fresh:
            blockers.append("STALE_LIVING_STATE")
        if estimate.split_brain:
            blockers.append("SPLIT_BRAIN_LIVING_STATE")
        if estimate.proof_maturity not in _MIN_PROOF:
            blockers.append("PROOF_MATURITY_BELOW_SOURCE")
        projections.append(
            CapabilityProjection(
                capability_id=capability_id,
                node_id=node_id,
                current_main_sha=current_main_sha,
                source_main_sha=source_main_sha,
                state=estimate.state,
                fresh=estimate.fresh,
                split_brain=estimate.split_brain,
                proof_maturity=estimate.proof_maturity,
                proof_rank=estimate.proof_rank,
                confidence=float(estimate.confidence),
                authority_ceiling=authority,
                latency_ms=latency_ms,
                cost_units=cost_units,
                failure_domains=failure_domains,
                proof_refs=proof_refs,
                schedulable=not blockers,
                blockers=tuple(sorted(set(blockers))),
            )
        )

    store_verified = bool(
        store_receipt
        and store_receipt.store_readback_verified
        and store_receipt.event_head_digest == model.event_head_digest
        and store_receipt.external_effects == 0
    )
    current_head_verified = all(
        item.source_main_sha == current_main_sha for item in projections
    )
    state = (
        "REGISTRY_READY"
        if projections
        and all(item.schedulable for item in projections)
        and store_verified
        and current_head_verified
        and model.external_effects == 0
        else "REGISTRY_HELD"
    )
    body = {
        "schema": "CFBE-OMEGA-CAPABILITY-REGISTRY-RECEIPT-V1",
        "state": state,
        "current_main_sha": current_main_sha,
        "matrix_sha256": _sha(matrix),
        "graph_sha256": model.graph_digest(now=now),
        "event_head_digest": model.event_head_digest,
        "store_receipt_sha256": store_receipt.receipt_sha256 if store_receipt else "",
        "store_readback_verified": store_verified,
        "current_head_verified": current_head_verified,
        "projections": [item.to_dict() for item in projections],
        "external_effects": model.external_effects,
    }
    return CapabilityRegistryReceipt(
        projections=tuple(projections),
        receipt_sha256=_sha(body),
        **{key: value for key, value in body.items() if key != "projections"},
    )


def load_preregistration(path: str | Path = PREREGISTRATION_PATH) -> dict[str, Any]:
    packet = json.loads(Path(path).read_text(encoding="utf-8"))
    if packet.get("schema") != "CFBE-OMEGA-CONVERGENCE-CLOSURE-OBSERVATION-PREREGISTRATION-V1":
        raise ValueError("CFBE_CLOSURE_PREREGISTRATION_SCHEMA_MISMATCH")
    dimensions = packet.get("dimensions")
    if not isinstance(dimensions, list) or len(dimensions) != 8:
        raise ValueError("CFBE_CLOSURE_PREREGISTRATION_EIGHT_DIMENSIONS_REQUIRED")
    names = [str(item.get("dimension", "")) for item in dimensions]
    if len(set(names)) != 8:
        raise ValueError("CFBE_CLOSURE_PREREGISTRATION_DIMENSIONS_INVALID")
    if not _SHA40.fullmatch(str(packet.get("source_main_sha", ""))):
        raise ValueError("CFBE_CLOSURE_PREREGISTRATION_MAIN_SHA40_REQUIRED")
    return packet


def compile_preregistered_observation(
    preregistration: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> MeasurementFabricReport:
    """Compile C07 only when one real window matches its earlier preregistration."""

    if observation.get("schema") != "CFBE-OMEGA-CONVERGENCE-CLOSURE-OBSERVATION-V1":
        raise ValueError("CFBE_CLOSURE_OBSERVATION_SCHEMA_MISMATCH")
    for field in ("window_id", "mission_id", "source_main_sha", "observation_command"):
        if str(observation.get(field, "")) != str(preregistration.get(field, "")):
            raise ValueError(f"CFBE_CLOSURE_OBSERVATION_PREREGISTRATION_MISMATCH:{field}")
    if observation.get("evidence_class") != _OBSERVED_EXPERIMENT or observation.get("synthetic") is not False:
        raise ValueError("CFBE_CLOSURE_OBSERVED_EXPERIMENT_REQUIRED")
    if int(observation.get("exit_code", -1)) != 0:
        raise ValueError("CFBE_CLOSURE_OBSERVATION_COMMAND_MUST_PASS")
    output_sha = str(observation.get("command_output_sha256", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", output_sha):
        raise ValueError("CFBE_CLOSURE_OBSERVATION_OUTPUT_SHA256_REQUIRED")
    evidence_refs = _clean_refs(observation.get("evidence_refs") or ())
    if not evidence_refs:
        raise ValueError("CFBE_CLOSURE_OBSERVATION_PROVENANCE_REQUIRED")
    telemetry = dict(observation.get("telemetry") or {})
    if float(telemetry.get("canary.incremental_cost_usd", -1)) > float(
        preregistration["maximum_incremental_cost_usd"]
    ):
        raise ValueError("CFBE_CLOSURE_OBSERVATION_COST_CEILING_EXCEEDED")
    if float(telemetry.get("canary.manual_owner_actions", -1)) != float(
        preregistration["manual_owner_actions_allowed"]
    ):
        raise ValueError("CFBE_CLOSURE_OBSERVATION_OWNER_BURDEN_EXCEEDED")

    bounds = tuple(
        DimensionBound(
            dimension=str(item["dimension"]),
            source_keys=(str(item["source_key"]),),
            bound=float(item["bound"]),
            evidence_refs=(
                str(item["evidence_ref"]),
                f"preregistration:sha256:{_sha(preregistration)}",
            ),
        )
        for item in preregistration["dimensions"]
    )
    packet = FederationObservationPacket(
        experiment_id=str(observation["window_id"]),
        label="CFBE C03/C05/C07/C12 closure canary",
        telemetry=telemetry,
        observed_at_sast=str(observation.get("observed_at_sast", "")),
        source_system="CFBE_CLOSURE_RUNTIME_V1",
        source_work_id=str(observation["mission_id"]),
        evidence_refs=_clean_refs(
            (
                *evidence_refs,
                f"command-output:sha256:{output_sha}",
                f"branch-head:{observation.get('branch_head_sha', '')}",
            )
        ),
        evidence_class=_OBSERVED_EXPERIMENT,
        synthetic=False,
    )
    return compile_measurement_rows(packet, bounds)


@dataclass(frozen=True, slots=True)
class FailureGenomeObservation:
    observation_id: str
    mission_id: str
    capability_gap: str
    source_main_sha: str
    evidence_refs: tuple[str, ...]
    observed: bool = True


@dataclass(frozen=True, slots=True)
class FoundryAssemblyReport:
    schema: str
    mission_id: str
    source_main_sha: str
    state: str
    option_key: str
    opportunity_gradient: float | None
    capability_gap: str
    regression_baseline: str
    evidence_refs: tuple[str, ...]
    blockers: tuple[str, ...]
    receipt_sha256: str


def _held_foundry(
    *, mission_id: str, source_main_sha: str, blockers: Iterable[str]
) -> FoundryAssemblyReport:
    body = {
        "schema": "CFBE-OMEGA-FOUNDRY-ASSEMBLY-RECEIPT-V1",
        "mission_id": mission_id,
        "source_main_sha": source_main_sha,
        "state": "HELD_INCOMPLETE_FOUNDRY_DATA",
        "option_key": "",
        "opportunity_gradient": None,
        "capability_gap": "",
        "regression_baseline": "",
        "evidence_refs": (),
        "blockers": tuple(sorted(set(blockers))),
    }
    return FoundryAssemblyReport(receipt_sha256=_sha(body), **body)


def assemble_foundry_readiness(
    registry: CapabilityRegistryReceipt,
    measurement: MeasurementFabricReport,
    failure_observations: Sequence[FailureGenomeObservation],
    *,
    mission_id: str,
    regression_baseline_id: str,
    regression_proof_refs: Iterable[str],
    regression_baseline_observed: bool = True,
) -> FoundryAssemblyReport:
    """Bind C03, C07 and C10 into the existing C12 Foundry readiness gate."""

    blockers: set[str] = set()
    if registry.state != "REGISTRY_READY" or not registry.current_head_verified:
        blockers.add("C03_REGISTRY_NOT_READY")
    if measurement.state != "MEASUREMENT_PACKET_READY":
        blockers.add("C07_MEASUREMENT_NOT_READY")
    source_work_ids = {str(row.get("Source_Work_ID", "")) for row in measurement.rows}
    if source_work_ids != {mission_id}:
        blockers.add("CROSS_MISSION_MEASUREMENT_STITCHING_PROHIBITED")
    if any(row.get("Synthetic") is not False for row in measurement.rows):
        blockers.add("SYNTHETIC_MEASUREMENT_PROHIBITED")
    try:
        normalized = evaluate_observed_experiment(
            assemble_observed_experiment_rows(measurement.rows)
        )
    except (TypeError, ValueError) as exc:
        blockers.add(str(exc))
        normalized = None
    if normalized is None or normalized.option is None:
        blockers.add("OBSERVED_OPTION_REQUIRED")
    if blockers:
        return _held_foundry(
            mission_id=mission_id,
            source_main_sha=registry.current_main_sha,
            blockers=blockers,
        )

    projection = next(
        (item for item in registry.projections if item.capability_id == "C03"),
        None,
    )
    confidence = ConfidenceEvidence(
        value=projection.confidence if projection and projection.schedulable else -1.0,
        evidence_refs=(f"c03-registry:{registry.receipt_sha256}",) if projection else (),
    )
    gaps: list[GapObservation] = []
    for item in failure_observations:
        same_scope = item.mission_id == mission_id and item.source_main_sha == registry.current_main_sha
        if not same_scope:
            blockers.add("CROSS_MISSION_OR_MAIN_GAP_STITCHING_PROHIBITED")
        gaps.append(
            GapObservation(
                observation_id=item.observation_id,
                capability_gap=item.capability_gap,
                evidence_refs=_clean_refs(item.evidence_refs),
                evidence_class="OBSERVED_FEDERATION_GAP" if item.observed and same_scope else "PUBLIC_SYNTHETIC",
            )
        )
    baseline = RegressionBaselineEvidence(
        baseline_id=regression_baseline_id,
        evidence_refs=_clean_refs(regression_proof_refs),
        evidence_class="OBSERVED_REGRESSION_BASELINE" if regression_baseline_observed else "PUBLIC_SYNTHETIC",
    )
    readiness = evaluate_capability_foundry_readiness(
        CapabilityFoundryInput(
            experiment=ExperimentEvidence(normalized.option),
            confidence=confidence,
            gap_observations=tuple(gaps),
            regression_baseline=baseline,
        )
    )
    blockers.update(readiness.blockers)
    state = readiness.state if not blockers else (
        "HELD_CROSS_MISSION_EVIDENCE" if "CROSS_MISSION_OR_MAIN_GAP_STITCHING_PROHIBITED" in blockers
        else readiness.state
    )
    body = {
        "schema": "CFBE-OMEGA-FOUNDRY-ASSEMBLY-RECEIPT-V1",
        "mission_id": mission_id,
        "source_main_sha": registry.current_main_sha,
        "state": state,
        "option_key": normalized.option.option_key,
        "opportunity_gradient": readiness.opportunity_gradient,
        "capability_gap": readiness.capability_gap,
        "regression_baseline": readiness.regression_baseline,
        "evidence_refs": tuple(sorted(set(readiness.evidence_refs) | {registry.receipt_sha256})),
        "blockers": tuple(sorted(blockers)),
    }
    return FoundryAssemblyReport(receipt_sha256=_sha(body), **body)


@dataclass(frozen=True, slots=True)
class ClosureCourtResult:
    schema: str
    status: str
    hard_gates_pass: bool
    promotion_allowed: bool
    blockers: tuple[str, ...]
    proof_refs: tuple[str, ...]
    receipt_sha256: str


def evaluate_universal_closure_court(
    registry: CapabilityRegistryReceipt,
    measurement: MeasurementFabricReport,
    foundry: FoundryAssemblyReport,
    *,
    regression_baseline_id: str,
    regression_proof_refs: Iterable[str],
) -> ClosureCourtResult:
    """C01 hard-gate evaluation for an internal DATA_READY challenger."""

    blockers: set[str] = set()
    if registry.state != "REGISTRY_READY" or registry.external_effects != 0:
        blockers.add("C03_REGISTRY_GATE_FAILED")
    if measurement.state != "MEASUREMENT_PACKET_READY":
        blockers.add("C07_ECONOMIC_GATE_FAILED")
    if foundry.state != "DATA_READY":
        blockers.add("C12_FOUNDRY_GATE_FAILED")
    expected_baseline = f"git:main:{registry.current_main_sha}"
    refs = _clean_refs(regression_proof_refs)
    if regression_baseline_id != expected_baseline or not refs:
        blockers.add("EXACT_REGRESSION_BASELINE_REQUIRED")
    if foundry.regression_baseline != regression_baseline_id:
        blockers.add("FOUNDRY_BASELINE_BINDING_MISMATCH")
    option = None
    if measurement.rows:
        try:
            option = evaluate_observed_experiment(
                assemble_observed_experiment_rows(measurement.rows)
            ).option
        except (TypeError, ValueError):
            option = None
    if option is None or option.information_value_score <= 0.0:
        blockers.add("POSITIVE_EXPECTED_EXPERIMENT_ECONOMICS_REQUIRED")

    body = {
        "schema": "CFBE-OMEGA-UNIVERSAL-CLOSURE-COURT-RECEIPT-V1",
        "status": "PASS_INTERNAL_DATA_READY" if not blockers else "HELD",
        "hard_gates_pass": not blockers,
        "promotion_allowed": False,
        "blockers": tuple(sorted(blockers)),
        "proof_refs": _clean_refs(
            (
                registry.receipt_sha256,
                *measurement.evidence_refs,
                foundry.receipt_sha256,
                *refs,
            )
        ),
    }
    return ClosureCourtResult(receipt_sha256=_sha(body), **body)


def plan_convergence_wave(
    matrix: Mapping[str, Any],
    registry: CapabilityRegistryReceipt,
    *,
    active_ids: Iterable[str] = (),
    completed_ids: Iterable[str] = (),
    roles: Mapping[str, str] | None = None,
    critical_regression_ids: Iterable[str] = (),
    measurement: MeasurementFabricReport | None = None,
    foundry: FoundryAssemblyReport | None = None,
) -> ClosureWaveReceipt:
    """Compose C03 current-state proof with C05 rather than building another scheduler."""

    projected = {item.capability_id: item for item in registry.projections}
    readiness_blockers = {
        str(row["id"]): (
            projected[str(row["id"])].blockers
            if str(row["id"]) in projected
            else ("CAPABILITY_PROJECTION_MISSING",)
        )
        for row in matrix["rows"]
        if str(row["id"]) not in projected or not projected[str(row["id"])].schedulable
    }
    if registry.state != "REGISTRY_READY":
        readiness_blockers.setdefault("C03", ("C03_REGISTRY_NOT_READY",))
    live_ready: set[str] = set()
    if measurement is not None and measurement.state == "MEASUREMENT_PACKET_READY":
        live_ready.add("C07")
    if foundry is not None and foundry.state == "DATA_READY":
        live_ready.add("C12")
    return plan_wave(
        matrix,
        active_ids=active_ids,
        completed_ids=completed_ids,
        roles=roles,
        live_ready_ids=live_ready,
        critical_regression_ids=critical_regression_ids,
        readiness_blockers=readiness_blockers,
    )


__all__ = [
    "PREREGISTRATION_PATH",
    "CapabilityProjection",
    "CapabilityRegistryReceipt",
    "ClosureCourtResult",
    "FailureGenomeObservation",
    "FoundryAssemblyReport",
    "assemble_foundry_readiness",
    "compile_preregistered_observation",
    "evaluate_universal_closure_court",
    "load_preregistration",
    "plan_convergence_wave",
    "project_capability_registry",
]
