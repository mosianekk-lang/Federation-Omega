from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import EventClass, OwnerBoundary


@dataclass(frozen=True)
class InstitutionalEvent:
    event_id: str
    event_class: EventClass
    source_system: str
    source_sha: str
    objective_id: str | None
    lane_id: str
    proof_refs: tuple[str, ...]
    owner_boundary: OwnerBoundary
    external_effect: bool
    payload_digest: str

    def digest(self) -> str:
        payload = {
            "event_id": self.event_id,
            "event_class": self.event_class.value,
            "source_system": self.source_system,
            "source_sha": self.source_sha,
            "objective_id": self.objective_id,
            "lane_id": self.lane_id,
            "proof_refs": sorted(set(self.proof_refs)),
            "owner_boundary": self.owner_boundary.value,
            "external_effect": self.external_effect,
            "payload_digest": self.payload_digest,
        }
        return "sha256:" + sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


def validate_institutional_event(event: InstitutionalEvent) -> Mapping[str, object]:
    if not event.event_id or not event.source_system or not event.source_sha or not event.lane_id:
        raise ValueError("event identity fields are required")
    if not event.payload_digest.startswith("sha256:"):
        raise ValueError("payload must be digest-only")
    if event.external_effect and event.owner_boundary == OwnerBoundary.NONE:
        raise ValueError("external effect requires explicit boundary classification")
    return {
        "event_id": event.event_id,
        "event_class": event.event_class.value,
        "event_digest": event.digest(),
        "raw_payload_stored": False,
        "authority_inherited": False,
    }
