from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable, Mapping

from benchmarking.cfbe_omega.bible_memory_fabric_v1 import MemoryEvent
from federation.mission_ir import MissionIR


_RESULT_STATES = frozenset({"SUCCESS", "BLOCKED", "FAILED", "IN_PROGRESS"})
_EFFECTFUL_CLASSES = frozenset({"BOUNDED_EFFECT", "CONSEQUENTIAL_EFFECT"})


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(item).strip() for item in values if str(item).strip()}))


@dataclass(frozen=True, slots=True)
class MissionResultCapture:
    """Privacy-minimal result envelope supplied by Bubbles or another MissionIR consumer.

    Raw model/tool/provider payloads do not belong here. Rich content remains behind
    result/source/proof references; the memory event carries state and lineage only.
    """

    state: str
    observed_at: str
    source_refs: tuple[str, ...]
    proof_refs: tuple[str, ...] = ()
    result_ref: str | None = None
    result_sha256: str | None = None
    next_action: str | None = None
    blocker_code: str | None = None
    receiver_readback_ref: str | None = None
    authority_receipt_ref: str | None = None
    metadata: Mapping[str, str] | None = None

    def normalized(self) -> "MissionResultCapture":
        return MissionResultCapture(
            state=self.state.strip().upper(),
            observed_at=self.observed_at.strip(),
            source_refs=_refs(self.source_refs),
            proof_refs=_refs(self.proof_refs),
            result_ref=(self.result_ref or "").strip() or None,
            result_sha256=(self.result_sha256 or "").strip() or None,
            next_action=(self.next_action or "").strip() or None,
            blocker_code=(self.blocker_code or "").strip() or None,
            receiver_readback_ref=(self.receiver_readback_ref or "").strip() or None,
            authority_receipt_ref=(self.authority_receipt_ref or "").strip() or None,
            metadata={str(k).strip(): str(v).strip() for k, v in sorted(dict(self.metadata or {}).items())},
        )

    def validate(self, mission: MissionIR) -> "MissionResultCapture":
        item = self.normalized()
        mission = mission.normalized()
        mission.validate()
        if item.state not in _RESULT_STATES:
            raise ValueError("BMF_CAPTURE_RESULT_STATE_INVALID")
        if not item.observed_at:
            raise ValueError("BMF_CAPTURE_OBSERVED_AT_REQUIRED")
        if not item.source_refs:
            raise ValueError("BMF_CAPTURE_SOURCE_REF_REQUIRED")
        if item.state == "SUCCESS":
            if not item.result_ref or not item.result_sha256 or not item.proof_refs:
                raise ValueError("BMF_CAPTURE_SUCCESS_PROOF_REQUIRED")
            if mission.effect_class in _EFFECTFUL_CLASSES and not item.receiver_readback_ref:
                raise ValueError("BMF_CAPTURE_EFFECT_READBACK_REQUIRED")
            if mission.effect_class == "CONSEQUENTIAL_EFFECT" and not item.authority_receipt_ref:
                raise ValueError("BMF_CAPTURE_CONSEQUENTIAL_AUTHORITY_RECEIPT_REQUIRED")
        if item.state in {"BLOCKED", "FAILED"} and not item.blocker_code:
            raise ValueError("BMF_CAPTURE_BLOCKER_CODE_REQUIRED")
        return item


