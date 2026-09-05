from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping, Sequence


class CarrierKind(str, Enum):
    GITHUB_ACTIONS = "GITHUB_ACTIONS"
    CLOUD_RUN = "CLOUD_RUN"
    APPS_SCRIPT = "APPS_SCRIPT"
    DURABLE_WORKER = "DURABLE_WORKER"
    SCHEDULED_AUTOMATION = "SCHEDULED_AUTOMATION"


@dataclass(frozen=True)
class CarrierCapability:
    carrier_id: str
    kind: CarrierKind
    durable_state: bool
    cross_process_resume: bool
    event_wake: bool
    zero_compute_wait: bool
    idempotent_step: bool
    independent_readback: bool
    external_effect: bool = False
    provider_verified: bool = False


@dataclass(frozen=True)
class CarrierQualification:
    carrier_id: str
    level7_continuity_candidate: bool
    missing: tuple[str, ...]
    provider_verified: bool
    external_effect_authorized: bool
    receipt: str


def qualify_carrier(capability: CarrierCapability) -> CarrierQualification:
    required = {
        "durable_state": capability.durable_state,
        "cross_process_resume": capability.cross_process_resume,
        "event_wake": capability.event_wake,
        "zero_compute_wait": capability.zero_compute_wait,
        "idempotent_step": capability.idempotent_step,
        "independent_readback": capability.independent_readback,
    }
    missing = tuple(sorted(name for name, present in required.items() if not present))
    candidate = not missing and (not capability.external_effect or capability.provider_verified)
    payload = {
        "carrier_id": capability.carrier_id,
        "kind": capability.kind.value,
        "candidate": candidate,
        "missing": missing,
        "provider_verified": capability.provider_verified,
        "external_effect_authorized": False,
    }
    receipt = "sha256:" + sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return CarrierQualification(
        carrier_id=capability.carrier_id,
        level7_continuity_candidate=candidate,
        missing=missing,
        provider_verified=capability.provider_verified,
        external_effect_authorized=False,
        receipt=receipt,
    )


def select_carrier(
    carriers: Sequence[CarrierCapability],
    *,
    require_external_effect: bool = False,
) -> CarrierQualification | None:
    qualified = [qualify_carrier(carrier) for carrier in carriers]
    by_id: Mapping[str, CarrierCapability] = {carrier.carrier_id: carrier for carrier in carriers}
    eligible = []
    for item in qualified:
        capability = by_id[item.carrier_id]
        if not item.level7_continuity_candidate:
            continue
        if require_external_effect and not capability.external_effect:
            continue
        if require_external_effect and not capability.provider_verified:
            continue
        eligible.append(item)
    if not eligible:
        return None
    return sorted(eligible, key=lambda item: item.carrier_id)[0]


def no_chat_continuity_claim(
    *,
    qualification: CarrierQualification,
    observed_resume_receipts: Sequence[str],
    minimum_observed_resumes: int = 3,
) -> bool:
    if minimum_observed_resumes <= 0:
        raise ValueError("minimum_observed_resumes must be positive")
    if not qualification.level7_continuity_candidate:
        return False
    receipts = tuple(dict.fromkeys(receipt for receipt in observed_resume_receipts if receipt))
    return len(receipts) >= minimum_observed_resumes
