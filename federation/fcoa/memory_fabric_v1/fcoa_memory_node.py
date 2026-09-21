from __future__ import annotations
from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Iterable, Mapping

from benchmarking.cfbe_omega.bible_memory_fabric_v1 import InMemoryEventStore, MemoryEvent

FCOA_AGENT_ID = "FCOA-OMEGA"
FCOA_NODE_ID = "NODE-SYS-FCOA-OMEGA"
GLOBAL_PRIVACY = frozenset({"GLOBAL", "P1_GLOBAL", "P1"})
CANONICAL_TRUTH = frozenset({"EVENT_TRUTH", "VERIFIED", "DERIVED_VERIFIED"})
FORBIDDEN_GLOBAL_KEYS = frozenset({"secret", "password", "credential", "token", "medical_raw", "private_raw", "raw_transcript"})


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _clean_refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(v).strip() for v in values if str(v).strip()}))


@dataclass(frozen=True, slots=True)
class IntelligenceProposal:
    topic: str
    summary: str
    recorded_at: str
    source_refs: tuple[str, ...]
    proof_refs: tuple[str, ...] = ()
    causal_parent_ids: tuple[str, ...] = ()
    receiver_scope: str = "ALL_REGISTERED_SYSTEMS"
    privacy_class: str = "GLOBAL"
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> "IntelligenceProposal":
        if not self.topic.strip() or not self.summary.strip() or not self.recorded_at.strip():
            raise ValueError("FCOA_MEMORY_PROPOSAL_REQUIRED_FIELD_MISSING")
        if self.privacy_class not in GLOBAL_PRIVACY:
            raise ValueError("FCOA_MEMORY_GLOBAL_PRIVACY_REQUIRED")
        refs = _clean_refs(self.source_refs)
        if not refs:
            raise ValueError("FCOA_MEMORY_SOURCE_REF_REQUIRED")
        md = {str(k).strip(): str(v).strip() for k, v in dict(self.metadata).items()}
        if FORBIDDEN_GLOBAL_KEYS & {k.casefold() for k in md}:
            raise ValueError("FCOA_MEMORY_SENSITIVE_METADATA_REJECTED")
        return IntelligenceProposal(
            topic=self.topic.strip(), summary=self.summary.strip(), recorded_at=self.recorded_at.strip(),
            source_refs=refs, proof_refs=_clean_refs(self.proof_refs),
            causal_parent_ids=_clean_refs(self.causal_parent_ids), receiver_scope=self.receiver_scope.strip(),
            privacy_class=self.privacy_class, metadata=md,
        )

    @property
    def proposal_id(self) -> str:
        v = self.validate()
        return "fcoa-proposal-" + _digest({"topic":v.topic,"summary":v.summary,"recorded_at":v.recorded_at,"sources":v.source_refs})[:24]


@dataclass(frozen=True, slots=True)
class VerificationReceipt:
    verifier_id: str
    receipt_ref: str
    verified_at: str
    proof_refs: tuple[str, ...]
    verdict: str = "ACCEPT"

    def validate(self) -> "VerificationReceipt":
        if self.verifier_id.strip() == FCOA_AGENT_ID:
            raise ValueError("FCOA_MEMORY_SELF_VERIFICATION_FORBIDDEN")
        if not self.verifier_id.strip() or not self.receipt_ref.strip() or not self.verified_at.strip():
            raise ValueError("FCOA_MEMORY_VERIFICATION_REQUIRED_FIELD_MISSING")
        if self.verdict.strip().upper() != "ACCEPT":
            raise ValueError("FCOA_MEMORY_VERIFICATION_NOT_ACCEPTED")
        proofs = _clean_refs(self.proof_refs)
        if not proofs:
            raise ValueError("FCOA_MEMORY_VERIFICATION_PROOF_REQUIRED")
        return VerificationReceipt(self.verifier_id.strip(), self.receipt_ref.strip(), self.verified_at.strip(), proofs, "ACCEPT")


@dataclass(frozen=True, slots=True)
class Receiver:
    receiver_id: str
    active: bool = True


class ReceiverRegistry:
    def __init__(self, receivers: Iterable[Receiver] = ()):
        self._r = {r.receiver_id: r for r in receivers}

    def register(self, receiver: Receiver) -> None:
        self._r[receiver.receiver_id] = receiver

    def active_ids(self) -> tuple[str, ...]:
        return tuple(sorted(r.receiver_id for r in self._r.values() if r.active))


@dataclass(frozen=True, slots=True)
class FanoutReceipt:
    event_id: str
    event_digest: str
    targets: tuple[str, ...]
    acked: tuple[str, ...]
    pending: tuple[str, ...]
    state: str


