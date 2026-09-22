from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProviderEventState(str, Enum):
    WAITING = "WAITING"
    WOKEN = "WOKEN"
    READBACK_VERIFIED = "READBACK_VERIFIED"
    HELD = "HELD"


@dataclass(frozen=True)
class ProviderEventReceipt:
    event_id: str
    provider_id: str
    zero_compute_wait_observed: bool
    event_wake_observed: bool
    cross_machine_handoff_observed: bool
    provider_native_readback: bool
    external_effect: bool
    state: ProviderEventState


def evaluate_provider_event_semantics(receipt: ProviderEventReceipt) -> ProviderEventState:
    if receipt.external_effect:
        return ProviderEventState.HELD
    if receipt.provider_native_readback and receipt.event_wake_observed and receipt.zero_compute_wait_observed and receipt.cross_machine_handoff_observed:
        return ProviderEventState.READBACK_VERIFIED
    if receipt.event_wake_observed:
        return ProviderEventState.WOKEN
    if receipt.zero_compute_wait_observed:
        return ProviderEventState.WAITING
    return ProviderEventState.HELD
