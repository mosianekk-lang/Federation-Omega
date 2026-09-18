from __future__ import annotations

"""Formation Foundry receipt verifier for FRCB v3.

This module does not execute the EvidenceOps foundry. It validates an already
produced FoundryCycleResult, binds its deterministic receipt digest to the exact
FormationDecision consumed downstream, and emits an authority-neutral binding
receipt.

The binding proves deterministic local foundry-cycle integrity and decision
attachment. It is not independent cryptographic attestation, provider execution,
or whole-mission terminal proof.
"""

from dataclasses import dataclass
from hashlib import sha256 as _hashlib_sha256
import json
from types import MappingProxyType
from typing import Any, Mapping

from evidenceops.innovation_engine.algorithms_common import (
    AUTHORITY_CEILING,
    sha256 as evidenceops_sha256,
)
from evidenceops.innovation_engine.foundry_model import FoundryCycleResult
from federation.of50_ace_v1 import FormationDecision

SCHEMA = "FUSE-FORMATION-FOUNDRY-BINDING-RECEIPT-V1"
VERSION = "1.0.0"
PRODUCER_ID = "EVIDENCEOPS-ALGORITHM-FOUNDRY"


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return "sha256:" + _hashlib_sha256(_stable(value).encode("utf-8")).hexdigest()


def foundry_receipt_sha256(result: FoundryCycleResult) -> str:
    receipt = str(result.as_dict().get("receipt_sha256") or "")
    if len(receipt) != 64:
        raise ValueError("FORMATION_FOUNDRY_RECEIPT_SHA256_INVALID")
    return receipt


def validate_foundry_cycle(result: FoundryCycleResult) -> str:
    if result.status != "PASSED":
        raise ValueError("FORMATION_FOUNDRY_CYCLE_NOT_PASSED")
    if result.authority_ceiling != AUTHORITY_CEILING:
        raise ValueError("FORMATION_FOUNDRY_AUTHORITY_WIDENING")
    if result.external_effect:
        raise ValueError("FORMATION_FOUNDRY_EXTERNAL_EFFECT_FORBIDDEN")
    if not result.cycle_id.strip():
        raise ValueError("FORMATION_FOUNDRY_CYCLE_ID_REQUIRED")
    if not result.maturity.strip():
        raise ValueError("FORMATION_FOUNDRY_MATURITY_REQUIRED")

    proof = dict(result.proof)
    if proof.get("authority_ceiling") != AUTHORITY_CEILING:
        raise ValueError("FORMATION_FOUNDRY_PROOF_AUTHORITY_MISMATCH")
    if proof.get("external_effect") is not False:
        raise ValueError("FORMATION_FOUNDRY_PROOF_EXTERNAL_EFFECT_MISMATCH")
    if proof.get("registry_chain") != "PASSED":
        raise ValueError("FORMATION_FOUNDRY_REGISTRY_CHAIN_NOT_VERIFIED")

    learning = proof.get("learning_chain")
    if not isinstance(learning, Mapping) or learning.get("status") != "PASSED":
        raise ValueError("FORMATION_FOUNDRY_LEARNING_CHAIN_NOT_VERIFIED")
    evolution = proof.get("evolution_chain")
    if not isinstance(evolution, Mapping) or evolution.get("status") != "PASSED":
        raise ValueError("FORMATION_FOUNDRY_EVOLUTION_CHAIN_NOT_VERIFIED")

    supplied_proof_sha = str(proof.get("proof_sha256") or "")
    unsigned_proof = {key: value for key, value in proof.items() if key != "proof_sha256"}
    expected_proof_sha = evidenceops_sha256(unsigned_proof)
    if not supplied_proof_sha or supplied_proof_sha != expected_proof_sha:
        raise ValueError("FORMATION_FOUNDRY_PROOF_SHA256_MISMATCH")

    return foundry_receipt_sha256(result)


