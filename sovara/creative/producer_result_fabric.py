from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from benchmarking.cfbe_omega.mission_result_fabric_adapter_v1 import (
    MissionResultIdentity,
    compile_mission_result_identity,
)
from benchmarking.cfbe_omega.mission_result_index_v1 import DurableMissionResultIndex

from .creative_graph import CreativeGraph
from .genome import CreativeMissionGenome
from .mission_ir_adapter import compile_creative_mission_ir
from .producer import ProducerCompiler, ProductionPlan, ProductionStep
from .taste import TasteMemory


_PLAN_SCHEMA = "SOVARA_SC_PRODUCER_PLAN_V1"
_FABRIC_SCHEMA = "SOVARA_SC_PRODUCER_RESULT_FABRIC_V1"
_CACHE_KEY = re.compile(r"^[0-9a-f]{64}$")


class ProducerResultFabricError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProducerPlanFabricResult:
    schema: str
    state: str
    reuse: bool
    cache_key: str
    result_ref: str
    result_sha256: str
    proof_refs: tuple[str, ...]
    plan: ProductionPlan | None
    provider_effect_authorized: bool = False
    authority_inherited: bool = False
    external_effect_performed: bool = False


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _step_mapping(step: ProductionStep) -> dict[str, object]:
    return {
        "step_id": step.step_id,
        "action": step.action,
        "inputs": list(step.inputs),
        "depends_on": list(step.depends_on),
        "approval_required": step.approval_required,
        "provider_execution_allowed": step.provider_execution_allowed,
    }


def _plan_base(plan: ProductionPlan) -> dict[str, object]:
    return {
        "schema": plan.schema,
        "mission_id": plan.mission_id,
        "objective": plan.objective,
        "content_class": plan.content_class,
        "privacy_class": plan.privacy_class,
        "rights_state": plan.rights_state,
        "owner_approval_required": plan.owner_approval_required,
        "graph_version": plan.graph_version,
        "graph_sha256": plan.graph_sha256,
        "taste_state_sha256": plan.taste_state_sha256,
        "taste_preferences": [list(item) for item in plan.taste_preferences],
        "steps": [_step_mapping(step) for step in plan.steps],
        "target_channels": list(plan.target_channels),
        "authority_inherited": plan.authority_inherited,
        "provider_execution_performed": plan.provider_execution_performed,
        "external_effect_performed": plan.external_effect_performed,
    }


def _plan_document(plan: ProductionPlan) -> dict[str, object]:
    return {**_plan_base(plan), "plan_sha256": plan.plan_sha256}


def _canonical_plan_bytes(plan: ProductionPlan) -> bytes:
    return (_stable_json(_plan_document(plan)) + "\n").encode("utf-8")


def _decode_plan(raw: bytes) -> ProductionPlan:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ProducerResultFabricError("SOVARA_PRODUCER_PLAN_ARTIFACT_INVALID_JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema") != _PLAN_SCHEMA:
        raise ProducerResultFabricError("SOVARA_PRODUCER_PLAN_ARTIFACT_SCHEMA_MISMATCH")
    try:
        steps = tuple(
            ProductionStep(
                step_id=str(item["step_id"]),
                action=str(item["action"]),
                inputs=tuple(str(value) for value in item["inputs"]),
                depends_on=tuple(str(value) for value in item["depends_on"]),
                approval_required=bool(item["approval_required"]),
                provider_execution_allowed=bool(item["provider_execution_allowed"]),
            )
            for item in payload["steps"]
        )
        plan = ProductionPlan(
            schema=str(payload["schema"]),
            mission_id=str(payload["mission_id"]),
            objective=str(payload["objective"]),
            content_class=str(payload["content_class"]),
            privacy_class=str(payload["privacy_class"]),
            rights_state=str(payload["rights_state"]),
            owner_approval_required=bool(payload["owner_approval_required"]),
            graph_version=str(payload["graph_version"]),
            graph_sha256=str(payload["graph_sha256"]),
            taste_state_sha256=str(payload["taste_state_sha256"]),
            taste_preferences=tuple(
                (str(item[0]), str(item[1])) for item in payload["taste_preferences"]
            ),
            steps=steps,
            target_channels=tuple(str(value) for value in payload["target_channels"]),
            authority_inherited=bool(payload["authority_inherited"]),
            provider_execution_performed=bool(payload["provider_execution_performed"]),
            external_effect_performed=bool(payload["external_effect_performed"]),
            plan_sha256=str(payload["plan_sha256"]),
        )
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise ProducerResultFabricError("SOVARA_PRODUCER_PLAN_ARTIFACT_INVALID_SHAPE") from exc

    if plan.authority_inherited or plan.provider_execution_performed or plan.external_effect_performed:
        raise ProducerResultFabricError("SOVARA_PRODUCER_PLAN_ARTIFACT_EFFECT_BOUNDARY_VIOLATION")
    ProducerCompiler._validate_dag(list(plan.steps))
    expected = _sha_bytes(_stable_json(_plan_base(plan)).encode("utf-8"))
    if plan.plan_sha256 != expected:
        raise ProducerResultFabricError("SOVARA_PRODUCER_PLAN_ARTIFACT_HASH_MISMATCH")
    if not plan.steps or plan.steps[-1].action != "REQUEST_OWNER_RELEASE_DECISION" or not plan.steps[-1].approval_required:
        raise ProducerResultFabricError("SOVARA_PRODUCER_PLAN_ARTIFACT_RELEASE_GATE_MISSING")
    return plan


