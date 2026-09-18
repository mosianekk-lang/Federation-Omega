from __future__ import annotations

"""OH50 producer adapter over existing HORIZON-Ω and Formation swarm primitives.

This module creates no scheduler, authority plane, provider runtime, proof store,
memory root, foundry, or external effect. It composes existing no-effect
Federation primitives into the 50-cell SwarmManifest contract already
consumed by OF50 and emits a deterministic producer-invocation receipt.

The receipt proves that these in-process producer primitives were actually
invoked to build the manifest. It is not an independent signature, provider
execution proof, or future-event proof.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from ao_harmonic_v3.horizon import HorizonOmega, HorizonRun
from formation_omega.autonomic_fabric import MissionSwarmPlanner, SwarmCell
from federation.of50_ace_v1 import Authority, HORIZON_IDS, HorizonCell, SwarmManifest

SCHEMA = "FUSE-OH50-PRODUCER-RECEIPT-V1"
VERSION = "1.0.0"
PRODUCER_ID = "HORIZON-OMEGA-V1+FORMATION-MISSION-SWARM"
SEMANTIC_READBACK_CONTRACT = (
    "OH50 producer receipt binds deterministic internal foresight output; "
    "downstream execution still requires action-specific independent semantic readback."
)


def _default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dict__"):
        return vars(value)
    return str(value)


def _stable(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_default,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


def manifest_digest(manifest: SwarmManifest) -> str:
    return _digest(asdict(manifest))


@dataclass(frozen=True, slots=True)
class OH50ProducerReceipt:
    schema: str
    version: str
    producer_id: str
    mission_id: str
    objective: str
    authority_ceiling: str
    host_algorithm_id: str
    horizon_count: int
    manifest_digest: str
    horizon_run_digest: str
    swarm_plan_digest: str
    receipt_digest: str
    truth_boundary: Mapping[str, bool]

    def deterministic_payload(self) -> Mapping[str, object]:
        return {
            "schema": self.schema,
            "version": self.version,
            "producer_id": self.producer_id,
            "mission_id": self.mission_id,
            "objective": self.objective,
            "authority_ceiling": self.authority_ceiling,
            "host_algorithm_id": self.host_algorithm_id,
            "horizon_count": self.horizon_count,
            "manifest_digest": self.manifest_digest,
            "horizon_run_digest": self.horizon_run_digest,
            "swarm_plan_digest": self.swarm_plan_digest,
            "truth_boundary": dict(self.truth_boundary),
        }

    def verify(self) -> bool:
        boundary = dict(self.truth_boundary)
        return bool(
            self.schema == SCHEMA
            and self.version == VERSION
            and self.producer_id == PRODUCER_ID
            and self.host_algorithm_id == PRODUCER_ID
            and self.mission_id.strip()
            and self.objective.strip()
            and self.authority_ceiling == Authority.A1_INTERNAL.value
            and self.horizon_count == 50
            and self.manifest_digest.startswith("sha256:")
            and self.horizon_run_digest.startswith("sha256:")
            and self.swarm_plan_digest.startswith("sha256:")
            and boundary.get("producer_invocation_verified") is True
            and boundary.get("producer_independent_attestation_verified") is False
            and boundary.get("prediction_promoted_to_fact") is False
            and boundary.get("provider_execution_verified") is False
            and boundary.get("external_effect_created") is False
            and boundary.get("authority_widened") is False
            and self.receipt_digest == _digest(self.deterministic_payload())
        )


@dataclass(frozen=True, slots=True)
class OH50ProducerResult:
    manifest: SwarmManifest
    horizon_run: HorizonRun
    swarm: tuple[SwarmCell, ...]
    receipt: OH50ProducerReceipt


class OH50ProducerAdapter:
    """Compose existing foresight + specialist-formation primitives into OH50."""

    def __init__(
        self,
        *,
        horizon: HorizonOmega | None = None,
        swarm_planner: MissionSwarmPlanner | None = None,
    ) -> None:
        self.horizon = horizon or HorizonOmega()
        self.swarm_planner = swarm_planner or MissionSwarmPlanner()

    def produce(
        self,
        *,
        mission_id: str,
        objective: str,
        authority_ceiling: str = Authority.A1_INTERNAL.value,
        required_capabilities: Iterable[str] = (),
    ) -> OH50ProducerResult:
        mission_id = str(mission_id).strip()
        objective = " ".join(str(objective).split())
        if not mission_id:
            raise ValueError("OH50_MISSION_ID_REQUIRED")
        if not objective:
            raise ValueError("OH50_OBJECTIVE_REQUIRED")
        if authority_ceiling != Authority.A1_INTERNAL.value:
            raise ValueError("OH50_PRODUCER_REQUIRES_A1_INTERNAL")

        run = self.horizon.simulate(
            objective=objective,
            profile="FRCB_OH50_50_HORIZON_PREPASS",
            consequential=True,
            requested_depth=50,
        )
        if run.adaptive_depth < 50 or len(run.nodes) < 50:
            raise ValueError("OH50_PRODUCER_DID_NOT_RETURN_50_HORIZONS")

        swarm = self.swarm_planner.plan(
            mission_id=mission_id,
            objective=objective,
            required_capabilities=tuple(sorted({str(x).strip() for x in required_capabilities if str(x).strip()})),
        )
        if not swarm:
            raise ValueError("OH50_SPECIALIST_SWARM_REQUIRED")

        nodes = run.nodes[:50]
        horizons = tuple(
            HorizonCell(
                horizon_id=HORIZON_IDS[index],
                state="ASSESSED",
                evidence_ref=_digest(asdict(node)),
                owner_role=swarm[index % len(swarm)].role.value,
            )
            for index, node in enumerate(nodes)
        )
        manifest = SwarmManifest(
            mission_id=mission_id,
            host_algorithm_id=PRODUCER_ID,
            objective=objective,
            authority_ceiling=authority_ceiling,
            horizons=horizons,
            specialist_roles=tuple(cell.role.value for cell in swarm),
            semantic_readback_contract=SEMANTIC_READBACK_CONTRACT,
        )
        errors = manifest.validate()
        if errors:
            raise ValueError("OH50_PRODUCED_MANIFEST_INVALID:" + ";".join(errors))

        truth_boundary = MappingProxyType({
            "producer_invocation_verified": True,
            "producer_independent_attestation_verified": False,
            "prediction_promoted_to_fact": False,
            "provider_execution_verified": False,
            "external_effect_created": False,
            "authority_widened": False,
        })
        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "producer_id": PRODUCER_ID,
            "mission_id": mission_id,
            "objective": objective,
            "authority_ceiling": authority_ceiling,
            "host_algorithm_id": manifest.host_algorithm_id,
            "horizon_count": len(manifest.horizons),
            "manifest_digest": manifest_digest(manifest),
            "horizon_run_digest": _digest(HorizonOmega.as_dict(run)),
            "swarm_plan_digest": _digest([asdict(cell) for cell in swarm]),
            "truth_boundary": dict(truth_boundary),
        }
        receipt = OH50ProducerReceipt(
            **material,
            receipt_digest=_digest(material),
        )
        if not receipt.verify():
            raise ValueError("OH50_PRODUCER_RECEIPT_SELF_VERIFICATION_FAILED")
        return OH50ProducerResult(
            manifest=manifest,
            horizon_run=run,
            swarm=swarm,
            receipt=receipt,
        )


__all__ = [
    "OH50ProducerAdapter",
    "OH50ProducerReceipt",
    "OH50ProducerResult",
    "PRODUCER_ID",
    "SCHEMA",
    "SEMANTIC_READBACK_CONTRACT",
    "VERSION",
    "manifest_digest",
]
