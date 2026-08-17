from __future__ import annotations

import base64
import fcntl
import hashlib
import hmac
import json
import os
import time
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class CapabilityState(str, Enum):
    VERIFIED_LOCAL = "VERIFIED_LOCAL"
    VERIFIED_LIVE = "VERIFIED_LIVE"
    ACTIVE_PARTIAL = "ACTIVE_PARTIAL"
    BLOCKED_OR_UNVERIFIED = "BLOCKED_OR_UNVERIFIED"
    ADAPTER_REQUIRED = "ADAPTER_REQUIRED"


class ActionRisk(str, Enum):
    READ_ONLY = "READ_ONLY"
    EFFECTFUL = "EFFECTFUL"


class TaskState(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRIED = "RETRIED"
    CANCELLED = "CANCELLED"
    DEAD_LETTER = "DEAD_LETTER"
    ROLLED_BACK = "ROLLED_BACK"
    QUARANTINED = "QUARANTINED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True)
class Capability:
    id: str
    modes: tuple[str, ...]
    state: CapabilityState
    authority: str
    proof_ref: str | None = None


@dataclass(frozen=True)
class ActionSpec:
    id: str
    capability: str
    risk: ActionRisk


@dataclass
class Decision:
    mission_id: str
    action_id: str
    risk: str
    capability: str
    status: str
    reasons: list[str] = field(default_factory=list)
    permit_required: bool = False
    permit_consumed: bool = False


ACTION_SPECS = {
    row.id: row
    for row in (
        ActionSpec("formation.audit", "formation", ActionRisk.READ_ONLY),
        ActionSpec("science.calculate", "science", ActionRisk.READ_ONLY),
        ActionSpec("science.explain", "science", ActionRisk.READ_ONLY),
        ActionSpec("gemini.reason", "gemini", ActionRisk.READ_ONLY),
        ActionSpec("drive.search", "drive", ActionRisk.READ_ONLY),
        ActionSpec("drive.read", "drive", ActionRisk.READ_ONLY),
        ActionSpec("drive.write", "drive", ActionRisk.EFFECTFUL),
        ActionSpec("drive.share", "drive", ActionRisk.EFFECTFUL),
        ActionSpec("drive.move", "drive", ActionRisk.EFFECTFUL),
        ActionSpec("gmail.search", "gmail", ActionRisk.READ_ONLY),
        ActionSpec("gmail.read", "gmail", ActionRisk.READ_ONLY),
        ActionSpec("gmail.draft", "gmail", ActionRisk.EFFECTFUL),
        ActionSpec("gmail.send", "gmail", ActionRisk.EFFECTFUL),
        ActionSpec("gmail.forward", "gmail", ActionRisk.EFFECTFUL),
        ActionSpec("gmail.archive", "gmail", ActionRisk.EFFECTFUL),
        ActionSpec("sheets.read", "sheets", ActionRisk.READ_ONLY),
        ActionSpec("sheets.write", "sheets", ActionRisk.EFFECTFUL),
        ActionSpec("calendar.read", "calendar", ActionRisk.READ_ONLY),
        ActionSpec("calendar.schedule", "calendar", ActionRisk.EFFECTFUL),
        ActionSpec("calendar.update", "calendar", ActionRisk.EFFECTFUL),
        ActionSpec("github.source", "github", ActionRisk.READ_ONLY),
        ActionSpec("github.release", "github", ActionRisk.EFFECTFUL),
        ActionSpec("cloud.describe", "google_cloud", ActionRisk.READ_ONLY),
        ActionSpec("cloud.deploy_candidate", "google_cloud", ActionRisk.EFFECTFUL),
        ActionSpec("cloud.promote_candidate", "google_cloud", ActionRisk.EFFECTFUL),
        ActionSpec("federation.discover", "federation_mcp", ActionRisk.READ_ONLY),
        ActionSpec("federation.invoke", "federation_mcp", ActionRisk.EFFECTFUL),
    )
}


class CapabilityFabric:
    """Versioned capability truth; configuration is never treated as live proof."""

    def __init__(self, provider_mode: str = "offline") -> None:
        gemini_state = CapabilityState.ADAPTER_REQUIRED if provider_mode == "offline" else CapabilityState.ACTIVE_PARTIAL
        gemini_proof = None if provider_mode == "offline" else f"configured-unproven:{provider_mode}"
        self._items = {
            "formation": Capability("formation", ("gate", "learn", "audit"), CapabilityState.VERIFIED_LOCAL, "local deterministic kernel", "local-tests"),
            "science": Capability("science", ("calculate", "hypothesize", "falsify"), CapabilityState.VERIFIED_LOCAL, "local deterministic engine", "science-doctrine-v1"),
            "gemini": Capability("gemini", ("reason", "multimodal", "function_call", "live"), gemini_state, "explicit Developer API key or Vertex ADC", gemini_proof),
            "drive": Capability("drive", ("search", "read", "write", "share", "move"), CapabilityState.ADAPTER_REQUIRED, "incremental OAuth or direct resource grant"),
            "gmail": Capability("gmail", ("search", "read", "draft", "send", "forward", "archive"), CapabilityState.ADAPTER_REQUIRED, "incremental user OAuth"),
            "sheets": Capability("sheets", ("read", "calculate", "write"), CapabilityState.ADAPTER_REQUIRED, "incremental OAuth or direct resource grant"),
            "calendar": Capability("calendar", ("read", "schedule", "update"), CapabilityState.ADAPTER_REQUIRED, "incremental user OAuth"),
            "google_cloud": Capability("google_cloud", ("describe", "deploy_candidate", "promote_candidate"), CapabilityState.BLOCKED_OR_UNVERIFIED, "dedicated runtime identity and current IAM readback", "wif-invalid-target"),
            "github": Capability("github", ("source", "ci", "release"), CapabilityState.ACTIVE_PARTIAL, "GitHub App bound to the publishing surface", "current-chat-github-readback"),
            "federation_mcp": Capability("federation_mcp", ("discover", "invoke"), CapabilityState.ACTIVE_PARTIAL, "per-server identity, allowlist and Formation permit", "context-bound-registry"),
        }

    def inventory(self) -> list[dict[str, Any]]:
        return [asdict(v) for v in self._items.values()]

    def get(self, capability: str) -> Capability | None:
        return self._items.get(capability)

    def record_session_semantic_proof(self, capability: str, proof_ref: str) -> None:
        current = self._items.get(capability)
        if current is not None:
            self._items[capability] = replace(current, state=CapabilityState.ACTIVE_PARTIAL, proof_ref=proof_ref)


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def semantic_fingerprint(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode()).hexdigest()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class PermitVerifier:
    """Validates mission/action/capability-bound HMAC permits and consumes nonce once."""

    AUDIENCE = "jarvis-ultimate"

    def __init__(self, secret: str | bytes | None, nonce_path: str | Path, clock: Callable[[], float] = time.time) -> None:
        self.secret = secret.encode() if isinstance(secret, str) else secret
        self.nonce_path = Path(nonce_path)
        self.nonce_path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock

    @classmethod
    def issue(
        cls,
        secret: str | bytes,
        mission_id: str,
        action_id: str,
        capability: str,
        nonce: str,
        issued_at: int,
        expires_at: int,
    ) -> str:
        key = secret.encode() if isinstance(secret, str) else secret
        payload = {
            "version": 1,
            "audience": cls.AUDIENCE,
            "missionId": mission_id,
            "actionId": action_id,
            "capability": capability,
            "nonce": nonce,
            "issuedAt": issued_at,
            "expiresAt": expires_at,
        }
        body = stable_json(payload).encode()
        signature = hmac.new(key, body, hashlib.sha256).digest()
        return f"{_b64encode(body)}.{_b64encode(signature)}"

    def verify_and_optionally_consume(
        self,
        token: str | None,
        mission_id: str,
        action_id: str,
        capability: str,
        consume: bool,
    ) -> tuple[bool, str, bool]:
        if not self.secret:
            return False, "FORMATION_AUTHORITY_UNBOUND", False
        if not token:
            return False, "SINGLE_USE_PERMIT_REQUIRED", False
        try:
            encoded_body, encoded_signature = token.split(".", 1)
            body = _b64decode(encoded_body)
            signature = _b64decode(encoded_signature)
            expected = hmac.new(self.secret, body, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                return False, "PERMIT_SIGNATURE_INVALID", False
            payload = json.loads(body)
        except (ValueError, TypeError, json.JSONDecodeError):
            return False, "PERMIT_MALFORMED", False

        required = {"version", "audience", "missionId", "actionId", "capability", "nonce", "issuedAt", "expiresAt"}
        if set(payload) != required:
            return False, "PERMIT_SCHEMA_INVALID", False
        if payload["version"] != 1 or payload["audience"] != self.AUDIENCE:
            return False, "PERMIT_AUDIENCE_INVALID", False
        if payload["missionId"] != mission_id or payload["actionId"] != action_id or payload["capability"] != capability:
            return False, "PERMIT_BINDING_MISMATCH", False
        now = int(self.clock())
        if not isinstance(payload["issuedAt"], int) or not isinstance(payload["expiresAt"], int):
            return False, "PERMIT_TIME_INVALID", False
        if payload["issuedAt"] > now + 30 or payload["expiresAt"] <= now or payload["expiresAt"] - payload["issuedAt"] > 300:
            return False, "PERMIT_EXPIRED_OR_OUT_OF_BOUNDS", False
        nonce = str(payload["nonce"])
        if len(nonce) < 16 or len(nonce) > 128:
            return False, "PERMIT_NONCE_INVALID", False
        nonce_hash = semantic_fingerprint({"nonce": nonce})
        self.nonce_path.touch(exist_ok=True)
        with self.nonce_path.open("a+", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            fh.seek(0)
            consumed = {line.strip() for line in fh if line.strip()}
            if nonce_hash in consumed:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                return False, "PERMIT_REPLAYED", False
            if consume:
                fh.seek(0, os.SEEK_END)
                fh.write(nonce_hash + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        return True, "PERMIT_VALID", consume


class FormationKernel:
    """Exact action-schema gate. It validates but never creates external authority."""

    def __init__(self, permit_verifier: PermitVerifier | None = None) -> None:
        self.permit_verifier = permit_verifier

    def decide(
        self,
        mission_id: str,
        action_id: str,
        capability: Capability | None,
        permit: str | None = None,
        consume_permit: bool = False,
    ) -> Decision:
        spec = ACTION_SPECS.get(action_id)
        reasons: list[str] = []
        if not mission_id.strip():
            reasons.append("MISSION_REQUIRED")
        if spec is None:
            reasons.append("ACTION_SCHEMA_UNKNOWN")
        if capability is None:
            reasons.append("CAPABILITY_UNKNOWN")
        elif spec is not None and capability.id != spec.capability:
            reasons.append("ACTION_CAPABILITY_MISMATCH")
        elif capability.state in {CapabilityState.BLOCKED_OR_UNVERIFIED, CapabilityState.ADAPTER_REQUIRED}:
            reasons.append("CAPABILITY_NOT_LIVE")

        risk = spec.risk if spec else ActionRisk.EFFECTFUL
        permit_consumed = False
        if risk is ActionRisk.EFFECTFUL and not reasons:
            if self.permit_verifier is None:
                reasons.append("FORMATION_AUTHORITY_UNBOUND")
            else:
                valid, reason, permit_consumed = self.permit_verifier.verify_and_optionally_consume(
                    permit, mission_id, action_id, capability.id if capability else "unknown", consume_permit
                )
                if not valid:
                    reasons.append(reason)

        return Decision(
            mission_id=mission_id,
            action_id=action_id,
            risk=risk.value,
            capability=capability.id if capability else "unknown",
            status="DENY" if reasons else ("AUTHORIZED_FOR_EXECUTION" if consume_permit else "ALLOW_DRY_RUN"),
            reasons=reasons,
            permit_required=risk is ActionRisk.EFFECTFUL,
            permit_consumed=permit_consumed,
        )


class LearningLedger:
    """Concurrency-safe hash-chain telemetry. Events cannot promote themselves."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        route: str,
        outcome: str,
        elapsed_ms: int,
        evidence_hash: str,
        semantic_fruit: bool = False,
    ) -> dict[str, Any]:
        if outcome not in {"SUCCESS", "FAILURE", "QUARANTINED"}:
            raise ValueError("OUTCOME_INVALID")
        self.path.touch(exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            fh.seek(0)
            lines = [line for line in fh.read().splitlines() if line]
            previous = json.loads(lines[-1])["hash"] if lines else "GENESIS"
            event = {
                "eventVersion": 2,
                "route": route,
                "outcome": outcome,
                "semanticFruit": bool(semantic_fruit),
                "elapsedMs": max(0, int(elapsed_ms)),
                "evidenceHash": evidence_hash,
                "improvementCandidate": "CAPTURED_NOT_PROMOTED",
                "previous": previous,
                "recordedAt": int(time.time()),
            }
            event["hash"] = hashlib.sha256(stable_json(event).encode()).hexdigest()
            fh.seek(0, os.SEEK_END)
            fh.write(stable_json(event) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        return event

    def verify(self) -> bool:
        previous = "GENESIS"
        if not self.path.exists():
            return True
        with self.path.open("r", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_SH)
            lines = list(fh)
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        for line in lines:
            try:
                event = json.loads(line)
                digest = event.get("hash")
                unhashed = {key: value for key, value in event.items() if key != "hash"}
                if unhashed.get("previous") != previous or hashlib.sha256(stable_json(unhashed).encode()).hexdigest() != digest:
                    return False
                previous = digest
            except (json.JSONDecodeError, TypeError, KeyError):
                return False
        return True


class CircuitBreaker:
    def __init__(self, threshold: int = 2) -> None:
        if threshold < 1:
            raise ValueError("THRESHOLD_INVALID")
        self.threshold = threshold
        self.failures: dict[str, int] = {}
        self.quarantined: set[str] = set()

    def allows(self, route: str) -> bool:
        return route not in self.quarantined

    def record(self, route: str, success: bool) -> None:
        if route in self.quarantined:
            return
        if success:
            self.failures[route] = 0
            return
        self.failures[route] = self.failures.get(route, 0) + 1
        if self.failures[route] >= self.threshold:
            self.quarantined.add(route)

    def restore_after_independent_proof(self, route: str, proof_count: int) -> bool:
        if proof_count < 2:
            return False
        self.failures[route] = 0
        self.quarantined.discard(route)
        return True