def _fsync_dir(path: Path) -> None:
    if os.name == "nt":
        return
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_once_verified(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != data:
            raise ProducerResultFabricError("SOVARA_PRODUCER_PLAN_ARTIFACT_COLLISION")
        return
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_dir(path.parent)
        if path.read_bytes() != data:
            raise ProducerResultFabricError("SOVARA_PRODUCER_PLAN_ARTIFACT_READBACK_MISMATCH")
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def compile_producer_result_identity(
    *,
    mission: CreativeMissionGenome,
    graph: CreativeGraph,
    taste: TasteMemory,
    source_frontier: str,
    fresh_until: str,
) -> MissionResultIdentity:
    taste_receipt = taste.receipt()
    mission_ir = compile_creative_mission_ir(
        mission,
        source_frontier=source_frontier,
        outcome_contract="One deterministic provider-disabled SOVARA Producer plan.",
        proof_requirements=("PRODUCER_PLAN_HASH", "GRAPH_STATE_HASH", "TASTE_STATE_HASH"),
        effect_class="NO_EFFECT",
        rollback_required=False,
    )
    return compile_mission_result_identity(
        mission_ir,
        step_id="sovara-producer-plan-v1",
        input_identity={
            "graph_version": graph.head_version,
            "graph_sha256": graph.state_sha256(),
            "taste_state_sha256": taste_receipt.state_sha256,
        },
        policy_identity={
            "content_class": mission.content_class.value,
            "privacy_class": mission.privacy_class.value,
            "rights_state": mission.rights_state.value,
            "owner_approval_required": mission.owner_approval_required,
            "required_modalities": list(mission.required_modalities),
            "target_channels": list(mission.target_channels),
            "producer_schema": _PLAN_SCHEMA,
            "fabric_schema": _FABRIC_SCHEMA,
        },
        environment_identity={
            "runtime": "PYTHON_STDLIB",
            "producer_compiler": "SC-PRODUCER-V1",
            "artifact_protocol": "LOCAL_ATOMIC_WRITE_ONCE_V1",
        },
        proof_scope="SOVARA_SC_PRODUCER_RESULT_FABRIC_V1",
        fresh_until=fresh_until,
        step_effect_class="NO_EFFECT",
    )


class DurableProducerPlanResultFabric:
    """Vertical SOVARA binding over the universal durable Result Index.

    The Result Index remains metadata-only. Canonical Producer plan bytes live in a
    local write-once artifact path addressed by the Result Fabric cache key. Reuse
    requires exact mission/graph/taste/policy/source identity plus artifact readback.
    No provider call, publication, spend, authority expansion or external effect is
    performed by this class.
    """

    def __init__(self, root: str | Path, *, compiler: ProducerCompiler | None = None) -> None:
        self.root = Path(root)
        self.index = DurableMissionResultIndex(self.root / "result-index.jsonl")
        self.compiler = compiler or ProducerCompiler()

    def _artifact_path(self, cache_key: str) -> Path:
        if not _CACHE_KEY.fullmatch(cache_key):
            raise ProducerResultFabricError("SOVARA_PRODUCER_RESULT_CACHE_KEY_INVALID")
        return self.root / "artifacts" / "producer-plans" / f"{cache_key}.json"

    def _read_plan(self, result_ref: str, *, expected_sha256: str) -> ProductionPlan:
        expected_prefix = "artifacts/producer-plans/"
        if not result_ref.startswith(expected_prefix) or not result_ref.endswith(".json"):
            raise ProducerResultFabricError("SOVARA_PRODUCER_PLAN_RESULT_REF_INVALID")
        relative = Path(result_ref)
        if relative.is_absolute() or ".." in relative.parts:
            raise ProducerResultFabricError("SOVARA_PRODUCER_PLAN_RESULT_REF_INVALID")
        path = self.root / relative
        if not path.exists() or path.is_symlink() or not path.is_file():
            raise ProducerResultFabricError("SOVARA_PRODUCER_PLAN_ARTIFACT_MISSING")
        plan = _decode_plan(path.read_bytes())
        if plan.plan_sha256 != expected_sha256:
            raise ProducerResultFabricError("SOVARA_PRODUCER_PLAN_RESULT_INDEX_HASH_MISMATCH")
        return plan

    def compile_or_reuse(
        self,
        *,
        mission: CreativeMissionGenome,
        graph: CreativeGraph,
        taste: TasteMemory,
        source_frontier: str,
        fresh_until: str,
        now: str,
    ) -> ProducerPlanFabricResult:
        if graph.graph_id != mission.mission_id:
            raise ProducerResultFabricError("SOVARA_PRODUCER_GRAPH_MISSION_IDENTITY_MISMATCH")
        identity = compile_producer_result_identity(
            mission=mission,
            graph=graph,
            taste=taste,
            source_frontier=source_frontier,
            fresh_until=fresh_until,
        )
        lookup = self.index.lookup(identity, now=now)
        if lookup.state == "HOLD_FRESHNESS_EXPIRED":
            return ProducerPlanFabricResult(
                schema=_FABRIC_SCHEMA,
                state=lookup.state,
                reuse=False,
                cache_key=identity.cache_key,
                result_ref="",
                result_sha256="",
                proof_refs=(),
                plan=None,
            )
        if lookup.state == "HIT":
            plan = self._read_plan(lookup.result_ref, expected_sha256=lookup.result_sha256)
            return ProducerPlanFabricResult(
                schema=_FABRIC_SCHEMA,
                state="HIT",
                reuse=True,
                cache_key=identity.cache_key,
                result_ref=lookup.result_ref,
                result_sha256=lookup.result_sha256,
                proof_refs=lookup.proof_refs,
                plan=plan,
            )
        if lookup.state != "MISS":
            raise ProducerResultFabricError(f"SOVARA_PRODUCER_RESULT_UNEXPECTED_STATE:{lookup.state}")

        plan = self.compiler.compile(mission=mission, graph=graph, taste=taste)
        artifact_path = self._artifact_path(identity.cache_key)
        artifact_bytes = _canonical_plan_bytes(plan)
        _write_once_verified(artifact_path, artifact_bytes)
        relative_ref = artifact_path.relative_to(self.root).as_posix()
        proof_refs = (
            f"sovara:producer-plan:{plan.plan_sha256}",
            f"sovara:graph:{plan.graph_sha256}",
            f"sovara:taste:{plan.taste_state_sha256}",
        )
        recorded = self.index.record(
            identity,
            result_ref=relative_ref,
            result_sha256=plan.plan_sha256,
            proof_refs=proof_refs,
            recorded_at=now,
            now=now,
        )
        if recorded.state != "RECORDED":
            raise ProducerResultFabricError(f"SOVARA_PRODUCER_RESULT_RECORD_FAILED:{recorded.state}")
        readback = self._read_plan(relative_ref, expected_sha256=plan.plan_sha256)
        return ProducerPlanFabricResult(
            schema=_FABRIC_SCHEMA,
            state="RECORDED",
            reuse=False,
            cache_key=identity.cache_key,
            result_ref=relative_ref,
            result_sha256=plan.plan_sha256,
            proof_refs=tuple(sorted(proof_refs)),
            plan=readback,
        )
