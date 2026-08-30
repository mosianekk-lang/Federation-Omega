from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from .creative_graph import CreativeGraph
from .genome import CreativeMissionGenome
from .taste import TasteMemory


class ProducerError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProductionStep:
    step_id: str
    action: str
    inputs: tuple[str, ...]
    depends_on: tuple[str, ...]
    approval_required: bool
    provider_execution_allowed: bool = False


@dataclass(frozen=True, slots=True)
class ProductionPlan:
    schema: str
    mission_id: str
    objective: str
    content_class: str
    privacy_class: str
    rights_state: str
    owner_approval_required: bool
    graph_version: str
    graph_sha256: str
    taste_state_sha256: str
    taste_preferences: tuple[tuple[str, str], ...]
    steps: tuple[ProductionStep, ...]
    target_channels: tuple[str, ...]
    authority_inherited: bool
    provider_execution_performed: bool
    external_effect_performed: bool
    plan_sha256: str


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _step_record(step: ProductionStep) -> dict[str, object]:
    return {
        "step_id": step.step_id,
        "action": step.action,
        "inputs": list(step.inputs),
        "depends_on": list(step.depends_on),
        "approval_required": step.approval_required,
        "provider_execution_allowed": step.provider_execution_allowed,
    }


class ProducerCompiler:
    """Compile intent, graph state and owner taste into a provider-disabled DAG."""

    def compile(
        self,
        *,
        mission: CreativeMissionGenome,
        graph: CreativeGraph,
        taste: TasteMemory,
    ) -> ProductionPlan:
        if graph.graph_id != mission.mission_id:
            raise ProducerError("graph_id must match mission_id")

        taste_receipt = taste.receipt()
        preferences = tuple(
            (preference.dimension, preference.value)
            for preference in taste.preferences()
        )
        steps: list[ProductionStep] = [
            ProductionStep(
                step_id="01-interpret-intent",
                action="INTERPRET_OWNER_INTENT",
                inputs=(mission.objective,),
                depends_on=(),
                approval_required=False,
            ),
            ProductionStep(
                step_id="02-bind-creative-state",
                action="BIND_GRAPH_TASTE_AND_POLICY_STATE",
                inputs=(
                    graph.head_version,
                    taste_receipt.state_sha256,
                    mission.content_class.value,
                    mission.privacy_class.value,
                    mission.rights_state.value,
                    (
                        "OWNER_APPROVAL_REQUIRED"
                        if mission.owner_approval_required
                        else "OWNER_APPROVAL_NOT_REQUIRED"
                    ),
                ),
                depends_on=("01-interpret-intent",),
                approval_required=False,
            ),
        ]

        modality_steps: list[str] = []
        for index, modality in enumerate(mission.required_modalities, start=1):
            step_id = f"10-{index:02d}-prepare-{modality}"
            modality_steps.append(step_id)
            steps.append(
                ProductionStep(
                    step_id=step_id,
                    action=f"PREPARE_{modality.upper()}_WORK_PACKET",
                    inputs=(modality, graph.state_sha256()),
                    depends_on=("02-bind-creative-state",),
                    approval_required=False,
                )
            )

        package_dependencies = tuple(modality_steps) or ("02-bind-creative-state",)
        steps.append(
            ProductionStep(
                step_id="80-package-preview",
                action="COMPILE_REVIEWABLE_PREVIEW_PACKAGE",
                inputs=mission.target_channels,
                depends_on=package_dependencies,
                approval_required=False,
            )
        )
        steps.append(
            ProductionStep(
                step_id="90-owner-release-gate",
                action="REQUEST_OWNER_RELEASE_DECISION",
                inputs=mission.target_channels,
                depends_on=("80-package-preview",),
                approval_required=True,
            )
        )

        self._validate_dag(steps)
        base = {
            "schema": "SOVARA_SC_PRODUCER_PLAN_V1",
            "mission_id": mission.mission_id,
            "objective": mission.objective,
            "content_class": mission.content_class.value,
            "privacy_class": mission.privacy_class.value,
            "rights_state": mission.rights_state.value,
            "owner_approval_required": mission.owner_approval_required,
            "graph_version": graph.head_version,
            "graph_sha256": graph.state_sha256(),
            "taste_state_sha256": taste_receipt.state_sha256,
            "taste_preferences": [list(item) for item in preferences],
            "steps": [_step_record(step) for step in steps],
            "target_channels": list(mission.target_channels),
            "authority_inherited": False,
            "provider_execution_performed": False,
            "external_effect_performed": False,
        }
        return ProductionPlan(
            schema=base["schema"],
            mission_id=mission.mission_id,
            objective=mission.objective,
            content_class=mission.content_class.value,
            privacy_class=mission.privacy_class.value,
            rights_state=mission.rights_state.value,
            owner_approval_required=mission.owner_approval_required,
            graph_version=graph.head_version,
            graph_sha256=graph.state_sha256(),
            taste_state_sha256=taste_receipt.state_sha256,
            taste_preferences=preferences,
            steps=tuple(steps),
            target_channels=mission.target_channels,
            authority_inherited=False,
            provider_execution_performed=False,
            external_effect_performed=False,
            plan_sha256=sha256(_stable_json(base).encode("utf-8")).hexdigest(),
        )

    @staticmethod
    def _validate_dag(steps: list[ProductionStep]) -> None:
        ids = [step.step_id for step in steps]
        if len(ids) != len(set(ids)):
            raise ProducerError("duplicate step_id")
        known: set[str] = set()
        for step in steps:
            if any(dependency not in known for dependency in step.depends_on):
                raise ProducerError("dependency must reference an earlier step")
            if step.provider_execution_allowed:
                raise ProducerError("SC-PRODUCER V1 is provider-disabled")
            known.add(step.step_id)