class BibleMemoryCaptureAdapter:
    """MissionIR/result -> MemoryEvent compiler. It has no provider/storage methods."""

    schema = "CFBE-BMF-CAPTURE-ADAPTER-V1"

    @staticmethod
    def stream_id(mission: MissionIR) -> str:
        mission = mission.normalized()
        mission.validate()
        return f"mission:{mission.mission_id}"

    @staticmethod
    def _identity(mission: MissionIR) -> dict[str, object]:
        item = mission.normalized()
        item.validate()
        metadata = dict(item.metadata)
        return {
            "mission_digest": item.digest(),
            "mission_id": item.mission_id,
            "domain": item.domain,
            "effect_class": item.effect_class,
            "owner_approval_required": item.owner_approval_required,
            "objective_sha256": _digest(item.objective),
            "outcome_contract_sha256": _digest(item.outcome_contract),
            "source_frontier_sha256": _digest(item.source_frontier),
            "metadata_sha256": _digest(metadata),
        }

    @classmethod
    def _event(
        cls,
        mission: MissionIR,
        *,
        stream_version: int,
        event_type: str,
        recorded_at: str,
        payload: Mapping[str, object],
        source_refs: Iterable[str],
        proof_refs: Iterable[str] = (),
        supersedes: Iterable[str] = (),
    ) -> MemoryEvent:
        item = mission.normalized()
        item.validate()
        if stream_version < 1:
            raise ValueError("BMF_CAPTURE_STREAM_VERSION_INVALID")
        recorded_at = str(recorded_at).strip()
        if not recorded_at:
            raise ValueError("BMF_CAPTURE_RECORDED_AT_REQUIRED")
        sources = _refs(source_refs)
        if not sources:
            raise ValueError("BMF_CAPTURE_SOURCE_REF_REQUIRED")
        proofs = _refs(proof_refs)
        superseded = _refs(supersedes)
        safe_payload = dict(payload)
        seed = {
            "schema": cls.schema,
            "stream_id": cls.stream_id(item),
            "stream_version": stream_version,
            "event_type": event_type,
            "recorded_at": recorded_at,
            "mission_digest": item.digest(),
            "payload": safe_payload,
            "source_refs": list(sources),
            "proof_refs": list(proofs),
            "supersedes": list(superseded),
        }
        token = _digest(seed)
        metadata = dict(item.metadata)
        return MemoryEvent(
            event_id=f"bmf-{token[:24]}",
            stream_id=cls.stream_id(item),
            stream_version=stream_version,
            event_type=event_type,
            recorded_at=recorded_at,
            valid_at=recorded_at,
            idempotency_key=f"bmf-idem-{token}",
            truth_class="DERIVED_VERIFIED",
            privacy_class=item.privacy_class,
            payload=safe_payload,
            source_refs=sources,
            proof_refs=proofs,
            directive_id=metadata.get("directive_id") or None,
            mission_id=item.mission_id,
            workstream_id=metadata.get("workstream_id") or item.domain,
            supersedes=superseded,
        ).validate()

    @classmethod
    def capture_mission_compiled(
        cls,
        mission: MissionIR,
        *,
        stream_version: int,
        recorded_at: str,
        source_refs: Iterable[str],
        supersedes: Iterable[str] = (),
    ) -> MemoryEvent:
        item = mission.normalized()
        identity = cls._identity(item)
        payload = {
            **identity,
            "mission_state": "COMPILED",
            "proof_requirement_count": len(item.proof_requirements),
            "authority_requirement_count": len(item.authority_requirements),
            "provider_effect_authorized": False,
            "publication_authorized": False,
        }
        return cls._event(
            item,
            stream_version=stream_version,
            event_type="STATE_SET",
            recorded_at=recorded_at,
            payload=payload,
            source_refs=source_refs,
            supersedes=supersedes,
        )

    @classmethod
    def capture_result(
        cls,
        mission: MissionIR,
        result: MissionResultCapture,
        *,
        stream_version: int,
        supersedes: Iterable[str] = (),
    ) -> MemoryEvent:
        item = mission.normalized()
        result = result.validate(item)
        identity = cls._identity(item)
        metadata_digest = _digest(dict(result.metadata or {}))
        payload: dict[str, object] = {
            **identity,
            "mission_state": result.state,
            "metadata_sha256": metadata_digest,
            "proof_count": len(result.proof_refs),
            "receiver_readback_present": bool(result.receiver_readback_ref),
            "authority_receipt_present": bool(result.authority_receipt_ref),
            "provider_effect_authorized": False,
            "publication_authorized": False,
        }
        if result.result_ref:
            payload["result_ref"] = result.result_ref
        if result.result_sha256:
            payload["result_sha256"] = result.result_sha256
        if result.next_action:
            payload["next_action"] = result.next_action
        if result.blocker_code:
            payload["blocker_code"] = result.blocker_code
        if result.receiver_readback_ref:
            payload["receiver_readback_ref"] = result.receiver_readback_ref
        if result.authority_receipt_ref:
            payload["authority_receipt_ref"] = result.authority_receipt_ref

        if result.state == "SUCCESS":
            event_type = "RESULT_VERIFIED"
        elif result.state in {"BLOCKED", "FAILED"}:
            event_type = "BLOCKER_SET"
        else:
            event_type = "STATE_SET"
        return cls._event(
            item,
            stream_version=stream_version,
            event_type=event_type,
            recorded_at=result.observed_at,
            payload=payload,
            source_refs=result.source_refs,
            proof_refs=result.proof_refs,
            supersedes=supersedes,
        )


__all__ = ["BibleMemoryCaptureAdapter", "MissionResultCapture"]
