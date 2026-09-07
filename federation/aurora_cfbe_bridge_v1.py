"""AURORA Ω ↔ CFBE Formation Mesh bridge v1.

Maps AURORA knowledge-agent specialists onto existing Formation/FUSE bot roles and
applies a conjunctive completion gate. No provider authority is created.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable

from benchmarking.cfbe_omega.formation_mesh_v1 import CFBEMeshWitness
from federation.aurora_omega_v1 import SpecialistRole

SCHEMA = "FUSE-AURORA-CFBE-FORMATION-BRIDGE-V1"
VERSION = "1.0.0"

ROLE_MAP = {
    SpecialistRole.MISSION_PLANNER: "ROUTE",
    SpecialistRole.INNOVATION_HISTORIAN: "EVIDENCE",
    SpecialistRole.SYNTHESIS_SCHOLAR: "EVIDENCE",
    SpecialistRole.RESEARCHER: "EVIDENCE",
    SpecialistRole.ROOT_CAUSE_INVESTIGATOR: "RECOVERY",
    SpecialistRole.BUILDER: "BUILDER",
    SpecialistRole.CHALLENGER: "FALSIFIER",
    SpecialistRole.VERIFIER: "WITNESS",
    SpecialistRole.VISUAL_REVIEWER: "EVIDENCE",
    SpecialistRole.KNOWLEDGE_CURATOR: "SENTINEL",
}


def _digest(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AuroraCFBEBotBinding:
    aurora_role: str
    formation_role: str
    independence_domain: str
    may_self_certify: bool = False
    provider_native_worker: bool = False


@dataclass(frozen=True, slots=True)
class AuroraCFBECompletionReceipt:
    schema: str
    version: str
    mission_id: str
    state: str
    aurora_complete_verified: bool
    cfbe_omega_verified: bool
    completion_allowed: bool
    bindings: tuple[AuroraCFBEBotBinding, ...]
    provider_native_worker_count: int
    external_effect: bool
    receipt_sha256: str


def compile_bindings(roles: Iterable[SpecialistRole] = tuple(SpecialistRole)) -> tuple[AuroraCFBEBotBinding, ...]:
    bindings: list[AuroraCFBEBotBinding] = []
    seen: set[SpecialistRole] = set()
    for role in roles:
        if role in seen:
            continue
        seen.add(role)
        formation_role = ROLE_MAP[role]
        independence = "INDEPENDENT_VERIFICATION" if role in {SpecialistRole.CHALLENGER, SpecialistRole.VERIFIER} else formation_role
        bindings.append(AuroraCFBEBotBinding(role.value, formation_role, independence))
    return tuple(bindings)


def completion_gate(*, mission_id: str, aurora_complete_verified: bool, cfbe_witness: CFBEMeshWitness) -> AuroraCFBECompletionReceipt:
    if not mission_id.strip():
        raise ValueError("MISSION_ID_REQUIRED")
    if cfbe_witness.mission_id != mission_id:
        raise ValueError("MISSION_IDENTITY_MISMATCH")
    cfbe_omega = bool(cfbe_witness.completion_allowed and cfbe_witness.state == "CFBE_FORMATION_OMEGA_VERIFIED" and cfbe_witness.alpha_omega_state == "OMEGA")
    completion = bool(aurora_complete_verified and cfbe_omega)
    state = "COMPLETE_VERIFIED" if completion else "CONTINUE_TO_COMPLETE_VERIFIED"
    bindings = compile_bindings()
    body = {"schema": SCHEMA, "version": VERSION, "mission_id": mission_id, "state": state, "aurora_complete_verified": bool(aurora_complete_verified), "cfbe_omega_verified": cfbe_omega, "bindings": [(item.aurora_role, item.formation_role) for item in bindings], "provider_native_worker_count": 0, "external_effect": False}
    return AuroraCFBECompletionReceipt(SCHEMA, VERSION, mission_id, state, bool(aurora_complete_verified), cfbe_omega, completion, bindings, 0, False, _digest(body))


__all__ = ["AuroraCFBEBotBinding", "AuroraCFBECompletionReceipt", "ROLE_MAP", "SCHEMA", "VERSION", "compile_bindings", "completion_gate"]
