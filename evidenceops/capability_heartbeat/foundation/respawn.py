"""Respawn contract proving local continuity without claiming live attachment."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import Authority, MATURITY, digest, parse_utc
from .errors import ContractError, HeartbeatError
from .ledger import ImmutableEventLedger
from .master_bible import MasterBiblePolicy
from .privacy import require_code, require_hash
from .registry import NodeRegistry
from .stop_control import StopControl


@dataclass(frozen=True, slots=True)
class RespawnManifest:
    manifest_code: str
    master_node_id: str
    parent_transaction_id: str
    policy_hash: str
    registry_hash: str
    ledger_tail_hash: str
    ledger_event_count: int
    root_node_generation: int
    control_generation: int
    authority_ceiling: Authority
    registration_receipts: tuple[str, ...]
    generated_at: str
    expires_at: str
    max_hops: int = 3
    recommendation_only: bool = True
    live_master_bible_attachment: bool = False
    active_chat_inventory: bool = False
    per_chat_emitters: bool = False
    unsolicited_injection: bool = False
    system_wide_awareness: bool = False
    maturity: str = MATURITY

    def __post_init__(self) -> None:
        if not isinstance(self.registration_receipts, (tuple, list)):
            raise ContractError("REGISTRATION_RECEIPTS_SEQUENCE_REQUIRED")
        object.__setattr__(self, "registration_receipts", tuple(self.registration_receipts))
        for field_name in ("manifest_code", "master_node_id"):
            require_code(getattr(self, field_name), field=field_name)
        for field_name in ("parent_transaction_id", "policy_hash", "registry_hash", "ledger_tail_hash"):
            require_hash(getattr(self, field_name), field=field_name)
        for receipt in self.registration_receipts:
            require_hash(receipt, field="registration_receipts")
        if len(set(self.registration_receipts)) != len(self.registration_receipts):
            raise ContractError("DUPLICATE_REGISTRATION_RECEIPT")
        if isinstance(self.ledger_event_count, bool) or not isinstance(self.ledger_event_count, int) or self.ledger_event_count < 0:
            raise ContractError("INVALID_LEDGER_EVENT_COUNT")
        for field_name in ("root_node_generation", "control_generation"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ContractError(f"INVALID_NONNEGATIVE_INTEGER:{field_name}")
        if self.authority_ceiling is not Authority.A0:
            raise ContractError("RESPAWN_AUTHORITY_MUST_BE_A0")
        if self.max_hops != 3 or not self.recommendation_only:
            raise ContractError("RESPAWN_POLICY_INVARIANT_FAILED")
        if any(
            (
                self.live_master_bible_attachment,
                self.active_chat_inventory,
                self.per_chat_emitters,
                self.unsolicited_injection,
                self.system_wide_awareness,
            )
        ):
            raise ContractError("UNPROVEN_LIVE_CAPABILITY_CLAIM")
        if self.maturity != MATURITY:
            raise ContractError("INVALID_MATURITY")
        generated = parse_utc(self.generated_at, field="generated_at")
        expires = parse_utc(self.expires_at, field="expires_at")
        if expires <= generated or (expires - generated).total_seconds() > 300:
            raise ContractError("RESPAWN_EXPIRY_INVALID")

    @property
    def manifest_hash(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class RespawnReadback:
    valid: bool
    manifest_hash: str
    registry_node_count: int
    ledger_event_count: int
    maturity: str = MATURITY


def verify_respawn(
    *,
    manifest: RespawnManifest,
    policy: MasterBiblePolicy,
    registry: NodeRegistry,
    ledger: ImmutableEventLedger,
    stop_control: StopControl,
    now: str,
) -> RespawnReadback:
    current = parse_utc(now, field="now")
    generated = parse_utc(manifest.generated_at, field="generated_at")
    if generated > current:
        raise ContractError("RESPAWN_MANIFEST_FUTURE_DATED")
    if (current - generated).total_seconds() > 300:
        raise ContractError("RESPAWN_MANIFEST_STALE")
    if current >= parse_utc(manifest.expires_at, field="expires_at"):
        raise ContractError("RESPAWN_MANIFEST_EXPIRED")
    registry_readback = registry.semantic_readback()
    try:
        registry_records_fresh = all(
            registry.assert_fresh(item.node_id, now=now) == item for item in registry.records
        )
    except HeartbeatError:
        registry_records_fresh = False
    ledger_readback = ledger.semantic_readback(
        expected_count=manifest.ledger_event_count,
        expected_tail=manifest.ledger_tail_hash,
        expected_generation=manifest.control_generation,
    )
    expected_receipts = tuple(sorted(item.registration_receipt for item in registry.records))
    roots = tuple(registry_readback["root_node_ids"])
    root_record = registry.get(roots[0]) if len(roots) == 1 else None
    parent_events = tuple(
        item for item in ledger.events if item.event_hash == manifest.parent_transaction_id
    )
    parent_event = parent_events[0] if len(parent_events) == 1 else None
    valid = all(
        (
            manifest.master_node_id == policy.root_node_id,
            roots == (policy.root_node_id,),
            root_record is not None,
            root_record is not None and root_record.node_id == policy.root_node_id,
            root_record is not None and root_record.owner_code == policy.owner_code,
            root_record is not None and root_record.matter_code == policy.matter_code,
            root_record is not None and root_record.classification == policy.classification,
            root_record is not None and root_record.authority_ceiling == policy.authority_ceiling,
            manifest.authority_ceiling == policy.authority_ceiling,
            root_record is not None and root_record.schema_version == policy.schema_version,
            root_record is not None and root_record.adapter_version == policy.adapter_version,
            root_record is not None
            and root_record.signer_identity.signing_version == policy.signing_version,
            root_record is not None and root_record.generation == policy.root_generation,
            root_record is not None and manifest.root_node_generation == root_record.generation,
            root_record is not None and root_record.control_generation == manifest.control_generation,
            manifest.policy_hash == policy.policy_hash,
            manifest.registry_hash == registry.registry_hash,
            policy.control_generation == manifest.control_generation,
            manifest.control_generation == stop_control.generation,
            stop_control.active,
            registry_readback["valid"],
            registry_records_fresh,
            ledger_readback.valid,
            all(item.control_generation == manifest.control_generation for item in registry.records),
            parent_event is not None,
            parent_event is not None and parent_event.entity_code == manifest.master_node_id,
            parent_event is not None and parent_event.control_generation == manifest.control_generation,
            parent_event is not None and parse_utc(parent_event.occurred_at, field="parent_event.occurred_at") <= generated,
            tuple(sorted(manifest.registration_receipts)) == expected_receipts,
        )
    )
    return RespawnReadback(
        valid=valid,
        manifest_hash=manifest.manifest_hash,
        registry_node_count=len(registry.records),
        ledger_event_count=len(ledger.events),
    )
