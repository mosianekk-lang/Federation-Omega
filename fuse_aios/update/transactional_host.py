#!/usr/bin/env python3
"""Deterministic FUSE AI-OS transactional A/B host state machine.

This is a control-plane proof model. It does not claim real block-device,
firmware, bootloader, or filesystem rollback until those paths are exercised
against real artifacts and devices.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _valid_digest(value: str) -> str:
    if not _SHA256.fullmatch(value):
        raise ValueError("digest must be lowercase SHA-256 hex")
    return value


@dataclass
class Slot:
    version: str | None = None
    digest: str | None = None
    status: str = "EMPTY"

    def mapping(self) -> dict[str, Any]:
        return {"version": self.version, "digest": self.digest, "status": self.status}


class TransactionalHost:
    def __init__(self, base_version: str, base_digest: str) -> None:
        if not base_version:
            raise ValueError("base_version required")
        self.slots = {
            "A": Slot(base_version, _valid_digest(base_digest), "GOOD"),
            "B": Slot(),
        }
        self.active_slot = "A"
        self.previous_slot: str | None = None
        self.candidate_slot: str | None = None
        self.state = "IDLE"
        self.transitions: list[dict[str, Any]] = []

    def _record(self, event: str, **fields: Any) -> None:
        self.transitions.append({"seq": len(self.transitions) + 1, "event": event, **fields})

    def stage(self, version: str, digest: str) -> str:
        if self.state not in {"IDLE", "COMMITTED", "ROLLED_BACK"}:
            raise RuntimeError(f"cannot stage from {self.state}")
        if not version:
            raise ValueError("version required")
        digest = _valid_digest(digest)
        target = "B" if self.active_slot == "A" else "A"
        self.slots[target] = Slot(version, digest, "STAGED")
        self.candidate_slot = target
        self.previous_slot = None
        self.state = "STAGED"
        self._record("STAGE", active=self.active_slot, candidate=target, version=version, digest=digest)
        return target

    def activate(self) -> str:
        if self.state != "STAGED" or self.candidate_slot is None:
            raise RuntimeError("activation requires a staged candidate")
        self.previous_slot = self.active_slot
        self.active_slot = self.candidate_slot
        self.slots[self.active_slot].status = "PENDING_HEALTH"
        self.state = "PENDING_HEALTH"
        self._record("ACTIVATE", previous=self.previous_slot, active=self.active_slot)
        return self.active_slot

    def evaluate_health(self, healthy: bool) -> str:
        if self.state != "PENDING_HEALTH" or self.previous_slot is None:
            raise RuntimeError("health evaluation requires pending activation")
        if healthy:
            self.slots[self.active_slot].status = "GOOD"
            old = self.previous_slot
            self.previous_slot = None
            self.candidate_slot = None
            self.state = "COMMITTED"
            self._record("COMMIT", active=self.active_slot, previous=old)
            return "COMMITTED"
        return self._rollback("HEALTH_FAILED")

    def recover_after_interruption(self) -> str:
        if self.state != "PENDING_HEALTH" or self.previous_slot is None:
            raise RuntimeError("recovery requires interrupted pending activation")
        return self._rollback("INTERRUPTED_PENDING_HEALTH")

    def _rollback(self, reason: str) -> str:
        failed = self.active_slot
        restored = self.previous_slot
        assert restored is not None
        self.slots[failed].status = "QUARANTINED"
        self.active_slot = restored
        self.slots[restored].status = "GOOD"
        self.previous_slot = None
        self.candidate_slot = None
        self.state = "ROLLED_BACK"
        self._record("ROLLBACK", failed=failed, restored=restored, reason=reason)
        return "ROLLED_BACK"

    def receipt(self) -> dict[str, Any]:
        return {
            "schema": "FUSE-AIOS-TRANSACTIONAL-HOST-RECEIPT-V1",
            "state": self.state,
            "active_slot": self.active_slot,
            "slots": {name: slot.mapping() for name, slot in sorted(self.slots.items())},
            "transitions": list(self.transitions),
            "truth": "TRANSACTIONAL_UPDATE_STATE_MACHINE_PROVED",
            "real_block_device_rollback_proved": False,
            "firmware_or_bootloader_rollback_proved": False,
        }