@dataclass(frozen=True, slots=True)
class FormationFoundryBindingReceipt:
    schema: str
    version: str
    producer_id: str
    mission_id: str
    cycle_id: str
    foundry_receipt_sha256: str
    proof_sha256: str
    decision_foundry_cycle_ref: str
    authority_ceiling: str
    receipt_digest: str
    truth_boundary: Mapping[str, bool]

    def deterministic_payload(self) -> Mapping[str, object]:
        return {
            "schema": self.schema,
            "version": self.version,
            "producer_id": self.producer_id,
            "mission_id": self.mission_id,
            "cycle_id": self.cycle_id,
            "foundry_receipt_sha256": self.foundry_receipt_sha256,
            "proof_sha256": self.proof_sha256,
            "decision_foundry_cycle_ref": self.decision_foundry_cycle_ref,
            "authority_ceiling": self.authority_ceiling,
            "truth_boundary": dict(self.truth_boundary),
        }

    def verify(self) -> bool:
        boundary = dict(self.truth_boundary)
        return bool(
            self.schema == SCHEMA
            and self.version == VERSION
            and self.producer_id == PRODUCER_ID
            and self.mission_id.strip()
            and self.cycle_id.strip()
            and len(self.foundry_receipt_sha256) == 64
            and len(self.proof_sha256) == 64
            and self.decision_foundry_cycle_ref == self.foundry_receipt_sha256
            and self.authority_ceiling == AUTHORITY_CEILING
            and boundary.get("foundry_cycle_receipt_verified") is True
            and boundary.get("foundry_chain_proof_verified") is True
            and boundary.get("mission_identity_native_to_foundry_receipt") is False
            and boundary.get("provider_execution_verified") is False
            and boundary.get("external_effect_created") is False
            and boundary.get("authority_widened") is False
            and self.receipt_digest == _digest(self.deterministic_payload())
        )


class FormationFoundryBinder:
    def bind(
        self,
        *,
        mission_id: str,
        foundry_result: FoundryCycleResult,
        formation_decision: FormationDecision,
    ) -> FormationFoundryBindingReceipt:
        mission_id = str(mission_id).strip()
        if not mission_id:
            raise ValueError("FORMATION_BINDING_MISSION_ID_REQUIRED")
        if formation_decision.mission_id != mission_id:
            raise ValueError("FORMATION_BINDING_MISSION_MISMATCH")
        if formation_decision.authority_ceiling != AUTHORITY_CEILING:
            raise ValueError("FORMATION_BINDING_AUTHORITY_WIDENING")
        if formation_decision.external_effect:
            raise ValueError("FORMATION_BINDING_EXTERNAL_EFFECT_FORBIDDEN")

        receipt_sha = validate_foundry_cycle(foundry_result)
        if formation_decision.foundry_cycle_ref != receipt_sha:
            raise ValueError("FORMATION_DECISION_FOUNDRY_RECEIPT_MISMATCH")

        truth_boundary = MappingProxyType({
            "foundry_cycle_receipt_verified": True,
            "foundry_chain_proof_verified": True,
            "mission_identity_native_to_foundry_receipt": False,
            "provider_execution_verified": False,
            "external_effect_created": False,
            "authority_widened": False,
        })
        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "producer_id": PRODUCER_ID,
            "mission_id": mission_id,
            "cycle_id": foundry_result.cycle_id,
            "foundry_receipt_sha256": receipt_sha,
            "proof_sha256": str(foundry_result.proof["proof_sha256"]),
            "decision_foundry_cycle_ref": formation_decision.foundry_cycle_ref,
            "authority_ceiling": formation_decision.authority_ceiling,
            "truth_boundary": dict(truth_boundary),
        }
        receipt = FormationFoundryBindingReceipt(
            schema=SCHEMA,
            version=VERSION,
            producer_id=PRODUCER_ID,
            mission_id=mission_id,
            cycle_id=foundry_result.cycle_id,
            foundry_receipt_sha256=receipt_sha,
            proof_sha256=str(foundry_result.proof["proof_sha256"]),
            decision_foundry_cycle_ref=formation_decision.foundry_cycle_ref,
            authority_ceiling=formation_decision.authority_ceiling,
            receipt_digest=_digest(material),
            truth_boundary=truth_boundary,
        )
        if not receipt.verify():
            raise ValueError("FORMATION_FOUNDRY_BINDING_RECEIPT_SELF_VERIFICATION_FAILED")
        return receipt


__all__ = [
    "FormationFoundryBinder",
    "FormationFoundryBindingReceipt",
    "PRODUCER_ID",
    "SCHEMA",
    "VERSION",
    "foundry_receipt_sha256",
    "validate_foundry_cycle",
]
