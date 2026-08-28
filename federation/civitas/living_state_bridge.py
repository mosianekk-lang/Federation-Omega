from __future__ import annotations

"""Additive bridge from CIVITAS observations into existing Living State ingress.

CIVITAS does not create a second canonical journal. The existing
`federation.living_state` event store and transactional ingress remain the
state authority when present.
"""

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .adapters import NormalizedObservation
from .contracts import CivitasError, ProofLevel, digest


@dataclass(frozen=True)
class BridgeReceipt:
    event_id: str
    disposition: str
    living_state_event_head: str
    living_state_snapshot_sha256: str
    proof_level_in: str
    proof_level_out: str
    evidence_upgraded: bool
    readback_verified: bool
    second_journal_created: bool = False
    authority_created: bool = False
    external_effects: int = 0

    @property
    def receipt_sha256(self) -> str:
        return digest(asdict(self))


class LivingStateCivitasBridge:
    """Proof-preserving adapter into `LivingStateIngress`."""

    def __init__(self, ingress: Any) -> None:
        self.ingress = ingress

    @staticmethod
    def _imports() -> Mapping[str, Any]:
        try:
            from federation.living_state.ingress import IngressEnvelope
            from federation.living_state.types import NodeKind, ProofMaturity
        except Exception as exc:  # pragma: no cover - exact host packaging boundary
            raise CivitasError("existing Living State ingress is not importable") from exc
        return {
            "IngressEnvelope": IngressEnvelope,
            "NodeKind": NodeKind,
            "ProofMaturity": ProofMaturity,
        }

    @staticmethod
    def _proof_level(level: ProofLevel, proof_maturity: Any) -> Any:
        mapping = {
            ProofLevel.UNKNOWN: "UNKNOWN",
            ProofLevel.DECLARED: "DECLARED",
            ProofLevel.SOURCE_READBACK: "SOURCE_READBACK",
            ProofLevel.DETERMINISTIC_TESTED: "DETERMINISTIC_TESTED",
            ProofLevel.SHADOW_VERIFIED: "DETERMINISTIC_TESTED",
            ProofLevel.RUNTIME_READBACK: "RUNTIME_READBACK",
            ProofLevel.PROVIDER_READBACK: "PROVIDER_READBACK",
            ProofLevel.RECEIPT_VERIFIED: "PROVIDER_READBACK",
        }
        name = mapping[level]
        try:
            return proof_maturity(name)
        except Exception:
            try:
                return getattr(proof_maturity, name)
            except AttributeError as exc:
                raise CivitasError(f"Living State proof maturity missing {name}") from exc

    @staticmethod
    def _node_kind(kind: str, node_kind: Any) -> str:
        try:
            return node_kind(str(kind)).value
        except Exception as exc:
            raise CivitasError(f"Living State node kind unsupported: {kind}") from exc

    def ingest(self, observation: NormalizedObservation) -> BridgeReceipt:
        observation.validate()
        imports = self._imports()
        proof = self._proof_level(observation.proof_level, imports["ProofMaturity"])
        object_kind = observation.object_kind
        if observation.event_class == "NODE_STATE":
            object_kind = self._node_kind(object_kind, imports["NodeKind"])
        envelope = imports["IngressEnvelope"](
            event_id=observation.event_id,
            event_class=observation.event_class,
            source_ref=observation.source_ref,
            observed_at=observation.observed_at,
            proof_ref=observation.proof_ref,
            proof_maturity=proof,
            object_id=observation.object_id,
            object_kind=object_kind,
            state=observation.state,
            payload=dict(observation.payload),
            ttl_seconds=observation.ttl_seconds,
            confidence=observation.confidence,
            matter_scope=observation.matter_scope,
            sensitivity="PRIVATE_LOCAL" if observation.sensitivity != "PUBLIC_SAFE" else "PUBLIC_SAFE",
            authority_ceiling="A1_INTERNAL",
        )
        result = self.ingress.ingest(envelope)
        output_name = str(getattr(proof, "value", proof))
        input_name = observation.proof_level.value
        upgrade = self._rank_output(output_name) > self._rank_input(observation.proof_level)
        if upgrade:
            raise CivitasError("Living State bridge attempted evidence upgrade")
        return BridgeReceipt(
            event_id=observation.event_id,
            disposition=str(result.disposition),
            living_state_event_head=str(result.new_event_head),
            living_state_snapshot_sha256=str(result.snapshot_sha256),
            proof_level_in=input_name,
            proof_level_out=output_name,
            evidence_upgraded=False,
            readback_verified=bool(result.readback_verified),
        )

    @staticmethod
    def _rank_input(level: ProofLevel) -> int:
        return {
            ProofLevel.UNKNOWN: 0,
            ProofLevel.DECLARED: 1,
            ProofLevel.SOURCE_READBACK: 2,
            ProofLevel.DETERMINISTIC_TESTED: 3,
            ProofLevel.SHADOW_VERIFIED: 4,
            ProofLevel.RUNTIME_READBACK: 5,
            ProofLevel.PROVIDER_READBACK: 6,
            ProofLevel.RECEIPT_VERIFIED: 7,
        }[level]

    @staticmethod
    def _rank_output(name: str) -> int:
        return {
            "UNKNOWN": 0,
            "DECLARED": 1,
            "SOURCE_READBACK": 2,
            "DETERMINISTIC_TESTED": 3,
            "RUNTIME_READBACK": 5,
            "PROVIDER_READBACK": 6,
            "RECEIPT_VERIFIED": 7,
        }.get(name, 0)

    @classmethod
    def from_store(cls, store: Any, *, fabric_id: str = "FEDERATION", allow_private_local: bool = False) -> "LivingStateCivitasBridge":
        try:
            from federation.living_state.ingress import LivingStateIngress
        except Exception as exc:  # pragma: no cover
            raise CivitasError("Living State ingress is not importable") from exc
        return cls(LivingStateIngress(store, fabric_id=fabric_id, allow_private_local=allow_private_local))


__all__ = ["BridgeReceipt", "LivingStateCivitasBridge"]
