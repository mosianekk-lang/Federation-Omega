from __future__ import annotations

"""Transition-aware facade over the Federation Living State world model.

The base model intentionally treats different fresh observations as potential
split-brain evidence. This extension adds one distinct semantic operation for a
lawful state transition: ``NODE_TRANSITIONED``. A transition names the exact
prior node fingerprint it supersedes and is replayed as immutable lineage.

Important boundary: ordinary ``NODE_OBSERVED`` events remain ordinary evidence
and can still produce split brain. Transition lineage cannot be used to hide a
stronger predecessor, move backward in time, cross node kind/matter scope, or
reference a predecessor that is absent from the local event history.
"""

from dataclasses import asdict
from typing import Any, Mapping, Sequence

from .model import LivingWorldModel as BaseLivingWorldModel
from .types import (
    AUTHORITY_CEILING,
    CausalEvidence,
    CausalStatus,
    ContextState,
    EdgeKind,
    FabricError,
    LearningClass,
    LearningEvent,
    NodeKind,
    ObservationEvent,
    ProofMaturity,
    RouteTelemetry,
    StateEstimate,
    WorldEdge,
    WorldNode,
    _PROOF_RANK,
    _authority_ok,
    _enum_value,
    _parse_time,
    digest,
)

EDPF_SCHEMA = "SOVARA_EDPF_LIVING_STATE_PREDICTION_ADAPTER_V1"
EDPF_OPEN_STATE = "PREDICTION_OPEN"
EDPF_RESOLVED_STATES = frozenset({
    "PREDICTION_RESOLVED_OCCURRED",
    "PREDICTION_RESOLVED_NOT_OCCURRED",
})


