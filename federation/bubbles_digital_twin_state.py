"""Bubbles digital-twin state adapter over Federation Living State.

This module does not create a second memory database. It maps owner preferences,
mission episodes and owner-burden observations into the existing event-sourced
LivingWorldModel and seals them through LivingStateStore's durable snapshot and
semantic readback path.

No private owner data is embedded here. Callers supply observations and proof
references at runtime. Source presence is not proof of a persistent production
digital twin; durable/provider/outcome maturity remains evidence-gated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from federation.living_state.model import LivingWorldModel
from federation.living_state.store import LivingStateStore, StoreReceipt
from federation.living_state.types import (
    NodeKind,
    ProofMaturity,
    Provenance,
    WorldNode,
    digest,
)


DIGITAL_TWIN_FABRIC_ID = "BUBBLES_DIGITAL_TWIN"
PREFERENCE_PREFIX = "context:owner-preference:"
MISSION_PREFIX = "mission:"
BURDEN_PREFIX = "evidence:owner-burden:"


def _nonnegative(value: float, label: str) -> float:
    number = float(value)
    if number < 0.0:
        raise ValueError(f"{label}_NON_NEGATIVE_REQUIRED")
    return number


def _preference_id(key: str) -> str:
    normalized = " ".join(str(key).split())
    if not normalized:
        raise ValueError("OWNER_PREFERENCE_KEY_REQUIRED")
    return PREFERENCE_PREFIX + digest({"key": normalized})[:20]


def _burden_id(mission_id: str, observed_at: str, proof_ref: str) -> str:
    if not str(mission_id).strip():
        raise ValueError("MISSION_ID_REQUIRED")
    return BURDEN_PREFIX + digest(
        {"mission_id": mission_id, "observed_at": observed_at, "proof_ref": proof_ref}
    )[:20]


@dataclass(frozen=True, slots=True)
class OwnerPreferenceObservation:
    key: str
    value: Any
    observed_at: str
    proof_ref: str
    confidence: float = 1.0
    ttl_seconds: int = 31_536_000
    matter_scope: str = "GLOBAL"
    sensitivity: str = "OWNER_PRIVATE"


@dataclass(frozen=True, slots=True)
class MissionEpisodeObservation:
    mission_id: str
    objective: str
    state: str
    observed_at: str
    proof_ref: str
    outcome_ref: str = ""
    accepted: bool | None = None
    cycle_time_seconds: float = 0.0
    owner_intervention_seconds: float = 0.0
    clarification_count: int = 0
    matter_scope: str = "GLOBAL"


@dataclass(frozen=True, slots=True)
class OwnerBurdenObservation:
    mission_id: str
    observed_at: str
    proof_ref: str
    intervention_seconds: float
    clarification_count: int = 0
    correction_count: int = 0
    matter_scope: str = "GLOBAL"


@dataclass(frozen=True, slots=True)
class DigitalTwinSealReceipt:
    fabric_id: str
    event_count: int
    event_head_digest: str
    snapshot_sha256: str
    store_readback_verified: bool
    preference_count: int
    mission_count: int
    burden_observation_count: int
    external_effects: int

    @property
    def receipt_sha256(self) -> str:
        return digest(
            {
                "fabric_id": self.fabric_id,
                "event_count": self.event_count,
                "event_head_digest": self.event_head_digest,
                "snapshot_sha256": self.snapshot_sha256,
                "store_readback_verified": self.store_readback_verified,
                "preference_count": self.preference_count,
                "mission_count": self.mission_count,
                "burden_observation_count": self.burden_observation_count,
                "external_effects": self.external_effects,
            }
        )


class BubblesDigitalTwinState:
    """Thin Bubbles projection over the canonical Living State model."""

    def __init__(self, model: LivingWorldModel | None = None) -> None:
        self.model = model or LivingWorldModel()

    @staticmethod
    def _provenance(
        *,
        source_ref: str,
        proof_ref: str,
        observed_at: str,
        confidence: float,
        ttl_seconds: int,
        matter_scope: str,
        sensitivity: str,
        source_class: str,
    ) -> Provenance:
        if not str(proof_ref).strip():
            raise ValueError("DIGITAL_TWIN_PROOF_REF_REQUIRED")
        if not 0.0 <= float(confidence) <= 1.0:
            raise ValueError("DIGITAL_TWIN_CONFIDENCE_OUT_OF_RANGE")
        return Provenance(
            source_ref=source_ref,
            proof_ref=proof_ref,
            observed_at=observed_at,
            proof_maturity=ProofMaturity.SOURCE_READBACK,
            ttl_seconds=int(ttl_seconds),
            confidence=float(confidence),
            matter_scope=matter_scope,
            sensitivity=sensitivity,
            source_class=source_class,
        ).validate()

    def observe_preference(self, item: OwnerPreferenceObservation) -> WorldNode:
        key = " ".join(str(item.key).split())
        node = WorldNode(
            node_id=_preference_id(key),
            kind=NodeKind.CONTEXT,
            label=key,
            state="ACTIVE",
            payload={"preference_key": key, "preference_value": item.value},
            provenance=self._provenance(
                source_ref="BUBBLES_OWNER_PREFERENCE_OBSERVATION",
                proof_ref=item.proof_ref,
                observed_at=item.observed_at,
                confidence=item.confidence,
                ttl_seconds=item.ttl_seconds,
                matter_scope=item.matter_scope,
                sensitivity=item.sensitivity,
                source_class="OWNER_PREFERENCE",
            ),
        ).validate()
        self.model.observe_node(node)
        return node

    def observe_mission_episode(self, item: MissionEpisodeObservation) -> WorldNode:
        if not str(item.mission_id).strip():
            raise ValueError("MISSION_ID_REQUIRED")
        if not str(item.objective).strip() or not str(item.state).strip():
            raise ValueError("MISSION_OBJECTIVE_AND_STATE_REQUIRED")
        cycle_time = _nonnegative(item.cycle_time_seconds, "MISSION_CYCLE_TIME")
        intervention = _nonnegative(
            item.owner_intervention_seconds, "MISSION_OWNER_INTERVENTION"
        )
        if int(item.clarification_count) < 0:
            raise ValueError("MISSION_CLARIFICATION_COUNT_NON_NEGATIVE_REQUIRED")
        node = WorldNode(
            node_id=MISSION_PREFIX + item.mission_id,
            kind=NodeKind.MISSION,
            label=item.objective,
            state=item.state,
            payload={
                "outcome_ref": item.outcome_ref,
                "accepted": item.accepted,
                "cycle_time_seconds": cycle_time,
                "owner_intervention_seconds": intervention,
                "clarification_count": int(item.clarification_count),
            },
            provenance=self._provenance(
                source_ref="BUBBLES_MISSION_EPISODE",
                proof_ref=item.proof_ref,
                observed_at=item.observed_at,
                confidence=1.0,
                ttl_seconds=31_536_000,
                matter_scope=item.matter_scope,
                sensitivity="PROJECT",
                source_class="MISSION_EPISODE",
            ),
        ).validate()
        self.model.observe_node(node)
        return node

    def observe_owner_burden(self, item: OwnerBurdenObservation) -> WorldNode:
        intervention = _nonnegative(
            item.intervention_seconds, "OWNER_INTERVENTION_SECONDS"
        )
        clarification = int(item.clarification_count)
        corrections = int(item.correction_count)
        if clarification < 0 or corrections < 0:
            raise ValueError("OWNER_BURDEN_COUNTS_NON_NEGATIVE_REQUIRED")
        node = WorldNode(
            node_id=_burden_id(item.mission_id, item.observed_at, item.proof_ref),
            kind=NodeKind.EVIDENCE,
            label=f"owner burden {item.mission_id}",
            state="OBSERVED",
            payload={
                "mission_id": item.mission_id,
                "intervention_seconds": intervention,
                "clarification_count": clarification,
                "correction_count": corrections,
            },
            provenance=self._provenance(
                source_ref="BUBBLES_OWNER_BURDEN_OBSERVATION",
                proof_ref=item.proof_ref,
                observed_at=item.observed_at,
                confidence=1.0,
                ttl_seconds=31_536_000,
                matter_scope=item.matter_scope,
                sensitivity="OWNER_PRIVATE",
                source_class="OWNER_BURDEN",
            ),
        ).validate()
        self.model.observe_node(node)
        return node

    def projection(self, *, now: str) -> dict[str, Any]:
        nodes = self.model.current_nodes(now=now)
        preference_nodes = [
            node for key, node in sorted(nodes.items()) if key.startswith(PREFERENCE_PREFIX)
        ]
        mission_nodes = [
            node for key, node in sorted(nodes.items()) if key.startswith(MISSION_PREFIX)
        ]
        burden_nodes = [
            node for key, node in sorted(nodes.items()) if key.startswith(BURDEN_PREFIX)
        ]

        preferences = {
            str(node.payload["preference_key"]): node.payload.get("preference_value")
            for node in preference_nodes
        }
        total_intervention = sum(
            float(node.payload.get("intervention_seconds", 0.0))
            for node in burden_nodes
        )
        total_clarifications = sum(
            int(node.payload.get("clarification_count", 0)) for node in burden_nodes
        )
        total_corrections = sum(
            int(node.payload.get("correction_count", 0)) for node in burden_nodes
        )
        accepted_outcomes = sum(
            node.payload.get("accepted") is True for node in mission_nodes
        )

        payload: dict[str, Any] = {
            "schema": "BUBBLES-DIGITAL-TWIN-PROJECTION-V1",
            "preferences": preferences,
            "preference_count": len(preference_nodes),
            "mission_count": len(mission_nodes),
            "burden_observation_count": len(burden_nodes),
            "accepted_outcomes": int(accepted_outcomes),
            "owner_intervention_seconds": total_intervention,
            "clarification_count": total_clarifications,
            "correction_count": total_corrections,
            "event_count": self.model.event_count,
            "event_head_digest": self.model.event_head_digest,
            "event_chain_valid": self.model.verify_event_chain(),
            "external_effects": self.model.external_effects,
            "truth_boundary": {
                "projection_is_owner_identity": False,
                "preferences_are_inferred_without_observation": False,
                "persistent_production_runtime_claimed": False,
                "provider_authority_inferred": False,
                "empirical_owner_value_claimed": False,
            },
        }
        payload["projection_sha256"] = digest(payload)
        return payload

    def seal(
        self,
        store: LivingStateStore,
        *,
        now: str,
        fabric_id: str = DIGITAL_TWIN_FABRIC_ID,
    ) -> DigitalTwinSealReceipt:
        store_receipt: StoreReceipt = store.seal(
            self.model, now=now, fabric_id=fabric_id
        )
        projection = self.projection(now=now)
        return DigitalTwinSealReceipt(
            fabric_id=fabric_id,
            event_count=store_receipt.event_count,
            event_head_digest=store_receipt.event_head_digest,
            snapshot_sha256=store_receipt.snapshot_sha256,
            store_readback_verified=store_receipt.store_readback_verified,
            preference_count=int(projection["preference_count"]),
            mission_count=int(projection["mission_count"]),
            burden_observation_count=int(projection["burden_observation_count"]),
            external_effects=store_receipt.external_effects,
        )

    @classmethod
    def restore(
        cls,
        store: LivingStateStore,
        *,
        fabric_id: str = DIGITAL_TWIN_FABRIC_ID,
    ) -> "BubblesDigitalTwinState":
        return cls(store.restore(fabric_id=fabric_id))


__all__ = [
    "BubblesDigitalTwinState",
    "DigitalTwinSealReceipt",
    "MissionEpisodeObservation",
    "OwnerBurdenObservation",
    "OwnerPreferenceObservation",
]