class ReceiverFanout:
    def __init__(self, registry: ReceiverRegistry):
        self.registry = registry
        self._targets: dict[str, tuple[str, ...]] = {}
        self._acks: dict[str, set[str]] = {}
        self._digests: dict[str, str] = {}

    def publish(self, event: MemoryEvent) -> FanoutReceipt:
        event.validate()
        if event.truth_class not in CANONICAL_TRUTH:
            raise ValueError("FCOA_MEMORY_FANOUT_REQUIRES_VERIFIED_TRUTH")
        targets = self.registry.active_ids()
        self._targets[event.event_id] = targets
        self._acks.setdefault(event.event_id, set())
        self._digests[event.event_id] = event.digest()
        return self.receipt(event.event_id)

    def ack(self, event_id: str, receiver_id: str, event_digest: str) -> FanoutReceipt:
        if event_id not in self._targets:
            raise ValueError("FCOA_MEMORY_UNKNOWN_FANOUT_EVENT")
        if receiver_id not in self._targets[event_id]:
            raise ValueError("FCOA_MEMORY_UNKNOWN_RECEIVER")
        if self._digests[event_id] != event_digest:
            raise ValueError("FCOA_MEMORY_RECEIVER_DIGEST_MISMATCH")
        self._acks[event_id].add(receiver_id)
        return self.receipt(event_id)

    def receipt(self, event_id: str) -> FanoutReceipt:
        targets = self._targets[event_id]
        acked = tuple(sorted(self._acks[event_id]))
        pending = tuple(x for x in targets if x not in self._acks[event_id])
        return FanoutReceipt(event_id, self._digests[event_id], targets, acked, pending, "CONVERGED" if not pending else "PENDING_ACKS")


class FCOAMemoryNode:
    """Bidirectional FCOA node on the existing Bible Memory Fabric; never a second memory root."""
    schema = "FCOA-BMF-NODE-V1"

    def __init__(self, store: InMemoryEventStore | None = None):
        self.store = store or InMemoryEventStore()

    def ingest(self, event: MemoryEvent):
        event.validate()
        if event.privacy_class not in GLOBAL_PRIVACY:
            raise ValueError("FCOA_MEMORY_ONLY_PORTABLE_GLOBAL_EVENTS")
        if event.truth_class not in CANONICAL_TRUTH:
            raise ValueError("FCOA_MEMORY_UNVERIFIED_EVENT_REJECTED")
        return self.store.append(event, expected_version=self.store.version(event.stream_id))

    def compile_proposal_event(self, proposal: IntelligenceProposal) -> MemoryEvent:
        p = proposal.validate()
        stream = f"fcoa-intel-proposal:{p.topic.casefold().replace(' ','-')}"
        version = self.store.version(stream) + 1
        payload = {
            "producer": FCOA_AGENT_ID,
            "node_id": FCOA_NODE_ID,
            "topic": p.topic,
            "summary": p.summary,
            "receiver_scope": p.receiver_scope,
            "metadata_sha256": _digest(dict(p.metadata)),
            "provider_effect_authorized": False,
            "publication_authorized": False,
            "canonical_promotion_authorized": False,
        }
        return MemoryEvent(
            event_id=p.proposal_id,
            stream_id=stream,
            stream_version=version,
            event_type="INTELLIGENCE_PROPOSED",
            recorded_at=p.recorded_at,
            valid_at=p.recorded_at,
            idempotency_key="fcoa-proposal-idem-" + _digest({"id":p.proposal_id,"payload":payload}),
            truth_class="DERIVED_INTERPRETATION",
            privacy_class=p.privacy_class,
            payload=payload,
            source_refs=p.source_refs,
            proof_refs=p.proof_refs,
            causal_parent_ids=p.causal_parent_ids,
            workstream_id="FCOA_GLOBAL_INTELLIGENCE",
        ).validate()

    def verify_and_accept(self, proposal: IntelligenceProposal, verification: VerificationReceipt) -> MemoryEvent:
        p = proposal.validate()
        v = verification.validate()
        if not p.proof_refs:
            raise ValueError("FCOA_MEMORY_ACCEPTANCE_REQUIRES_PROPOSAL_PROOF")
        stream = f"global-intelligence:{p.topic.casefold().replace(' ','-')}"
        version = self.store.version(stream) + 1
        all_proofs = _clean_refs((*p.proof_refs, *v.proof_refs, v.receipt_ref))
        seed = {"proposal":p.proposal_id,"verifier":v.verifier_id,"proofs":all_proofs,"stream":stream,"version":version}
        event = MemoryEvent(
            event_id="fcoa-global-" + _digest(seed)[:24],
            stream_id=stream,
            stream_version=version,
            event_type="INTELLIGENCE_UPDATE_ACCEPTED",
            recorded_at=v.verified_at,
            valid_at=p.recorded_at,
            idempotency_key="fcoa-global-idem-" + _digest(seed),
            truth_class="DERIVED_VERIFIED",
            privacy_class=p.privacy_class,
            payload={
                "producer": FCOA_AGENT_ID,
                "node_id": FCOA_NODE_ID,
                "topic": p.topic,
                "summary": p.summary,
                "receiver_scope": p.receiver_scope,
                "verification_actor": v.verifier_id,
                "verification_receipt_ref": v.receipt_ref,
                "provider_effect_authorized": False,
                "publication_authorized": False,
                "external_effect_authority_inherited": False,
            },
            source_refs=p.source_refs,
            proof_refs=all_proofs,
            causal_parent_ids=_clean_refs((*p.causal_parent_ids, p.proposal_id)),
            workstream_id="FCOA_GLOBAL_INTELLIGENCE",
        ).validate()
        self.store.append(event, expected_version=self.store.version(stream))
        return event

    def current_global_events(self) -> tuple[MemoryEvent, ...]:
        return tuple(e for e in self.store.all_events() if e.truth_class in CANONICAL_TRUTH and e.privacy_class in GLOBAL_PRIVACY)