class TransitionAwareLivingWorldModel(BaseLivingWorldModel):
    """LivingWorldModel with explicit replayable state-transition lineage."""

    def __init__(self, *, authority_ceiling: str = AUTHORITY_CEILING) -> None:
        super().__init__(authority_ceiling=authority_ceiling)
        self._transition_parents: dict[str, dict[str, tuple[str, ...]]] = {}

    def transition_node(
        self,
        node: WorldNode,
        *,
        supersedes_fingerprint: str,
        transition_class: str = "EXPLICIT_STATE_TRANSITION",
    ) -> ObservationEvent:
        """Append a lawful state transition without erasing its predecessor.

        The predecessor stays in the immutable event journal. Split-brain
        reconciliation ignores it only when the selected state is a descendant
        of that exact fingerprint through explicit transition lineage.
        """
        node.validate()
        if not _authority_ok(node.provenance.authority_ceiling, self.authority_ceiling):
            raise FabricError("node authority exceeds model ceiling")
        if not str(supersedes_fingerprint).strip():
            raise FabricError("state transition requires predecessor fingerprint")
        if not str(transition_class).strip():
            raise FabricError("state transition requires transition_class")

        history = self._node_history.get(node.node_id, [])
        predecessor = next(
            (item for item in history if item.fingerprint == supersedes_fingerprint),
            None,
        )
        if predecessor is None:
            raise FabricError("state transition predecessor not found")
        if node.fingerprint == predecessor.fingerprint:
            raise FabricError("state transition replacement must differ from predecessor")
        if any(item.fingerprint == node.fingerprint for item in history):
            raise FabricError("state transition replacement already observed")
        if node.kind != predecessor.kind:
            raise FabricError("state transition cannot change node kind")
        if node.provenance.matter_scope != predecessor.provenance.matter_scope:
            raise FabricError("state transition cannot cross matter scope")
        if node.state == predecessor.state:
            raise FabricError("state transition requires a changed state")
        if _parse_time(node.provenance.observed_at) <= _parse_time(predecessor.provenance.observed_at):
            raise FabricError("state transition must be later than predecessor")
        if node.provenance.rank < predecessor.provenance.rank:
            raise FabricError("state transition cannot supersede stronger proof with weaker proof")

        parents = self._transition_parents.setdefault(node.node_id, {})
        existing = parents.get(node.fingerprint)
        lineage = (predecessor.fingerprint,)
        if existing is not None and existing != lineage:
            raise FabricError("state transition lineage collision")
        parents[node.fingerprint] = lineage
        self._node_history.setdefault(node.node_id, []).append(node)
        return self._append_event(
            "NODE_TRANSITIONED",
            node.node_id,
            {
                "node": asdict(node),
                "supersedes_fingerprint": predecessor.fingerprint,
                "transition_class": transition_class,
            },
        )

    def _lineage_supersedes(self, node_id: str, descendant: str, ancestor: str) -> bool:
        if descendant == ancestor:
            return False
        graph = self._transition_parents.get(node_id, {})
        stack = list(graph.get(descendant, ()))
        seen: set[str] = set()
        while stack:
            current = stack.pop()
            if current == ancestor:
                return True
            if current in seen:
                continue
            seen.add(current)
            stack.extend(graph.get(current, ()))
        return False

    def _edpf_transition_predecessor(self, node: WorldNode) -> WorldNode | None:
        """Recognize only the admitted EDPF OPEN -> RESOLVED lifecycle.

        This binding is intentionally narrow. Any other different-state node is
        handled by the base observation path and therefore remains eligible for
        split-brain detection.
        """
        payload = node.payload
        if (
            node.kind != NodeKind.EXPERIMENT
            or node.provenance.source_class != "EDPF_PROSPECTIVE_OUTCOME"
            or node.state not in EDPF_RESOLVED_STATES
            or payload.get("schema") != EDPF_SCHEMA
            or payload.get("prospective_capture") is not True
        ):
            return None
        if not isinstance(payload.get("resolution"), Mapping):
            raise FabricError("EDPF resolved transition requires resolution payload")

        candidates = [
            item
            for item in self._node_history.get(node.node_id, [])
            if item.kind == NodeKind.EXPERIMENT
            and item.state == EDPF_OPEN_STATE
            and item.provenance.source_class == "EDPF_PROSPECTIVE_PREDICTION"
            and item.provenance.matter_scope == node.provenance.matter_scope
            and item.payload.get("schema") == EDPF_SCHEMA
            and item.payload.get("prospective_capture") is True
            and item.payload.get("prediction") == payload.get("prediction")
            and item.payload.get("mission_id") == payload.get("mission_id")
            and item.payload.get("mission_snapshot_digest") == payload.get("mission_snapshot_digest")
        ]
        if len(candidates) != 1:
            raise FabricError("EDPF lifecycle transition predecessor is missing or ambiguous")
        return candidates[0]

    def observe_node(self, node: WorldNode) -> ObservationEvent:
        predecessor = self._edpf_transition_predecessor(node)
        if predecessor is not None:
            return self.transition_node(
                node,
                supersedes_fingerprint=predecessor.fingerprint,
                transition_class="EDPF_PROSPECTIVE_PREDICTION_RESOLUTION",
            )
        return BaseLivingWorldModel.observe_node(self, node)

    def state_estimate(self, node_id: str, *, now: str) -> StateEstimate:
        history = self._node_history.get(node_id, [])
        if not history:
            return StateEstimate(node_id, "UNKNOWN", False, ProofMaturity.UNKNOWN.value, 0, 0.0, "", "", "", False, ())
        fresh = [item for item in history if item.provenance.fresh_at(now)]
        pool = fresh if fresh else history
        ranked = sorted(
            pool,
            key=lambda item: (
                item.provenance.rank,
                _parse_time(item.provenance.observed_at),
                item.provenance.confidence,
                item.fingerprint,
            ),
            reverse=True,
        )
        best = ranked[0]
        best_time = _parse_time(best.provenance.observed_at)
        competing = [
            item for item in ranked[1:]
            if item.state != best.state
            and not self._lineage_supersedes(node_id, best.fingerprint, item.fingerprint)
            and abs((_parse_time(item.provenance.observed_at) - best_time).total_seconds())
                <= min(item.provenance.ttl_seconds, best.provenance.ttl_seconds)
            and item.provenance.rank >= _PROOF_RANK[ProofMaturity.SOURCE_READBACK]
            and item.provenance.confidence >= 0.5
        ]
        return StateEstimate(
            node_id=node_id,
            state=best.state if fresh else "STALE:" + best.state,
            fresh=bool(fresh),
            proof_maturity=best.provenance.proof_maturity.value,
            proof_rank=best.provenance.rank,
            confidence=float(best.provenance.confidence),
            source_ref=best.provenance.source_ref,
            proof_ref=best.provenance.proof_ref,
            observed_at=best.provenance.observed_at,
            split_brain=bool(competing),
            alternatives=tuple(sorted({item.state for item in competing})),
        )

    @classmethod
    def replay(
        cls,
        events: Sequence[Mapping[str, Any]],
        *,
        authority_ceiling: str = AUTHORITY_CEILING,
    ) -> "TransitionAwareLivingWorldModel":
        """Replay old and transition-aware journals without reclassifying history."""
        model = cls(authority_ceiling=authority_ceiling)
        expected_prior = "GENESIS"
        for expected_sequence, raw in enumerate(events, 1):
            event = ObservationEvent(
                sequence=int(raw["sequence"]),
                event_type=str(raw["event_type"]),
                object_id=str(raw["object_id"]),
                payload=dict(raw["payload"]),
                event_digest=str(raw["event_digest"]),
                prior_digest=str(raw["prior_digest"]),
            )
            body = {
                "sequence": event.sequence,
                "event_type": event.event_type,
                "object_id": event.object_id,
                "payload": dict(event.payload),
                "prior_digest": event.prior_digest,
            }
            if event.sequence != expected_sequence:
                raise FabricError("event journal sequence gap")
            if event.prior_digest != expected_prior:
                raise FabricError("event journal prior-digest mismatch")
            if digest(body) != event.event_digest:
                raise FabricError("event journal digest mismatch")

            if event.event_type in {"NODE_OBSERVED", "NODE_TRANSITIONED"}:
                data = dict(event.payload["node"])
                data["kind"] = NodeKind(_enum_value(data["kind"]))
                data["provenance"] = cls._provenance_from(data["provenance"])
                node = WorldNode(**data)
                if event.event_type == "NODE_OBSERVED":
                    # Preserve old journals exactly: do not retroactively turn a
                    # historical observation into a transition event.
                    generated = BaseLivingWorldModel.observe_node(model, node)
                else:
                    generated = model.transition_node(
                        node,
                        supersedes_fingerprint=str(event.payload["supersedes_fingerprint"]),
                        transition_class=str(event.payload.get("transition_class", "EXPLICIT_STATE_TRANSITION")),
                    )
            elif event.event_type == "EDGE_OBSERVED":
                data = dict(event.payload["edge"])
                data["kind"] = EdgeKind(_enum_value(data["kind"]))
                data["causal_status"] = CausalStatus(_enum_value(data.get("causal_status", CausalStatus.NONE.value)))
                data["causal_evidence"] = CausalEvidence(**dict(data.get("causal_evidence", {})))
                data["provenance"] = cls._provenance_from(data["provenance"])
                generated = model.observe_edge(WorldEdge(**data))
            elif event.event_type == "ROUTE_TELEMETRY":
                data = dict(event.payload["sample"])
                data["failure_domains"] = tuple(data.get("failure_domains", ()))
                generated = model.observe_route_telemetry(RouteTelemetry(**data))
            elif event.event_type == "CONTEXT_OBSERVED":
                data = dict(event.payload["context"])
                for key in (
                    "verified_facts", "adverse_evidence", "contradictions", "gaps",
                    "blockers", "decisions", "source_refs",
                ):
                    data[key] = tuple(data.get(key, ()))
                generated = model.observe_context(ContextState(**data))
            elif event.event_type == "LEARNING_OBSERVED":
                data = dict(event.payload["learning"])
                data["learning_class"] = LearningClass(_enum_value(data["learning_class"]))
                data["proof_refs"] = tuple(data.get("proof_refs", ()))
                generated = model.observe_learning(LearningEvent(**data))
            elif event.event_type == "BENCHMARK_OBSERVED":
                generated = model.observe_benchmark(
                    event.object_id,
                    str(event.payload["observed_at"]),
                    str(event.payload["proof_ref"]),
                )
            elif event.event_type == "OMEGA4_METRICS":
                generated = model._append_event("OMEGA4_METRICS", event.object_id, dict(event.payload))
            else:
                raise FabricError(f"unknown event type during replay: {event.event_type}")

            if generated.event_digest != event.event_digest:
                raise FabricError("semantic replay drift detected")
            expected_prior = event.event_digest
        if not model.verify_event_chain():
            raise FabricError("replayed event chain failed verification")
        return model


__all__ = ["TransitionAwareLivingWorldModel"]
