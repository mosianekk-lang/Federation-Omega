"""Self-contained, proof-bound MODISA cognitive decision adapter.

The adapter consumes a stable Federation capability handle (``CFBE``), not direct
imports from upstream BCO, ProofOS, or SOL packages. It validates authority and
objective bindings before appending an HMAC-authenticated MODISA proof record.
It performs no dispatch and grants no external-effect authority.
"""

from __future__ import annotations

import json
import re
import sqlite3
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ..canonical import sha256_json, sha256_text
from ..proof_ledger import ProofLedger
from ..schemas import ProofAppendRequest, ProofType
from ..security import contains_secret

BINDING_SCHEMA = "MODISA_COGNITIVE_BINDING_RECEIPT_V1"
BINDING_VERSION = "1.0.0"
ACTOR_ID = "MODISA-COGNITIVE-BINDING-V1"
EVIDENCE_REFERENCE = re.compile(r"^[a-z][a-z0-9._-]{1,31}:[A-Za-z0-9][A-Za-z0-9._/@-]{0,255}$")


class CognitiveBindingError(RuntimeError):
    """Base cognitive-binding failure."""


class CognitiveBindingVerificationError(CognitiveBindingError):
    """The request, policy, or generated proof failed verification."""


class CognitiveBindingCollisionError(CognitiveBindingError):
    """An idempotency key is already bound to different decision content."""


class CognitiveBindingState(StrEnum):
    ADMITTED_INTERNAL = "ADMITTED_INTERNAL"
    HOLD_OWNER = "HOLD_OWNER"
    HOLD_PROVIDER = "HOLD_PROVIDER"
    REJECTED = "REJECTED"


class CognitiveDecisionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mission_id: str = Field(min_length=1, max_length=200)
    matter_id: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=4000)
    objective_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer_receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dependency_handle: str = Field(default="CFBE", min_length=1, max_length=100)
    dispatch_authorized: bool = False
    external_effect_authorized: bool = False
    owner_interrupt_required: bool = False
    provider_runtime_hold: bool = False
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, values: list[str]) -> list[str]:
        for value in values:
            if not EVIDENCE_REFERENCE.fullmatch(value):
                raise ValueError("Evidence references must be bounded opaque identifiers")
            if contains_secret(value):
                raise ValueError("Secret-like material is forbidden in evidence references")
        return values

    @model_validator(mode="after")
    def validate_hold_exclusivity(self) -> CognitiveDecisionEnvelope:
        if self.owner_interrupt_required and self.provider_runtime_hold:
            raise ValueError("Owner and provider holds cannot both be asserted")
        return self


class CognitiveBindingPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_id: Literal["MODISA_COGNITIVE_BINDING_POLICY_V1"] = Field(alias="schema")
    version: str
    depends_on: list[str]
    authority_ceiling: Literal["A1"]
    effect_class: Literal["NO_EXTERNAL_EFFECT"]
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_policy: str
    admission: Literal["MERGED_PR_1029"]


class CognitiveBindingReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_id: Literal["MODISA_COGNITIVE_BINDING_RECEIPT_V1"] = Field(
        default="MODISA_COGNITIVE_BINDING_RECEIPT_V1", alias="schema"
    )
    version: str = BINDING_VERSION
    matter_id: str
    mission_id: str
    state: CognitiveBindingState
    proof_id: str
    proof_payload_sha256: str
    proof_chain_head: str
    policy_sha256: str
    reused_existing: bool
    authority_ceiling: Literal["A1"] = "A1"
    external_effects: Literal[0] = 0
    hmac_verified: Literal[True] = True


def _load_policy(path: Path) -> CognitiveBindingPolicy:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CognitiveBindingVerificationError("Cognitive binding policy is unreadable") from exc
    if not isinstance(raw, dict):
        raise CognitiveBindingVerificationError("Cognitive binding policy must be an object")
    try:
        return CognitiveBindingPolicy.model_validate(cast(dict[str, Any], raw))
    except ValidationError as exc:
        raise CognitiveBindingVerificationError("Cognitive binding policy is invalid") from exc


