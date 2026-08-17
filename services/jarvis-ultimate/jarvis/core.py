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


class ArgumentKind(str, Enum):
    STRING = "STRING"
    BOOLEAN = "BOOLEAN"
    INTEGER = "INTEGER"
    OBJECT = "OBJECT"
    ARRAY = "ARRAY"


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
class ArgumentField:
    name: str
    kind: ArgumentKind
    required: bool = False


@dataclass(frozen=True)
class ActionSpec:
    id: str
    capability: str
    risk: ActionRisk
    resource_required: bool
    arguments: tuple[ArgumentField, ...] = ()

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "capability": self.capability,
            "risk": self.risk.value,
            "resourceRequired": self.resource_required,
            "arguments": [
                {"name": item.name, "kind": item.kind.value, "required": item.required}
                for item in self.arguments
            ],
        }


@dataclass
class Decision:
    mission_id: str
    mission_version: int
    action_id: str
    risk: str
    capability: str
    subject_id: str | None
    resource: str | None
    arguments_hash: str
    status: str
    reasons: list[str] = field(default_factory=list)
    permit_required: bool = False
    permit_consumed: bool = False


S = ArgumentKind.STRING
B = ArgumentKind.BOOLEAN
I = ArgumentKind.INTEGER
O = ArgumentKind.OBJECT
A = ArgumentKind.ARRAY


def arg(name: str, kind: ArgumentKind = S, required: bool = False) -> ArgumentField:
    return ArgumentField(name, kind, required)


def effectful(*fields: ArgumentField) -> tuple[ArgumentField, ...]:
    return (arg("idempotency_key", S, True), *fields)


