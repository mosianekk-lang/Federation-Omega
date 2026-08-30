from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping

from .creative_graph import CreativeGraph, CreativeNodeKind, GraphConflictError
from .producer import ProductionPlan
from .taste import TasteMemory


class RippleError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RippleReceipt:
    schema: str
    graph_id: str
    previous_graph_version: str
    new_graph_version: str
    changed_node_ids: tuple[str, ...]
    invalidated_node_ids: tuple[str, ...]
    blocked_locked_node_ids: tuple[str, ...]
    regeneration_step_ids: tuple[str, ...]
    preserved_step_ids: tuple[str, ...]
    taste_conflict_dimensions: tuple[str, ...]
    owner_review_required: bool
    authority_inherited: bool
    provider_execution_performed: bool
    external_effect_performed: bool
    receipt_sha256: str


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class RippleCompiler:
    """Apply one owner correction and compile its minimum safe regeneration ripple."""

    def apply(
        self,
        *,
        graph: CreativeGraph,
        plan: ProductionPlan,
        taste: TasteMemory,
        expected_graph_version: str,
        node_id: str,
        patch: Mapping[str, Any],
    ) -> RippleReceipt:
        if plan.mission_id != graph.graph_id:
            raise RippleError("production plan mission does not match graph")
        if plan.graph_version != expected_graph_version:
            raise GraphConflictError("production plan is stale for the requested correction")
        if graph.head_version != expected_graph_version:
            raise GraphConflictError("graph head changed before correction")
        if not patch:
            raise RippleError("correction patch is required")

        impact = graph.impact((node_id,))
        affected_nodes = (node_id,) + impact.invalidated_node_ids
        modalities = self._affected_modalities(graph, affected_nodes)
        regeneration = self._regeneration_steps(plan, modalities)
        all_step_ids = tuple(step.step_id for step in plan.steps)
        preserved = tuple(step_id for step_id in all_step_ids if step_id not in regeneration)
        conflicts = self._taste_conflicts(taste, patch)

        mutation = graph.update_node(
            expected_version=expected_graph_version,
            node_id=node_id,
            patch=patch,
        )
        owner_review = bool(mutation.blocked_locked_node_ids or conflicts)
        base = {
            "schema": "SOVARA_SC_RIPPLE_RECEIPT_V1",
            "graph_id": graph.graph_id,
            "previous_graph_version": expected_graph_version,
            "new_graph_version": mutation.version_id,
            "changed_node_ids": list(mutation.changed_node_ids),
            "invalidated_node_ids": list(mutation.invalidated_node_ids),
            "blocked_locked_node_ids": list(mutation.blocked_locked_node_ids),
            "regeneration_step_ids": list(regeneration),
            "preserved_step_ids": list(preserved),
            "taste_conflict_dimensions": list(conflicts),
            "owner_review_required": owner_review,
            "authority_inherited": False,
            "provider_execution_performed": False,
            "external_effect_performed": False,
        }
        return RippleReceipt(
            schema=base["schema"],
            graph_id=graph.graph_id,
            previous_graph_version=expected_graph_version,
            new_graph_version=mutation.version_id,
            changed_node_ids=mutation.changed_node_ids,
            invalidated_node_ids=mutation.invalidated_node_ids,
            blocked_locked_node_ids=mutation.blocked_locked_node_ids,
            regeneration_step_ids=regeneration,
            preserved_step_ids=preserved,
            taste_conflict_dimensions=conflicts,
            owner_review_required=owner_review,
            authority_inherited=False,
            provider_execution_performed=False,
            external_effect_performed=False,
            receipt_sha256=sha256(_stable_json(base).encode("utf-8")).hexdigest(),
        )

    @staticmethod
    def _affected_modalities(graph: CreativeGraph, node_ids: tuple[str, ...]) -> tuple[str, ...]:
        modalities: set[str] = set()
        broad = False
        for node_id in node_ids:
            node = graph.node(node_id)
            raw = node.attributes.get("modality")
            if isinstance(raw, str) and raw.strip():
                modalities.add(raw.strip().lower())
            elif node.kind in {CreativeNodeKind.SHOT, CreativeNodeKind.EDIT}:
                modalities.add("video")
            elif node.kind is CreativeNodeKind.ASSET:
                broad = True
            elif node.kind in {
                CreativeNodeKind.CONCEPT,
                CreativeNodeKind.WORLD,
                CreativeNodeKind.CHARACTER,
                CreativeNodeKind.SCENE,
            }:
                broad = True
        return () if broad else tuple(sorted(modalities))

    @staticmethod
    def _regeneration_steps(plan: ProductionPlan, modalities: tuple[str, ...]) -> tuple[str, ...]:
        modality_steps = [
            step
            for step in plan.steps
            if step.action.startswith("PREPARE_") and step.action.endswith("_WORK_PACKET")
        ]
        if modalities:
            selected = [
                step.step_id
                for step in modality_steps
                if step.action.removeprefix("PREPARE_").removesuffix("_WORK_PACKET").lower()
                in modalities
            ]
        else:
            selected = [step.step_id for step in modality_steps]
        selected.extend(
            step.step_id
            for step in plan.steps
            if step.step_id in {"80-package-preview", "90-owner-release-gate"}
        )
        return tuple(selected)

    @staticmethod
    def _taste_conflicts(taste: TasteMemory, patch: Mapping[str, Any]) -> tuple[str, ...]:
        conflicts: list[str] = []
        for dimension, proposed in patch.items():
            preference = taste.preference(str(dimension))
            if preference is not None and str(proposed) != preference.value:
                conflicts.append(str(dimension))
        return tuple(sorted(conflicts))