class CognitiveBindingAdapter:
    """Validate and HMAC-bind a cognitive decision inside MODISA's A1 boundary."""

    def __init__(self, ledger: ProofLedger, *, policy_path: Path | None = None) -> None:
        default_path = Path(__file__).parent / "policies" / "bco_modisa_sol61_binding_policy_v1.json"
        self.ledger = ledger
        self.policy = _load_policy(policy_path or default_path)
        if self.policy.depends_on != ["CFBE"]:
            raise CognitiveBindingVerificationError(
                "Cognitive binding policy must depend only on the registered CFBE capability"
            )
        self.policy_sha256 = sha256_json(self.policy.model_dump(mode="json", by_alias=True))

    def _existing_receipt(
        self,
        *,
        envelope: CognitiveDecisionEnvelope,
        subject_id: str,
        payload: dict[str, Any],
        state: CognitiveBindingState,
    ) -> CognitiveBindingReceipt | None:
        matches = [
            proof
            for proof in self.ledger.list_for_mission(envelope.matter_id, envelope.mission_id)
            if proof.proof_type == ProofType.COGNITIVE_BINDING
            and proof.subject_id == subject_id
        ]
        if len(matches) > 1:
            raise CognitiveBindingCollisionError("Duplicate cognitive-binding proofs detected")
        if not matches:
            return None
        existing = matches[0]
        if existing.payload != payload:
            raise CognitiveBindingCollisionError(
                "Cognitive idempotency key is bound to different decision content"
            )
        valid, reason = self.ledger.verify_record(existing)
        if not valid:
            raise CognitiveBindingVerificationError(
                f"Existing cognitive-binding proof is invalid: {reason}"
            )
        chain = self.ledger.verify_chain(envelope.matter_id)
        if not chain.valid or chain.head_hash is None:
            raise CognitiveBindingVerificationError(
                f"Existing cognitive-binding chain is invalid: {chain.reason}"
            )
        return CognitiveBindingReceipt(
            matter_id=envelope.matter_id,
            mission_id=envelope.mission_id,
            state=state,
            proof_id=existing.proof_id,
            proof_payload_sha256=existing.payload_hash,
            proof_chain_head=chain.head_hash,
            policy_sha256=self.policy_sha256,
            reused_existing=True,
        )

    def bind(self, envelope: CognitiveDecisionEnvelope) -> CognitiveBindingReceipt:
        if envelope.dependency_handle not in self.policy.depends_on:
            raise CognitiveBindingVerificationError("Unregistered cognitive dependency handle")
        if sha256_text(envelope.objective) != envelope.objective_sha256:
            raise CognitiveBindingVerificationError("Objective digest mismatch")
        if envelope.dispatch_authorized or envelope.external_effect_authorized:
            raise CognitiveBindingVerificationError(
                "Cognitive envelope attempts to widen dispatch or external-effect authority"
            )
        if not self.ledger.ready:
            raise CognitiveBindingVerificationError("Proof-ledger HMAC key is unavailable")

        if envelope.owner_interrupt_required:
            state = CognitiveBindingState.HOLD_OWNER
        elif envelope.provider_runtime_hold:
            state = CognitiveBindingState.HOLD_PROVIDER
        else:
            state = CognitiveBindingState.ADMITTED_INTERNAL

        subject_id = (
            f"COGNITIVE_BINDING:{envelope.mission_id}:{envelope.producer_receipt_sha256}"
        )
        payload: dict[str, Any] = {
            "schema": BINDING_SCHEMA,
            "version": BINDING_VERSION,
            "state": state.value,
            "dependency_handle": envelope.dependency_handle,
            "objective_sha256": envelope.objective_sha256,
            "producer_receipt_sha256": envelope.producer_receipt_sha256,
            "dispatch_authorized": False,
            "external_effect_authorized": False,
            "evidence_refs": envelope.evidence_refs,
            "policy_sha256": self.policy_sha256,
            "authority_ceiling": self.policy.authority_ceiling,
            "external_effects": 0,
        }

        existing_receipt = self._existing_receipt(
            envelope=envelope, subject_id=subject_id, payload=payload, state=state
        )
        if existing_receipt is not None:
            return existing_receipt

        try:
            proof = self.ledger.append(
                ProofAppendRequest(
                    matter_id=envelope.matter_id,
                    mission_id=envelope.mission_id,
                    proof_type=ProofType.COGNITIVE_BINDING,
                    subject_id=subject_id,
                    actor_id=ACTOR_ID,
                    source_ids=[
                        f"Federation-Omega@{self.policy.source_commit}",
                        self.policy.source_policy,
                    ],
                    payload=payload,
                )
            )
        except sqlite3.IntegrityError as exc:
            raced_receipt = self._existing_receipt(
                envelope=envelope, subject_id=subject_id, payload=payload, state=state
            )
            if raced_receipt is None:
                raise CognitiveBindingVerificationError(
                    "Cognitive binding append failed without an idempotent proof"
                ) from exc
            return raced_receipt
        valid, reason = self.ledger.verify_record(proof)
        chain = self.ledger.verify_chain(envelope.matter_id)
        if not valid or not chain.valid or chain.head_hash is None:
            raise CognitiveBindingVerificationError(
                f"Generated cognitive-binding proof failed verification: {reason or chain.reason}"
            )
        return CognitiveBindingReceipt(
            matter_id=envelope.matter_id,
            mission_id=envelope.mission_id,
            state=state,
            proof_id=proof.proof_id,
            proof_payload_sha256=proof.payload_hash,
            proof_chain_head=chain.head_hash,
            policy_sha256=self.policy_sha256,
            reused_existing=False,
        )
