"""Master Bible propagation root and non-widening inheritance helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import (
    SCHEMA_VERSION,
    SUPPORTED_SIGNING_VERSIONS,
    Authority,
    Classification,
    MATURITY,
    NodeType,
    SignerIdentity,
    digest,
    enum_value,
)
from .errors import ContractError
from .privacy import require_code, require_hash
from .registry import NodeRecord, NodeRegistry


def build_policy_hash(
    *,
    root_node_id: str,
    owner_code: str,
    matter_code: str,
    classification: Classification,
    control_generation: int,
    schema_version: str,
    adapter_version: str,
    signing_version: str,
    root_generation: int,
    authority_ceiling: Authority,
    max_hops: int,
    recommendation_only: bool,
    live_attachment: bool,
    active_chat_inventory: bool,
    unsolicited_injection: bool,
    system_wide_awareness: bool,
    maturity: str,
) -> str:
    """Canonical digest of every field that defines Master Bible policy."""
    return digest(
        {
            "root_node_id": root_node_id,
            "owner_code": owner_code,
            "matter_code": matter_code,
            "classification": classification,
            "control_generation": control_generation,
            "schema_version": schema_version,
            "adapter_version": adapter_version,
            "signing_version": signing_version,
            "root_generation": root_generation,
            "authority_ceiling": authority_ceiling,
            "max_hops": max_hops,
            "recommendation_only": recommendation_only,
            "live_attachment": live_attachment,
            "active_chat_inventory": active_chat_inventory,
            "unsolicited_injection": unsolicited_injection,
            "system_wide_awareness": system_wide_awareness,
            "maturity": maturity,
        }
    )


@dataclass(frozen=True, slots=True)
class MasterBiblePolicy:
    root_node_id: str
    owner_code: str
    matter_code: str
    classification: Classification
    control_generation: int
    policy_hash: str
    schema_version: str = SCHEMA_VERSION
    adapter_version: str = "LOCAL-0.1"
    signing_version: str = "HMAC-0.1"
    root_generation: int = 0
    authority_ceiling: Authority = Authority.A0
    max_hops: int = 3
    recommendation_only: bool = True
    live_attachment: bool = False
    active_chat_inventory: bool = False
    unsolicited_injection: bool = False
    system_wide_awareness: bool = False
    maturity: str = MATURITY

    def __post_init__(self) -> None:
        object.__setattr__(self, "classification", enum_value(Classification, self.classification, field="classification"))
        object.__setattr__(self, "authority_ceiling", enum_value(Authority, self.authority_ceiling, field="authority_ceiling"))
        for field_name in ("root_node_id", "owner_code", "matter_code"):
            require_code(getattr(self, field_name), field=field_name)
        for field_name in ("schema_version", "adapter_version", "signing_version"):
            require_code(getattr(self, field_name), field=field_name)
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError("MASTER_BIBLE_SCHEMA_VERSION_UNSUPPORTED")
        if self.signing_version not in SUPPORTED_SIGNING_VERSIONS:
            raise ContractError("MASTER_BIBLE_SIGNING_VERSION_UNSUPPORTED")
        for field_name in ("root_generation", "control_generation"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ContractError(f"INVALID_NONNEGATIVE_INTEGER:{field_name}")
        require_hash(self.policy_hash, field="policy_hash")
        expected_policy_hash = build_policy_hash(
            root_node_id=self.root_node_id,
            owner_code=self.owner_code,
            matter_code=self.matter_code,
            classification=self.classification,
            control_generation=self.control_generation,
            schema_version=self.schema_version,
            adapter_version=self.adapter_version,
            signing_version=self.signing_version,
            root_generation=self.root_generation,
            authority_ceiling=self.authority_ceiling,
            max_hops=self.max_hops,
            recommendation_only=self.recommendation_only,
            live_attachment=self.live_attachment,
            active_chat_inventory=self.active_chat_inventory,
            unsolicited_injection=self.unsolicited_injection,
            system_wide_awareness=self.system_wide_awareness,
            maturity=self.maturity,
        )
        if self.policy_hash != expected_policy_hash:
            raise ContractError("MASTER_BIBLE_POLICY_HASH_MISMATCH")
        if self.authority_ceiling is not Authority.A0:
            raise ContractError("MASTER_BIBLE_POLICY_CEILING_MUST_BE_A0")
        if self.max_hops != 3 or not self.recommendation_only:
            raise ContractError("MASTER_BIBLE_POLICY_SAFETY_INVARIANT_FAILED")
        if any((self.live_attachment, self.active_chat_inventory, self.unsolicited_injection, self.system_wide_awareness)):
            raise ContractError("UNPROVEN_LIVE_CAPABILITY_CLAIM")
        if self.maturity != MATURITY:
            raise ContractError("INVALID_MATURITY")

    @classmethod
    def create(
        cls,
        *,
        root_node_id: str,
        owner_code: str,
        matter_code: str,
        classification: Classification,
        control_generation: int,
    ) -> "MasterBiblePolicy":
        policy_hash = build_policy_hash(
            root_node_id=root_node_id,
            owner_code=owner_code,
            matter_code=matter_code,
            classification=classification,
            control_generation=control_generation,
            schema_version=SCHEMA_VERSION,
            adapter_version="LOCAL-0.1",
            signing_version="HMAC-0.1",
            root_generation=0,
            authority_ceiling=Authority.A0,
            max_hops=3,
            recommendation_only=True,
            live_attachment=False,
            active_chat_inventory=False,
            unsolicited_injection=False,
            system_wide_awareness=False,
            maturity=MATURITY,
        )
        return cls(
            root_node_id=root_node_id,
            owner_code=owner_code,
            matter_code=matter_code,
            classification=classification,
            control_generation=control_generation,
            policy_hash=policy_hash,
        )

    def root_record(
        self,
        *,
        observed_at: str,
        expires_at: str,
        capability_hash: str,
        endpoint_reference_hash: str,
        registration_receipt: str,
        signer_identity: SignerIdentity,
    ) -> NodeRecord:
        if signer_identity.signing_version != self.signing_version:
            raise ContractError("ROOT_SIGNING_VERSION_POLICY_MISMATCH")
        return NodeRecord(
            node_id=self.root_node_id,
            node_type=NodeType.MASTER_BIBLE,
            parent_node_id=None,
            generation=self.root_generation,
            owner_code=self.owner_code,
            matter_code=self.matter_code,
            classification=self.classification,
            schema_version=self.schema_version,
            adapter_version=self.adapter_version,
            capability_hash=capability_hash,
            authority_ceiling=Authority.A0,
            observed_at=observed_at,
            expires_at=expires_at,
            control_generation=self.control_generation,
            endpoint_reference_hash=endpoint_reference_hash,
            signer_identity=signer_identity,
            registration_receipt=registration_receipt,
        )

    def inherit_child(
        self,
        *,
        registry: NodeRegistry,
        parent_node_id: str,
        child_node_id: str,
        node_type: NodeType,
        observed_at: str,
        expires_at: str,
        capability_hash: str,
        endpoint_reference_hash: str,
        registration_receipt: str,
        signer_identity: SignerIdentity,
        requested_authority: Authority = Authority.A0,
        requested_classification: Classification | None = None,
    ) -> NodeRecord:
        parent = registry.get(parent_node_id)
        if parent.owner_code != self.owner_code or parent.matter_code != self.matter_code:
            raise ContractError("PARENT_OUTSIDE_MASTER_BIBLE_SCOPE")
        return NodeRecord(
            node_id=child_node_id,
            node_type=node_type,
            parent_node_id=parent_node_id,
            generation=parent.generation + 1,
            owner_code=parent.owner_code,
            matter_code=parent.matter_code,
            classification=requested_classification or parent.classification,
            schema_version=parent.schema_version,
            adapter_version=parent.adapter_version,
            capability_hash=capability_hash,
            authority_ceiling=requested_authority,
            observed_at=observed_at,
            expires_at=expires_at,
            control_generation=parent.control_generation,
            endpoint_reference_hash=endpoint_reference_hash,
            signer_identity=signer_identity,
            registration_receipt=registration_receipt,
        )