ACTION_SPECS = {
    row.id: row
    for row in (
        ActionSpec("formation.audit", "formation", ActionRisk.READ_ONLY, False, (arg("event_hash"),)),
        ActionSpec("science.calculate", "science", ActionRisk.READ_ONLY, False, (arg("expression", S, True),)),
        ActionSpec("science.explain", "science", ActionRisk.READ_ONLY, False, (arg("principle_id", S, True),)),
        ActionSpec("gemini.reason", "gemini", ActionRisk.READ_ONLY, True, (arg("prompt_hash", S, True),)),
        ActionSpec("drive.search", "drive", ActionRisk.READ_ONLY, True, (arg("query", S, True), arg("page_size", I))),
        ActionSpec("drive.read", "drive", ActionRisk.READ_ONLY, True),
        ActionSpec("drive.write", "drive", ActionRisk.EFFECTFUL, True, effectful(arg("name", S, True), arg("content_hash", S, True), arg("mime_type"))),
        ActionSpec("drive.share", "drive", ActionRisk.EFFECTFUL, True, effectful(arg("recipient_hash", S, True), arg("role", S, True))),
        ActionSpec("drive.move", "drive", ActionRisk.EFFECTFUL, True, effectful(arg("destination_id", S, True))),
        ActionSpec("gmail.search", "gmail", ActionRisk.READ_ONLY, True, (arg("query", S, True), arg("page_size", I))),
        ActionSpec("gmail.read", "gmail", ActionRisk.READ_ONLY, True),
        ActionSpec("gmail.draft", "gmail", ActionRisk.EFFECTFUL, True, effectful(arg("to_hash", S, True), arg("body_hash", S, True))),
        ActionSpec("gmail.send", "gmail", ActionRisk.EFFECTFUL, True, effectful(arg("to_hash", S, True), arg("body_hash", S, True))),
        ActionSpec("gmail.forward", "gmail", ActionRisk.EFFECTFUL, True, effectful(arg("to_hash", S, True), arg("body_hash", S, True))),
        ActionSpec("gmail.archive", "gmail", ActionRisk.EFFECTFUL, True, effectful()),
        ActionSpec("sheets.read", "sheets", ActionRisk.READ_ONLY, True, (arg("range", S, True),)),
        ActionSpec("sheets.write", "sheets", ActionRisk.EFFECTFUL, True, effectful(arg("range", S, True), arg("values_hash", S, True))),
        ActionSpec("calendar.read", "calendar", ActionRisk.READ_ONLY, True, (arg("time_min"), arg("time_max"))),
        ActionSpec("calendar.schedule", "calendar", ActionRisk.EFFECTFUL, True, effectful(arg("event_hash", S, True))),
        ActionSpec("calendar.update", "calendar", ActionRisk.EFFECTFUL, True, effectful(arg("event_hash", S, True))),
        ActionSpec("github.source", "github", ActionRisk.READ_ONLY, True, (arg("ref"),)),
        ActionSpec("github.release", "github", ActionRisk.EFFECTFUL, True, effectful(arg("branch", S, True), arg("commit_sha", S, True))),
        ActionSpec("cloud.describe", "google_cloud", ActionRisk.READ_ONLY, True, (arg("region", S, True),)),
        ActionSpec("cloud.deploy_candidate", "google_cloud", ActionRisk.EFFECTFUL, True, effectful(arg("region", S, True), arg("service", S, True), arg("image_digest", S, True))),
        ActionSpec("cloud.promote_candidate", "google_cloud", ActionRisk.EFFECTFUL, True, effectful(arg("region", S, True), arg("service", S, True), arg("revision", S, True))),
        ActionSpec("federation.discover", "federation_mcp", ActionRisk.READ_ONLY, True, (arg("server", S, True),)),
        ActionSpec("federation.invoke", "federation_mcp", ActionRisk.EFFECTFUL, True, effectful(arg("tool", S, True), arg("arguments_hash", S, True))),
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
        return [asdict(value) for value in self._items.values()]

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


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def validate_arguments(spec: ActionSpec, arguments: dict[str, Any] | None) -> list[str]:
    values = arguments if isinstance(arguments, dict) else {}
    reasons: list[str] = []
    fields = {field.name: field for field in spec.arguments}
    unknown = sorted(set(values) - set(fields))
    if unknown:
        reasons.append("ACTION_ARGUMENT_UNKNOWN:" + ",".join(unknown))
    expected_types = {
        ArgumentKind.STRING: str,
        ArgumentKind.BOOLEAN: bool,
        ArgumentKind.INTEGER: int,
        ArgumentKind.OBJECT: dict,
        ArgumentKind.ARRAY: list,
    }
    for field in spec.arguments:
        if field.required and field.name not in values:
            reasons.append("ACTION_ARGUMENT_REQUIRED:" + field.name)
            continue
        if field.name not in values:
            continue
        value = values[field.name]
        expected = expected_types[field.kind]
        if not isinstance(value, expected) or (field.kind is ArgumentKind.INTEGER and isinstance(value, bool)):
            reasons.append("ACTION_ARGUMENT_TYPE_INVALID:" + field.name)
        elif field.kind is ArgumentKind.STRING and (not value.strip() or len(value) > 4096):
            reasons.append("ACTION_ARGUMENT_VALUE_INVALID:" + field.name)
    return reasons


class PermitVerifier:
    """Verifies externally minted v2 HMAC permits; no issuance method exists in this runtime."""

    AUDIENCE = "jarvis-ultimate"
    MINIMUM_KEY_BYTES = 32

    def __init__(self, secret: str | bytes | None, nonce_path: str | Path, clock: Callable[[], float] = time.time) -> None:
        key = secret.encode() if isinstance(secret, str) else secret
        self.secret = key if key and len(key) >= self.MINIMUM_KEY_BYTES else None
        self.key_too_weak = bool(key) and self.secret is None
        self.nonce_path = Path(nonce_path)
        self.nonce_path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock

    def verify_and_optionally_consume(
        self,
        token: str | None,
        *,
        mission_id: str,
        mission_version: int,
        action_id: str,
        capability: str,
        subject_id: str,
        resource: str,
        arguments_hash: str,
        idempotency_key: str,
        consume: bool,
    ) -> tuple[bool, str, bool]:
        if self.key_too_weak:
            return False, "FORMATION_KEY_TOO_WEAK", False
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

        required = {
            "version", "audience", "missionId", "missionVersion", "actionId", "capability",
            "subjectId", "resource", "argumentsHash", "idempotencyKey", "nonce", "issuedAt", "expiresAt",
        }
        if set(payload) != required:
            return False, "PERMIT_SCHEMA_INVALID", False
        if payload["version"] != 2 or payload["audience"] != self.AUDIENCE:
            return False, "PERMIT_AUDIENCE_INVALID", False
        expected_binding = (
            mission_id, mission_version, action_id, capability, subject_id, resource, arguments_hash, idempotency_key
        )
        actual_binding = (
            payload["missionId"], payload["missionVersion"], payload["actionId"], payload["capability"],
            payload["subjectId"], payload["resource"], payload["argumentsHash"], payload["idempotencyKey"],
        )
        if actual_binding != expected_binding:
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
        with self.nonce_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0)
            consumed = {line.strip() for line in handle if line.strip()}
            if nonce_hash in consumed:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                return False, "PERMIT_REPLAYED", False
            if consume:
                handle.seek(0, os.SEEK_END)
                handle.write(nonce_hash + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return True, "PERMIT_VALID", consume


class FormationKernel:
    """Exact typed request gate; capability is never treated as authority."""

    LOCAL_CAPABILITIES = {"formation", "science"}

    def __init__(self, permit_verifier: PermitVerifier | None = None) -> None:
        self.permit_verifier = permit_verifier

    def decide(
        self,
        mission_id: str,
        mission_version: int,
        action_id: str,
        capability: Capability | None,
        *,
        resource: str | None = None,
        arguments: dict[str, Any] | None = None,
        authority_envelope: Any | None = None,
        permit: str | None = None,
        consume_permit: bool = False,
    ) -> Decision:
        spec = ACTION_SPECS.get(action_id)
        values = arguments if isinstance(arguments, dict) else {}
        arguments_hash = semantic_fingerprint(values)
        reasons: list[str] = []
        if not mission_id.strip():
            reasons.append("MISSION_REQUIRED")
        if not isinstance(mission_version, int) or mission_version < 1:
            reasons.append("MISSION_VERSION_INVALID")
        if spec is None:
            reasons.append("ACTION_SCHEMA_UNKNOWN")
        if capability is None:
            reasons.append("CAPABILITY_UNKNOWN")
        elif spec is not None and capability.id != spec.capability:
            reasons.append("ACTION_CAPABILITY_MISMATCH")
        elif capability.state in {CapabilityState.BLOCKED_OR_UNVERIFIED, CapabilityState.ADAPTER_REQUIRED}:
            reasons.append("CAPABILITY_NOT_LIVE")
        if spec is not None:
            if spec.resource_required and (not isinstance(resource, str) or not resource.strip() or resource == "*"):
                reasons.append("ACTION_RESOURCE_EXACT_REQUIRED")
            reasons.extend(validate_arguments(spec, arguments))

        risk = spec.risk if spec else ActionRisk.EFFECTFUL
        subject_id = getattr(authority_envelope, "subject_id", None)
        permit_valid = risk is ActionRisk.READ_ONLY
        idempotency_key = str(values.get("idempotency_key", ""))
        permit_consumed = False
        if risk is ActionRisk.EFFECTFUL and not reasons:
            if self.permit_verifier is None:
                reasons.append("FORMATION_AUTHORITY_UNBOUND")
            elif not subject_id:
                reasons.append("AUTHORITY_SUBJECT_REQUIRED")
            else:
                permit_valid, permit_reason, _ = self.permit_verifier.verify_and_optionally_consume(
                    permit,
                    mission_id=mission_id,
                    mission_version=mission_version,
                    action_id=action_id,
                    capability=capability.id if capability else "unknown",
                    subject_id=subject_id,
                    resource=resource or "",
                    arguments_hash=arguments_hash,
                    idempotency_key=idempotency_key,
                    consume=False,
                )
                if not permit_valid:
                    reasons.append(permit_reason)

        if spec is not None and capability is not None and capability.id not in self.LOCAL_CAPABILITIES:
            if authority_envelope is None:
                reasons.append("EFFECTIVE_AUTHORITY_REQUIRED")
            else:
                allowed, authority_reasons = authority_envelope.evaluate(
                    action_id=action_id,
                    resource=resource or "",
                    mission_permit=permit_valid,
                )
                if not allowed:
                    reasons.extend(authority_reasons)

        if risk is ActionRisk.EFFECTFUL and consume_permit and not reasons:
            valid, permit_reason, permit_consumed = self.permit_verifier.verify_and_optionally_consume(
                permit,
                mission_id=mission_id,
                mission_version=mission_version,
                action_id=action_id,
                capability=capability.id if capability else "unknown",
                subject_id=subject_id or "",
                resource=resource or "",
                arguments_hash=arguments_hash,
                idempotency_key=idempotency_key,
                consume=True,
            )
            if not valid:
                reasons.append(permit_reason)

        return Decision(
            mission_id=mission_id,
            mission_version=mission_version,
            action_id=action_id,
            risk=risk.value,
            capability=capability.id if capability else "unknown",
            subject_id=subject_id,
            resource=resource,
            arguments_hash=arguments_hash,
            status="DENY" if reasons else ("AUTHORIZED_FOR_EXECUTION" if consume_permit else "ALLOW_DRY_RUN"),
            reasons=sorted(set(reasons)),
            permit_required=risk is ActionRisk.EFFECTFUL,
            permit_consumed=permit_consumed,
        )


class LedgerIntegrityError(RuntimeError):
    pass


class LearningLedger:
    """Locked hash chain with optional authenticated checkpoint; corrupt chains reject writes."""

    def __init__(self, path: str | Path, checkpoint_secret: str | bytes | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        key = checkpoint_secret.encode() if isinstance(checkpoint_secret, str) else checkpoint_secret
        self.checkpoint_secret = key if key and len(key) >= 32 else None
        self.checkpoint_path = self.path.with_suffix(self.path.suffix + ".checkpoint")

    @staticmethod
    def _validate_lines(lines: list[str]) -> tuple[bool, str, int]:
        previous = "GENESIS"
        count = 0
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                digest = event.get("hash")
                unhashed = {key: value for key, value in event.items() if key != "hash"}
                if unhashed.get("previous") != previous or hashlib.sha256(stable_json(unhashed).encode()).hexdigest() != digest:
                    return False, previous, count
                previous = digest
                count += 1
            except (json.JSONDecodeError, TypeError, KeyError):
                return False, previous, count
        return True, previous, count

    def _write_checkpoint(self, head: str, count: int) -> None:
        if not self.checkpoint_secret:
            return
        body = {"version": 1, "head": head, "count": count}
        body["signature"] = hmac.new(self.checkpoint_secret, stable_json(body).encode(), hashlib.sha256).hexdigest()
        temporary = self.checkpoint_path.with_name(f"{self.checkpoint_path.name}.tmp.{os.getpid()}")
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(stable_json(body))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.checkpoint_path)

    def append(self, route: str, outcome: str, elapsed_ms: int, evidence_hash: str, semantic_fruit: bool = False) -> dict[str, Any]:
        if outcome not in {"SUCCESS", "FAILURE", "QUARANTINED", "INPUT_REJECTED"}:
            raise ValueError("OUTCOME_INVALID")
        self.path.touch(exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0)
            lines = handle.read().splitlines()
            valid, previous, count = self._validate_lines(lines)
            if not valid:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                raise LedgerIntegrityError("LEDGER_INTEGRITY_FAILED_WRITE_BLOCKED")
            event = {
                "eventVersion": 3,
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
            handle.seek(0, os.SEEK_END)
            handle.write(stable_json(event) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            self._write_checkpoint(event["hash"], count + 1)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return event

    def verify(self) -> bool:
        if not self.path.exists():
            return True
        with self.path.open("r", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            lines = handle.read().splitlines()
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        valid, head, count = self._validate_lines(lines)
        if not valid:
            return False
        if not self.checkpoint_secret:
            return True
        if count == 0:
            return not self.checkpoint_path.exists()
        try:
            checkpoint = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
            signature = checkpoint.pop("signature")
            expected = hmac.new(self.checkpoint_secret, stable_json(checkpoint).encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(signature, expected) and checkpoint == {"version": 1, "head": head, "count": count}
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            return False

    @property
    def authenticated_checkpoint_enabled(self) -> bool:
        return self.checkpoint_secret is not None


@dataclass(frozen=True)
class RecoveryProof:
    route: str
    proof_id: str
    verifier_id: str
    evidence_hash: str
    passed: bool
    checked_at: int


class CircuitBreaker:
    def __init__(self, threshold: int = 2, clock: Callable[[], float] = time.time) -> None:
        if threshold < 1:
            raise ValueError("THRESHOLD_INVALID")
        self.threshold = threshold
        self.clock = clock
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

    def restore_after_independent_proof(self, route: str, proofs: tuple[RecoveryProof, ...]) -> bool:
        now = int(self.clock())
        valid = [
            proof for proof in proofs
            if proof.route == route and proof.passed and 0 <= now - proof.checked_at <= 900
            and len(proof.proof_id) >= 8 and len(proof.verifier_id) >= 8 and len(proof.evidence_hash) == 64
        ]
        if len(valid) < 2:
            return False
        if len({proof.proof_id for proof in valid}) < 2 or len({proof.verifier_id for proof in valid}) < 2 or len({proof.evidence_hash for proof in valid}) < 2:
            return False
        self.failures[route] = 0
        self.quarantined.discard(route)
        return True
