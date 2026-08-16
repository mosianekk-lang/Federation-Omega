from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import hmac
import json
import re
import secrets
import time
from pathlib import Path
from typing import Any, Mapping


FIREWALL_SCHEMA = "LEX-EXTERNAL-ACTION-FIREWALL-V1"
LEASE_SCHEMA = "LEX-MUTATION-LEASE-V1"
LEASE_PROOF = "user_execution_lease_verified"

READ_ONLY_MARKERS = (
    r"\bupdate\s+(?:all\s+)?status\b",
    r"\breadiness\s+check\b",
    r"\baudit\b",
    r"\breconcile\b",
    r"\bverify\b",
    r"\binspect\b",
    r"\breview\b",
    r"\bcheck\s+(?:the\s+)?(?:status|correspondence|mail|email|drive)\b",
    r"\bstatus\s+check\b",
)

ACTION_VERBS = {
    "send": ("send", "resend", "transmit"),
    "send_email": ("send", "resend", "email"),
    "send_draft": ("send", "resend", "draft"),
    "file": ("file", "lodge"),
    "submit": ("submit", "lodge"),
    "delete": ("delete", "remove"),
    "update": ("update", "change", "edit"),
    "create": ("create", "make"),
    "create_draft": ("create", "draft"),
    "share": ("share",),
    "move": ("move",),
    "merge": ("merge",),
    "label": ("label",),
    "archive": ("archive",),
}

MUTATING_ACTION_TOKENS = (
    "send",
    "file",
    "submit",
    "create",
    "update",
    "delete",
    "remove",
    "modify",
    "move",
    "share",
    "merge",
    "label",
    "archive",
    "trash",
    "reply",
    "forward",
    "batch_modify",
    "apply_",
)


class FirewallDecision(str, Enum):
    READ_ONLY = "READ_ONLY"
    PREPARED = "PREPARED"
    ALLOW_ONCE = "ALLOW_ONCE"
    DENY = "DENY"


@dataclass(frozen=True)
class DecisionReceipt:
    schema: str
    decision: str
    reason: str
    action: str
    target_digest: str
    lease_token: str | None = None
    expires_at: int | None = None
    receipt_sha256: str | None = None

    def sealed(self) -> "DecisionReceipt":
        payload = asdict(self)
        payload["receipt_sha256"] = None
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return DecisionReceipt(**{**payload, "receipt_sha256": digest})


