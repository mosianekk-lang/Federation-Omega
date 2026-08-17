from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class CapabilityState(str, Enum):
    VERIFIED_LIVE = "VERIFIED_LIVE"
    ACTIVE_PARTIAL = "ACTIVE_PARTIAL"
    BLOCKED_OR_UNVERIFIED = "BLOCKED_OR_UNVERIFIED"
    ADAPTER_REQUIRED = "ADAPTER_REQUIRED"


@dataclass(frozen=True)
class Capability:
    id: str
    modes: tuple[str, ...]
    state: CapabilityState
    authority: str
    proof_ref: str | None = None


@dataclass
class Decision:
    mission_id: str
    action: str
    effectful: bool
    capability: str
    status: str
    reasons: list[str] = field(default_factory=list)
    permit_required: bool = False


class CapabilityFabric:
    def __init__(self) -> None:
        gemini_live = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_CLOUD_PROJECT"))
        self._items = {
            "formation": Capability("formation", ("gate", "learn", "audit"), CapabilityState.VERIFIED_LIVE, "local"),
            "science": Capability("science", ("calculate", "hypothesize", "falsify"), CapabilityState.VERIFIED_LIVE, "local"),
            "gemini": Capability("gemini", ("reason", "multimodal", "function_call", "live"), CapabilityState.VERIFIED_LIVE if gemini_live else CapabilityState.ADAPTER_REQUIRED, "GOOGLE_API_KEY or ADC"),
            "drive": Capability("drive", ("search", "read", "write"), CapabilityState.ADAPTER_REQUIRED, "incremental OAuth or service account"),
            "gmail": Capability("gmail", ("search", "read", "draft", "send"), CapabilityState.ADAPTER_REQUIRED, "incremental OAuth"),
            "sheets": Capability("sheets", ("read", "calculate", "write"), CapabilityState.ADAPTER_REQUIRED, "incremental OAuth"),
            "calendar": Capability("calendar", ("read", "schedule"), CapabilityState.ADAPTER_REQUIRED, "incremental OAuth"),
            "github": Capability("github", ("source", "ci", "release"), CapabilityState.ACTIVE_PARTIAL, "GitHub App"),
            "federation_mcp": Capability("federation_mcp", ("discover", "invoke"), CapabilityState.ACTIVE_PARTIAL, "per-server token"),
        }

    def inventory(self) -> list[dict[str, Any]]:
        return [asdict(v) for v in self._items.values()]

    def get(self, capability: str) -> Capability | None:
        return self._items.get(capability)


class FormationKernel:
    """Small executor-level gate. It does not mint external authority."""

    EFFECTFUL = {"write", "send", "delete", "deploy", "promote", "schedule", "purchase", "grant"}

    def decide(self, mission_id: str, action: str, capability: Capability | None, permit: str | None = None) -> Decision:
        verb = action.strip().split(" ", 1)[0].lower()
        effectful = verb in self.EFFECTFUL
        reasons: list[str] = []
        if not mission_id.strip():
            reasons.append("MISSION_REQUIRED")
        if capability is None:
            reasons.append("CAPABILITY_UNKNOWN")
        elif capability.state in {CapabilityState.BLOCKED_OR_UNVERIFIED, CapabilityState.ADAPTER_REQUIRED}:
            reasons.append("CAPABILITY_NOT_LIVE")
        if effectful and not permit:
            reasons.append("SINGLE_USE_PERMIT_REQUIRED")
        return Decision(mission_id, action, effectful, capability.id if capability else "unknown", "DENY" if reasons else "EXECUTE", reasons, effectful)


class LearningLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, route: str, outcome: str, elapsed_ms: int, evidence: str) -> dict[str, Any]:
        previous = "GENESIS"
        if self.path.exists():
            lines = [x for x in self.path.read_text(encoding="utf-8").splitlines() if x]
            if lines:
                previous = json.loads(lines[-1])["hash"]
        event = {"route": route, "outcome": outcome, "elapsedMs": elapsed_ms, "evidence": evidence, "previous": previous, "recordedAt": int(time.time())}
        event["hash"] = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True) + "\n")
        return event

    def verify(self) -> bool:
        previous = "GENESIS"
        if not self.path.exists():
            return True
        for line in self.path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            digest = event.pop("hash")
            if event["previous"] != previous or hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest() != digest:
                return False
            previous = digest
        return True


class CircuitBreaker:
    def __init__(self, threshold: int = 2) -> None:
        self.threshold = threshold
        self.failures: dict[str, int] = {}
        self.quarantined: set[str] = set()

    def record(self, route: str, success: bool) -> None:
        if success:
            self.failures[route] = 0
        else:
            self.failures[route] = self.failures.get(route, 0) + 1
            if self.failures[route] >= self.threshold:
                self.quarantined.add(route)


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def semantic_fingerprint(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode()).hexdigest()
