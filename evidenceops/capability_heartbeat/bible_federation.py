"""Master Bible facade over the single verified-v4 authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .authority import VerifiedV4Authority
from .foundation.adapters.common import Observation
from .foundation.aggregator import AggregationResult
from .foundation.contracts import HeartbeatEnvelope, Receipt, canonicalize
from .foundation.errors import ContractError, HeartbeatError
from .foundation.ledger import ImmutableEventLedger
from .foundation.respawn import RespawnManifest, RespawnReadback, verify_respawn


@dataclass(frozen=True, slots=True)
class BibleFederation:
    """Compatibility facade; it owns no policy, score, signer or scheduler."""

    authority: VerifiedV4Authority

    def __post_init__(self) -> None:
        if not isinstance(self.authority, VerifiedV4Authority):
            raise ContractError("VERIFIED_V4_AUTHORITY_REQUIRED")

    def make_heartbeat(
        self,
        *,
        observations: tuple[Observation, ...],
        observed_at: str,
        expires_at: str,
        trace_id: str,
        root_transaction_id: str,
        mission_code: str,
        sequence: int,
    ) -> tuple[AggregationResult, HeartbeatEnvelope]:
        return self.authority.build_root_envelope(
            observations=observations,
            now=observed_at,
            expires_at=expires_at,
            trace_id=trace_id,
            root_transaction_id=root_transaction_id,
            mission_code=mission_code,
            sequence=sequence,
        )

    def forward(
        self,
        *,
        lineage: tuple[HeartbeatEnvelope, ...],
        forwarding_node_id: str,
        observed_at: str,
    ) -> HeartbeatEnvelope:
        return self.authority.forward(
            lineage=lineage,
            forwarding_node_id=forwarding_node_id,
            now=observed_at,
        )

    def accept(
        self,
        *,
        lineage: tuple[HeartbeatEnvelope, ...],
        destination_node_id: str,
        observed_at: str,
    ) -> Receipt:
        return self.authority.accept(
            lineage=lineage,
            destination_node_id=destination_node_id,
            now=observed_at,
        )

    def child_scaffold(self, node_id: str) -> dict[str, Any]:
        """Describe an already registered child without creating authority."""
        record = self.authority.registry.get(node_id)
        if record.parent_node_id is None:
            raise ContractError("CHILD_NODE_REQUIRED")
        return {
            "schema": "EVIDENCEOPS-BIBLE-CHILD-SCAFFOLD-2",
            "node_id": record.node_id,
            "parent_node_id": record.parent_node_id,
            "generation": record.generation,
            "owner_code": record.owner_code,
            "matter_code": record.matter_code,
            "classification": record.classification.value,
            "authority_ceiling": record.authority_ceiling.value,
            "control_generation": record.control_generation,
            "registration_receipt": record.registration_receipt,
            "signer_identity": canonicalize(record.signer_identity),
            "max_hops": self.authority.policy.max_hops,
            "effectful_execution_inherited": False,
            "live_awareness_flags": self.authority.live_awareness_flags,
            "truth_boundary": "This is a read-only view of prior verified registration, not a child-creation action.",
        }

    def reconcile(self, *, observed_at: str) -> dict[str, Any]:
        readback = self.authority.authority_readback(now=observed_at)
        return {
            "schema": "EVIDENCEOPS-BIBLE-NODE-RECONCILIATION-2",
            "observed_at": observed_at,
            "authority_readback": readback,
            "registered_node_count": len(self.authority.registry.records),
            "active_chat_count": 0,
            "scheduler_authority": False,
            "live_awareness_flags": self.authority.live_awareness_flags,
            "truth_boundary": (
                "Fresh registered nodes are known to the injected local authority. No provider-authoritative "
                "active-chat inventory, per-chat emitter coverage, or live attachment is inferred."
            ),
        }

    def verify_respawn(
        self,
        *,
        manifest: RespawnManifest,
        ledger: ImmutableEventLedger,
        observed_at: str,
    ) -> RespawnReadback:
        return verify_respawn(
            manifest=manifest,
            policy=self.authority.policy,
            registry=self.authority.registry,
            ledger=ledger,
            stop_control=self.authority.stop_control,
            now=observed_at,
        )


__all__ = ["BibleFederation", "HeartbeatError"]
