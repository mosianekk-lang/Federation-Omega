"""One-authority integration facade for the verified heartbeat foundation.

Legacy catalogue, SQLite, MCP and CLI surfaces may call this object.  They may
not calculate policy, create unsigned ingress, or widen recommendation
authority themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from .foundation.adapters.common import Observation
from .foundation.aggregator import AggregationResult, OnInputAggregator
from .foundation.contracts import (
    Authority,
    Classification,
    HeartbeatEnvelope,
    NodeState,
    Receipt,
    digest,
)
from .foundation.errors import ContractError
from .foundation.master_bible import MasterBiblePolicy
from .foundation.policy import FlowState
from .foundation.propagation import accept_envelope, build_envelope, forward_envelope
from .foundation.registry import NodeRecord, NodeRegistry
from .foundation.signing import RuntimeSigner
from .foundation.stop_control import StopControl


@dataclass(frozen=True, slots=True)
class VerifiedV4Authority:
    """The only policy, recommendation, signing and acceptance authority.

    Runtime signers are injected by the caller and are never discovered from
    static files.  A catalogue record or an unhosted adapter can therefore be
    observed, but can never authorize ingress.
    """

    policy: MasterBiblePolicy
    registry: NodeRegistry
    runtime_signers: Mapping[str, RuntimeSigner]
    stop_control: StopControl = StopControl()
    aggregator: OnInputAggregator = OnInputAggregator()
    _signers: Mapping[str, RuntimeSigner] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.policy, MasterBiblePolicy):
            raise ContractError("MASTER_BIBLE_POLICY_REQUIRED")
        if not isinstance(self.registry, NodeRegistry):
            raise ContractError("NODE_REGISTRY_REQUIRED")
        if not isinstance(self.stop_control, StopControl):
            raise ContractError("STOP_CONTROL_REQUIRED")
        if not self.stop_control.active or self.stop_control.generation != self.policy.control_generation:
            raise ContractError("POLICY_STOP_GENERATION_MISMATCH")
        readback = self.registry.semantic_readback()
        if not readback["valid"] or tuple(readback["root_node_ids"]) != (self.policy.root_node_id,):
            raise ContractError("REGISTRY_POLICY_ROOT_MISMATCH")
        signers = dict(self.runtime_signers)
        if set(signers) != {item.node_id for item in self.registry.records}:
            raise ContractError("COMPLETE_REGISTERED_SIGNER_SET_REQUIRED")
        for record in self.registry.records:
            signer = signers.get(record.node_id)
            if not isinstance(signer, RuntimeSigner):
                raise ContractError("REGISTERED_RUNTIME_SIGNER_REQUIRED")
            signer.assert_binding(node_record=record, stop_control=self.stop_control)
            if record.owner_code != self.policy.owner_code or record.matter_code != self.policy.matter_code:
                raise ContractError("REGISTRY_POLICY_SCOPE_MISMATCH")
            if record.authority_ceiling is not Authority.A0:
                raise ContractError("INTEGRATION_AUTHORITY_MUST_BE_A0")
        object.__setattr__(self, "_signers", MappingProxyType(signers))

    @property
    def live_awareness_flags(self) -> dict[str, bool]:
        return {
            "live_master_bible_attachment": False,
            "active_chat_inventory": False,
            "per_chat_emitters": False,
            "unsolicited_injection": False,
            "system_wide_awareness": False,
        }

    def recommend(
        self,
        *,
        observations: tuple[Observation, ...],
        now: str,
        flow_state: FlowState = FlowState(),
    ) -> AggregationResult:
        self.stop_control.assert_current(self.policy.control_generation)
        return self.aggregator.on_input(
            observations=observations,
            owner_code=self.policy.owner_code,
            matter_code=self.policy.matter_code,
            now=now,
            flow_state=flow_state,
        )

    def build_root_envelope(
        self,
        *,
        observations: tuple[Observation, ...],
        now: str,
        expires_at: str,
        trace_id: str,
        root_transaction_id: str,
        mission_code: str,
        sequence: int,
        state: NodeState = NodeState.NEEDS_CAPABILITY,
        flow_state: FlowState = FlowState(),
    ) -> tuple[AggregationResult, HeartbeatEnvelope]:
        result = self.recommend(observations=observations, now=now, flow_state=flow_state)
        root = self.registry.assert_fresh(self.policy.root_node_id, now=now)
        signer = self._signers[root.node_id]
        envelope = build_envelope(
            signer=signer,
            trace_id=trace_id,
            origin_node_id=root.node_id,
            root_transaction_id=root_transaction_id,
            mission_code=mission_code,
            owner_code=self.policy.owner_code,
            matter_code=self.policy.matter_code,
            classification=self.policy.classification,
            state=state,
            capability_hashes=tuple(sorted({item.capability_hash for item in observations})),
            blocker_codes=tuple(sorted({item.blocker_code for item in observations}, key=lambda item: item.value)),
            recommendations=result.recommendations,
            observed_at=now,
            expires_at=expires_at,
            sequence=sequence,
            control_generation=self.policy.control_generation,
        )
        return result, envelope

    def forward(
        self,
        *,
        lineage: tuple[HeartbeatEnvelope, ...],
        forwarding_node_id: str,
        now: str,
    ) -> HeartbeatEnvelope:
        return forward_envelope(
            lineage=lineage,
            forwarding_node_id=forwarding_node_id,
            registry=self.registry,
            stop_control=self.stop_control,
            runtime_verifiers=self._signers,
            forwarding_signer=self._signers[forwarding_node_id],
            now=now,
        )

    def accept(
        self,
        *,
        lineage: tuple[HeartbeatEnvelope, ...],
        destination_node_id: str,
        now: str,
    ) -> Receipt:
        destination = self.registry.assert_fresh(destination_node_id, now=now)
        receipt = accept_envelope(
            lineage=lineage,
            destination_node_id=destination_node_id,
            registry=self.registry,
            stop_control=self.stop_control,
            runtime_verifiers=self._signers,
            destination_signer=self._signers[destination_node_id],
            now=now,
        )
        self._signers[destination_node_id].verify_receipt(
            receipt,
            accepted_envelope=lineage[-1],
            destination_record=destination,
            stop_control=self.stop_control,
            now=now,
        )
        return receipt

    def verifier_for(self, node_id: str) -> RuntimeSigner:
        try:
            return self._signers[node_id]
        except KeyError as exc:
            raise ContractError("NODE_NOT_REGISTERED") from exc

    def authority_readback(self, *, now: str) -> dict[str, object]:
        fresh = tuple(
            self.registry.assert_fresh(item.node_id, now=now).record_hash
            for item in self.registry.records
        )
        return {
            "schema": "EVIDENCEOPS-VERIFIED-V4-AUTHORITY-READBACK-1",
            "policy_hash": self.policy.policy_hash,
            "registry_hash": self.registry.registry_hash,
            "fresh_record_hashes": fresh,
            "authority_ceiling": Authority.A0.value,
            "max_hops": self.policy.max_hops,
            "recommendation_only": self.policy.recommendation_only,
            "control_generation": self.policy.control_generation,
            "live_awareness_flags": self.live_awareness_flags,
            "readback_hash": digest(
                {
                    "policy_hash": self.policy.policy_hash,
                    "registry_hash": self.registry.registry_hash,
                    "fresh_record_hashes": fresh,
                    "control_generation": self.policy.control_generation,
                }
            ),
        }


def assert_policy_matches_record(policy: MasterBiblePolicy, record: NodeRecord) -> None:
    """Small reusable integration assertion for facade and fixture builders."""
    if not all(
        (
            record.node_id == policy.root_node_id,
            record.owner_code == policy.owner_code,
            record.matter_code == policy.matter_code,
            record.classification == policy.classification,
            record.control_generation == policy.control_generation,
            record.authority_ceiling is Authority.A0,
            record.signer_identity.signing_version == policy.signing_version,
        )
    ):
        raise ContractError("ROOT_RECORD_POLICY_MISMATCH")