class FileLeaseStore:
    """Small fail-closed durable store. Losing state blocks execution rather than permitting it."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Lease store root must be an object")
        return {str(k): dict(v) for k, v in data.items() if isinstance(v, Mapping)}

    def _write(self, data: Mapping[str, Mapping[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        temp.replace(self.path)

    def put(self, token: str, record: Mapping[str, Any]) -> None:
        data = self._read()
        data[token] = dict(record)
        self._write(data)

    def get(self, token: str) -> dict[str, Any] | None:
        return self._read().get(token)

    def consume(self, token: str) -> dict[str, Any] | None:
        data = self._read()
        record = data.get(token)
        if not record or record.get("consumed"):
            return None
        record = dict(record)
        record["consumed"] = True
        record["consumed_at"] = int(time.time())
        data[token] = record
        self._write(data)
        return record


class ExternalActionFirewall:
    """Two-phase, one-use capability firewall for external mutations.

    A read-only/status/audit turn can never prepare or execute a mutation.
    A mutation requires:
      1) an explicit user instruction naming the action,
      2) an exact target bound into a signed lease,
      3) a separate user turn containing only EXECUTE <lease-token>,
      4) one-time atomic consumption before the provider call,
      5) provider readback handled by the caller after execution.
    """

    def __init__(
        self,
        *,
        secret: bytes,
        store: FileLeaseStore,
        ttl_seconds: int = 600,
        clock=time.time,
    ) -> None:
        if not secret:
            raise ValueError("secret is required")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._secret = secret
        self._store = store
        self._ttl = ttl_seconds
        self._clock = clock

    @staticmethod
    def is_read_only_turn(user_text: str) -> bool:
        text = user_text.lower()
        return any(re.search(pattern, text) for pattern in READ_ONLY_MARKERS)

    @staticmethod
    def is_mutating_action(action: str) -> bool:
        name = action.strip().lower()
        return any(token in name for token in MUTATING_ACTION_TOKENS)

    @staticmethod
    def _canonical_target(target: Mapping[str, Any]) -> str:
        if not isinstance(target, Mapping) or not target:
            raise ValueError("exact non-empty target mapping is required")
        return json.dumps(dict(target), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def target_digest(cls, target: Mapping[str, Any]) -> str:
        return hashlib.sha256(cls._canonical_target(target).encode("utf-8")).hexdigest()

    @staticmethod
    def _explicit_action_requested(user_text: str, action: str) -> bool:
        text = user_text.lower()
        normalized = action.strip().lower()
        verbs: tuple[str, ...] = ()
        for key, candidates in ACTION_VERBS.items():
            if key in normalized:
                verbs = candidates
                break
        if not verbs:
            verbs = tuple(token for token in MUTATING_ACTION_TOKENS if token.isalpha())
        return any(re.search(rf"\b{re.escape(verb)}\b", text) for verb in verbs)

    def _sign(self, payload: Mapping[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hmac.new(self._secret, body, hashlib.sha256).hexdigest()

    def _token(self, lease_id: str, signature: str) -> str:
        return f"{lease_id}.{signature[:24]}"

    def prepare(
        self,
        *,
        user_turn_id: str,
        user_text: str,
        action: str,
        target: Mapping[str, Any],
        provider_state: Mapping[str, Any] | None = None,
    ) -> DecisionReceipt:
        digest = self.target_digest(target)

        if not self.is_mutating_action(action):
            return DecisionReceipt(
                FIREWALL_SCHEMA, FirewallDecision.READ_ONLY.value,
                "Action is non-mutating; no execution lease is required.", action, digest
            ).sealed()

        if self.is_read_only_turn(user_text):
            return DecisionReceipt(
                FIREWALL_SCHEMA, FirewallDecision.DENY.value,
                "Read-only/status/audit intent hard-locks all external mutations for this turn.",
                action, digest,
            ).sealed()

        if not self._explicit_action_requested(user_text, action):
            return DecisionReceipt(
                FIREWALL_SCHEMA, FirewallDecision.DENY.value,
                "No explicit current-turn user mutation instruction matches the requested action.",
                action, digest,
            ).sealed()

        state = dict(provider_state or {})
        already_sent = bool(state.get("sent_counterpart_exists"))
        resend_authorized = bool(re.search(r"\bresend\b", user_text.lower()))
        if "send" in action.lower() and already_sent and not resend_authorized:
            return DecisionReceipt(
                FIREWALL_SCHEMA, FirewallDecision.DENY.value,
                "A SENT counterpart already exists; duplicate transmission is blocked unless the user explicitly says RESEND.",
                action, digest,
            ).sealed()

        now = int(self._clock())
        lease_id = secrets.token_urlsafe(16)
        payload = {
            "schema": LEASE_SCHEMA,
            "lease_id": lease_id,
            "prepared_turn_id": user_turn_id,
            "action": action,
            "target_digest": digest,
            "created_at": now,
            "expires_at": now + self._ttl,
            "resend_authorized": resend_authorized,
        }
        signature = self._sign(payload)
        token = self._token(lease_id, signature)
        self._store.put(token, {**payload, "signature": signature, "consumed": False})

        return DecisionReceipt(
            FIREWALL_SCHEMA,
            FirewallDecision.PREPARED.value,
            "Mutation capability prepared but not executable. A separate user turn must contain exactly EXECUTE <lease-token>.",
            action,
            digest,
            lease_token=token,
            expires_at=payload["expires_at"],
        ).sealed()

    def commit(
        self,
        *,
        user_turn_id: str,
        user_text: str,
        lease_token: str,
        action: str,
        target: Mapping[str, Any],
        provider_state: Mapping[str, Any] | None = None,
    ) -> DecisionReceipt:
        digest = self.target_digest(target)

        if self.is_read_only_turn(user_text):
            return DecisionReceipt(
                FIREWALL_SCHEMA, FirewallDecision.DENY.value,
                "Read-only/status/audit intent cannot consume a mutation lease.", action, digest
            ).sealed()

        if user_text.strip() != f"EXECUTE {lease_token}":
            return DecisionReceipt(
                FIREWALL_SCHEMA, FirewallDecision.DENY.value,
                "Execution confirmation must be the exact standalone phrase EXECUTE <lease-token>.",
                action, digest,
            ).sealed()

        record = self._store.get(lease_token)
        if not record:
            return DecisionReceipt(
                FIREWALL_SCHEMA, FirewallDecision.DENY.value,
                "Lease is unknown, lost, or already unavailable; fail closed.", action, digest
            ).sealed()

        if record.get("consumed"):
            return DecisionReceipt(
                FIREWALL_SCHEMA, FirewallDecision.DENY.value,
                "Lease has already been consumed; replay blocked.", action, digest
            ).sealed()

        if user_turn_id == record.get("prepared_turn_id"):
            return DecisionReceipt(
                FIREWALL_SCHEMA, FirewallDecision.DENY.value,
                "Same-turn execution is prohibited; two distinct user turns are required.",
                action, digest,
            ).sealed()

        if int(self._clock()) > int(record.get("expires_at", 0)):
            return DecisionReceipt(
                FIREWALL_SCHEMA, FirewallDecision.DENY.value,
                "Lease expired before execution.", action, digest
            ).sealed()

        expected_payload = {
            key: record[key]
            for key in (
                "schema", "lease_id", "prepared_turn_id", "action",
                "target_digest", "created_at", "expires_at", "resend_authorized"
            )
        }
        if not hmac.compare_digest(str(record.get("signature", "")), self._sign(expected_payload)):
            return DecisionReceipt(
                FIREWALL_SCHEMA, FirewallDecision.DENY.value,
                "Lease signature mismatch.", action, digest
            ).sealed()

        if action != record.get("action") or digest != record.get("target_digest"):
            return DecisionReceipt(
                FIREWALL_SCHEMA, FirewallDecision.DENY.value,
                "Requested action or target differs from the prepared lease.", action, digest
            ).sealed()

        state = dict(provider_state or {})
        if (
            "send" in action.lower()
            and state.get("sent_counterpart_exists")
            and not record.get("resend_authorized")
        ):
            return DecisionReceipt(
                FIREWALL_SCHEMA, FirewallDecision.DENY.value,
                "Provider state now shows a SENT counterpart and the lease did not authorize RESEND.",
                action, digest
            ).sealed()

        consumed = self._store.consume(lease_token)
        if not consumed:
            return DecisionReceipt(
                FIREWALL_SCHEMA, FirewallDecision.DENY.value,
                "Lease could not be atomically consumed; fail closed.", action, digest
            ).sealed()

        return DecisionReceipt(
            FIREWALL_SCHEMA,
            FirewallDecision.ALLOW_ONCE.value,
            "One external mutation is authorized for the exact action and target. Lease is already consumed; retries require a new lease.",
            action,
            digest,
        ).sealed()


def requires_execution_lease(effect: str) -> bool:
    return effect != "READ"
