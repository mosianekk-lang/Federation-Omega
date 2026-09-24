from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from sol_61_runtime.sol_62_frontier_primitives import ConstraintError, digest
from sol_61_runtime.sol_62_complete_client_runtime import Sol62CompleteClientRuntime

SCHEMA = "SOL62_BROWSER_CONTROL_PLANE_V1"
COMMAND_SCHEMA = "SOL62_BROWSER_COMMAND_V1"
ACK_SCHEMA = "SOL62_BROWSER_COMMAND_ACK_V1"


class BrowserEffectClass(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOCAL_BROWSER_STATE = "LOCAL_BROWSER_STATE"
    WEBSITE_STATE = "WEBSITE_STATE"


class BrowserCommandState(str, Enum):
    QUEUED = "QUEUED"
    LEASED = "LEASED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    HELD = "HELD"


READ_ONLY_OPERATIONS = frozenset({
    "LIST_TABS",
    "SEMANTIC_SNAPSHOT",
    "READ_ACTIVE_TAB",
})

LOCAL_BROWSER_OPERATIONS = frozenset({
    "CREATE_TAB",
    "ACTIVATE_TAB",
    "CLOSE_TAB",
    "RELOAD_TAB",
    "GO_BACK",
    "GO_FORWARD",
    "NAVIGATE_CHATGPT",
    "OPEN_NEW_CHAT",
    "FOCUS_ELEMENT",
    "SCROLL_ELEMENT",
})

WEBSITE_STATE_OPERATIONS = frozenset({
    "CLICK_ELEMENT",
    "FILL_ELEMENT",
})

ALL_OPERATIONS = READ_ONLY_OPERATIONS | LOCAL_BROWSER_OPERATIONS | WEBSITE_STATE_OPERATIONS

REQUIRED_CAPABILITY: Mapping[str, str] = {
    "LIST_TABS": "TAB_QUERY",
    "READ_ACTIVE_TAB": "TAB_QUERY",
    "CREATE_TAB": "TAB_CREATE",
    "OPEN_NEW_CHAT": "TAB_CREATE",
    "ACTIVATE_TAB": "TAB_ACTIVATE",
    "CLOSE_TAB": "TAB_CLOSE",
    "RELOAD_TAB": "TAB_RELOAD",
    "GO_BACK": "HISTORY_BACK_FORWARD",
    "GO_FORWARD": "HISTORY_BACK_FORWARD",
    "NAVIGATE_CHATGPT": "SAFE_CHATGPT_NAVIGATION",
    "SEMANTIC_SNAPSHOT": "SEMANTIC_DOM_SNAPSHOT",
    "FOCUS_ELEMENT": "SEMANTIC_FOCUS_SCROLL",
    "SCROLL_ELEMENT": "SEMANTIC_FOCUS_SCROLL",
    "CLICK_ELEMENT": "SEMANTIC_CLICK_GATED",
    "FILL_ELEMENT": "SEMANTIC_FILL_GATED",
}


@dataclass(frozen=True, slots=True)
class BrowserControlIntent:
    operation: str
    args: Mapping[str, Any] = field(default_factory=dict)
    effect_class: BrowserEffectClass = BrowserEffectClass.READ_ONLY
    expected_readback: Mapping[str, Any] = field(default_factory=dict)
    authority_ref: str = ""
    command_id: str = ""

    def __post_init__(self) -> None:
        op = self.operation.strip().upper()
        if op not in ALL_OPERATIONS:
            raise ValueError(f"unsupported browser operation: {op}")
        object.__setattr__(self, "operation", op)
        if op in WEBSITE_STATE_OPERATIONS and self.effect_class != BrowserEffectClass.WEBSITE_STATE:
            raise ValueError("website-state browser operation requires WEBSITE_STATE effect class")
        if op in LOCAL_BROWSER_OPERATIONS and self.effect_class == BrowserEffectClass.READ_ONLY:
            raise ValueError("browser-state mutation cannot be declared READ_ONLY")


@dataclass(frozen=True, slots=True)
class BrowserTarget:
    stable_id: str = ""
    role: str = ""
    name: str = ""
    text: str = ""
    href: str = ""


@dataclass(frozen=True, slots=True)
class BrowserCarrierScore:
    carrier_id: str
    score: float
    capability_fit: float
    currentness: float
    semantic_control: float
    recoverability: float
    privacy_fit: float
    failure_domain_diversity: float
    latency_penalty: float


def safe_chatgpt_url(candidate: str) -> str:
    value = (candidate or "https://chatgpt.com/").strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != "chatgpt.com":
        raise ConstraintError("CHATGPT_ORIGIN_REQUIRED")
    if parsed.username or parsed.password:
        raise ConstraintError("URL_CREDENTIALS_FORBIDDEN")
    return value


def expected_effect_class(operation: str) -> BrowserEffectClass:
    op = operation.strip().upper()
    if op in READ_ONLY_OPERATIONS:
        return BrowserEffectClass.READ_ONLY
    if op in LOCAL_BROWSER_OPERATIONS:
        return BrowserEffectClass.LOCAL_BROWSER_STATE
    if op in WEBSITE_STATE_OPERATIONS:
        return BrowserEffectClass.WEBSITE_STATE
    raise ValueError(f"unsupported browser operation: {op}")


def semantic_control_score(
    candidate: Mapping[str, Any],
    target: BrowserTarget,
) -> float:
    score = 0.0
    if target.stable_id and candidate.get("stable_id") == target.stable_id:
        score += 0.72
    if target.role and str(candidate.get("role", "")).lower() == target.role.lower():
        score += 0.12
    if target.name and str(candidate.get("name", "")).strip().lower() == target.name.strip().lower():
        score += 0.10
    if target.text and str(candidate.get("text", "")).strip().lower() == target.text.strip().lower():
        score += 0.06
    if target.href and candidate.get("href") == target.href:
        score += 0.12
    return min(1.0, round(score, 8))


class BrowserControlPlane:
    """Typed browser-command plane over detachable SOL browser carriers.

    Browser control is not mission authority. The plane queues bounded commands,
    requires carrier capability/currentness, gates website mutations on a
    separate authority reference, and stores post-action readback before a
    command is considered verified.
    """

    def __init__(
        self,
        client: Sol62CompleteClientRuntime,
        *,
        lease_seconds: int = 30,
        command_ttl_seconds: int = 300,
    ) -> None:
        if lease_seconds < 5:
            raise ValueError("LEASE_SECONDS_TOO_LOW")
        if command_ttl_seconds < lease_seconds:
            raise ValueError("COMMAND_TTL_BELOW_LEASE")
        self.client = client
        self.lease_seconds = int(lease_seconds)
        self.command_ttl_seconds = int(command_ttl_seconds)

    def _now(self, now_epoch: int | None) -> int:
        return int(time.time()) if now_epoch is None else int(now_epoch)

    def _carrier(self, carrier_id: str, owner_subject: str) -> Mapping[str, Any]:
        row = self.client._get("sol62.browser.carrier", carrier_id)
        if not row:
            raise KeyError(carrier_id)
        value = row["value"]
        if value.get("owner_subject") != owner_subject:
            raise ConstraintError("BROWSER_CARRIER_OWNER_MISMATCH")
        return value

    def capability_twin(
        self,
        carrier_id: str,
        *,
        owner_subject: str,
        now_epoch: int | None = None,
    ) -> dict[str, Any]:
        now = self._now(now_epoch)
        carrier = dict(self._carrier(carrier_id, owner_subject))
        capabilities = sorted(set(carrier.get("capabilities", ())))
        age = max(0, now - int(carrier.get("last_seen_epoch", 0)))
        state = str(carrier.get("state", "UNKNOWN"))
        return {
            "schema": "SOL62_BROWSER_CAPABILITY_TWIN_V1",
            "carrier_id": carrier_id,
            "owner_subject": owner_subject,
            "client_kind": carrier.get("client_kind", ""),
            "failure_domain": carrier.get("failure_domain", ""),
            "capabilities": capabilities,
            "current": bool(carrier.get("current", True)),
            "state": state,
            "age_seconds": age,
            "callable": bool(carrier.get("current", True))
            and state in {"HEALTHY", "DEGRADED"},
            "mission_authority": False,
            "provider_authority": False,
            "website_effect_authority": False,
        }

    def score_carriers(
        self,
        *,
        owner_subject: str,
        operation: str,
        preferred_failure_domain: str = "",
        now_epoch: int | None = None,
    ) -> tuple[BrowserCarrierScore, ...]:
        now = self._now(now_epoch)
        op = operation.strip().upper()
        required = REQUIRED_CAPABILITY[op]
        rows = self.client._rows("sol62.browser.carrier")
        scores: list[BrowserCarrierScore] = []
        for row in rows:
            value = row["value"]
            if value.get("owner_subject") != owner_subject:
                continue
            caps = set(value.get("capabilities", ()))
            if required not in caps:
                continue
            state = str(value.get("state", ""))
            if state not in {"HEALTHY", "DEGRADED"} or not bool(value.get("current", True)):
                continue
            age = max(0, now - int(value.get("last_seen_epoch", 0)))
            currentness = max(0.0, 1.0 - min(age, 120) / 120.0)
            semantic = 1.0 if "SEMANTIC_DOM_SNAPSHOT" in caps else 0.45
            recoverability = 1.0 if "DURABLE_LOCAL_OUTBOX" in caps else 0.55
            privacy = 1.0
            domain = str(value.get("failure_domain", ""))
            diversity = 1.0 if preferred_failure_domain and domain != preferred_failure_domain else 0.65
            latency_penalty = 0.05 if "FUSE_OWNED" in str(value.get("client_kind", "")) else 0.10
            fit = 1.0
            score = (
                0.30 * fit
                + 0.18 * currentness
                + 0.16 * semantic
                + 0.14 * recoverability
                + 0.10 * privacy
                + 0.12 * diversity
                - latency_penalty
            )
            scores.append(BrowserCarrierScore(
                carrier_id=str(value["carrier_id"]),
                score=round(score, 8),
                capability_fit=fit,
                currentness=round(currentness, 8),
                semantic_control=semantic,
                recoverability=recoverability,
                privacy_fit=privacy,
                failure_domain_diversity=diversity,
                latency_penalty=latency_penalty,
            ))
        return tuple(sorted(scores, key=lambda item: (-item.score, item.carrier_id)))

    def elect_carrier(
        self,
        *,
        owner_subject: str,
        operation: str,
        preferred_failure_domain: str = "",
        now_epoch: int | None = None,
    ) -> BrowserCarrierScore | None:
        ranked = self.score_carriers(
            owner_subject=owner_subject,
            operation=operation,
            preferred_failure_domain=preferred_failure_domain,
            now_epoch=now_epoch,
        )
        return ranked[0] if ranked else None

    def _normalize_args(self, operation: str, args: Mapping[str, Any]) -> dict[str, Any]:
        body = dict(args)
        if operation in {"CREATE_TAB", "NAVIGATE_CHATGPT", "OPEN_NEW_CHAT"}:
            body["url"] = safe_chatgpt_url(str(body.get("url") or "https://chatgpt.com/"))
        if operation in {"ACTIVATE_TAB", "CLOSE_TAB", "RELOAD_TAB", "GO_BACK", "GO_FORWARD"}:
            tab_id = body.get("tab_id")
            if not isinstance(tab_id, int) or tab_id < 0:
                raise ConstraintError("VALID_TAB_ID_REQUIRED")
        if operation in {"FOCUS_ELEMENT", "SCROLL_ELEMENT", "CLICK_ELEMENT", "FILL_ELEMENT"}:
            target = body.get("target")
            if not isinstance(target, Mapping):
                raise ConstraintError("SEMANTIC_TARGET_REQUIRED")
            if operation == "FILL_ELEMENT" and not isinstance(body.get("value"), str):
                raise ConstraintError("STRING_FILL_VALUE_REQUIRED")
        return body

    def enqueue(
        self,
        *,
        owner_subject: str,
        carrier_id: str,
        intent: BrowserControlIntent,
        now_epoch: int | None = None,
    ) -> dict[str, Any]:
        now = self._now(now_epoch)
        carrier = self._carrier(carrier_id, owner_subject)
        required = REQUIRED_CAPABILITY[intent.operation]
        capabilities = set(carrier.get("capabilities", ()))
        if required not in capabilities:
            raise ConstraintError("BROWSER_CARRIER_CAPABILITY_MISSING")
        if str(carrier.get("state", "")) not in {"HEALTHY", "DEGRADED"}:
            raise ConstraintError("BROWSER_CARRIER_NOT_HEALTHY")
        expected_class = expected_effect_class(intent.operation)
        if intent.effect_class != expected_class:
            raise ConstraintError("BROWSER_EFFECT_CLASS_MISMATCH")
        if expected_class == BrowserEffectClass.WEBSITE_STATE and not intent.authority_ref:
            raise ConstraintError("WEBSITE_STATE_AUTHORITY_REFERENCE_REQUIRED")

        args = self._normalize_args(intent.operation, intent.args)
        fingerprint = {
            "owner_subject": owner_subject,
            "carrier_id": carrier_id,
            "operation": intent.operation,
            "args": args,
            "effect_class": intent.effect_class.value,
            "expected_readback": dict(intent.expected_readback),
            "authority_ref": intent.authority_ref,
        }
        command_id = intent.command_id or ("browser-" + digest(fingerprint)[:24])
        existing = self.client._get("sol62.browser.command", command_id)
        if existing:
            if existing["value"].get("fingerprint_sha256") != digest(fingerprint):
                raise ConstraintError("BROWSER_COMMAND_IDEMPOTENCY_COLLISION")
            return existing

        body = {
            "schema": COMMAND_SCHEMA,
            "command_id": command_id,
            "owner_subject": owner_subject,
            "carrier_id": carrier_id,
            "operation": intent.operation,
            "args": args,
            "effect_class": intent.effect_class.value,
            "expected_readback": dict(intent.expected_readback),
            "authority_ref": intent.authority_ref,
            "authority_bound": bool(intent.authority_ref)
            if expected_class == BrowserEffectClass.WEBSITE_STATE
            else True,
            "state": BrowserCommandState.QUEUED.value,
            "created_epoch": now,
            "expires_epoch": now + self.command_ttl_seconds,
            "lease_until_epoch": 0,
            "attempt": 0,
            "fingerprint_sha256": digest(fingerprint),
            "browser_mission_authority": False,
            "provider_authority": False,
        }
        stored = self.client._put("sol62.browser.command", command_id, body)
        self.client.runtime.control.append_event(
            command_id,
            "SOL62_BROWSER_COMMAND_QUEUED",
            {
                "carrier_id": carrier_id,
                "operation": intent.operation,
                "effect_class": intent.effect_class.value,
                "authority_bound": body["authority_bound"],
            },
        )
        return stored

    def next_command(
        self,
        carrier_id: str,
        *,
        owner_subject: str,
        now_epoch: int | None = None,
    ) -> dict[str, Any] | None:
        now = self._now(now_epoch)
        self._carrier(carrier_id, owner_subject)
        rows = self.client._rows("sol62.browser.command")
        candidates = []
        for row in rows:
            value = row["value"]
            if value.get("owner_subject") != owner_subject or value.get("carrier_id") != carrier_id:
                continue
            if int(value.get("expires_epoch", 0)) <= now:
                if value.get("state") in {BrowserCommandState.QUEUED.value, BrowserCommandState.LEASED.value}:
                    expired = dict(value)
                    expired["state"] = BrowserCommandState.HELD.value
                    expired["hold_reason"] = "COMMAND_EXPIRED"
                    self.client._put("sol62.browser.command", str(value["command_id"]), expired)
                continue
            state = value.get("state")
            if state == BrowserCommandState.QUEUED.value:
                candidates.append(value)
            elif state == BrowserCommandState.LEASED.value and int(value.get("lease_until_epoch", 0)) <= now:
                candidates.append(value)
        if not candidates:
            return None
        candidates.sort(key=lambda value: (int(value.get("created_epoch", 0)), str(value["command_id"])))
        selected = dict(candidates[0])
        selected["state"] = BrowserCommandState.LEASED.value
        selected["lease_until_epoch"] = now + self.lease_seconds
        selected["attempt"] = int(selected.get("attempt", 0)) + 1
        stored = self.client._put("sol62.browser.command", str(selected["command_id"]), selected)
        self.client.runtime.control.append_event(
            str(selected["command_id"]),
            "SOL62_BROWSER_COMMAND_LEASED",
            {
                "carrier_id": carrier_id,
                "operation": selected["operation"],
                "attempt": selected["attempt"],
            },
        )
        return dict(stored["value"])

    def acknowledge(
        self,
        command_id: str,
        *,
        owner_subject: str,
        carrier_id: str,
        status: str,
        readback: Mapping[str, Any] | None = None,
        error_code: str = "",
        now_epoch: int | None = None,
    ) -> dict[str, Any]:
        now = self._now(now_epoch)
        row = self.client._get("sol62.browser.command", command_id)
        if not row:
            raise KeyError(command_id)
        body = dict(row["value"])
        if body.get("owner_subject") != owner_subject or body.get("carrier_id") != carrier_id:
            raise ConstraintError("BROWSER_COMMAND_OWNER_OR_CARRIER_MISMATCH")
        normalized_status = status.strip().upper()
        if normalized_status not in {"VERIFIED", "FAILED", "HELD"}:
            raise ConstraintError("BROWSER_COMMAND_ACK_STATUS_INVALID")
        actual = dict(readback or {})
        expected = dict(body.get("expected_readback", {}))
        readback_ok = all(actual.get(key) == value for key, value in expected.items())
        if normalized_status == "VERIFIED" and not readback_ok:
            normalized_status = "FAILED"
            error_code = error_code or "BROWSER_READBACK_MISMATCH"

        body["state"] = normalized_status
        body["ack_epoch"] = now
        body["readback"] = actual
        body["readback_sha256"] = digest(actual)
        body["readback_match"] = readback_ok
        body["error_code"] = error_code
        body["lease_until_epoch"] = 0
        stored = self.client._put("sol62.browser.command", command_id, body)
        self.client.runtime.control.append_event(
            command_id,
            "SOL62_BROWSER_COMMAND_ACK",
            {
                "carrier_id": carrier_id,
                "status": normalized_status,
                "readback_match": readback_ok,
                "error_code": error_code,
            },
        )
        return {
            "schema": ACK_SCHEMA,
            "command": dict(stored["value"]),
            "browser_action_verified": normalized_status == "VERIFIED" and readback_ok,
            "mission_authority_granted": False,
            "provider_authority_granted": False,
        }

    def status(
        self,
        *,
        owner_subject: str,
        carrier_id: str = "",
    ) -> dict[str, Any]:
        rows = self.client._rows("sol62.browser.command")
        selected = [
            row["value"]
            for row in rows
            if row["value"].get("owner_subject") == owner_subject
            and (not carrier_id or row["value"].get("carrier_id") == carrier_id)
        ]
        counts: dict[str, int] = {}
        for value in selected:
            state = str(value.get("state", "UNKNOWN"))
            counts[state] = counts.get(state, 0) + 1
        return {
            "schema": SCHEMA,
            "owner_subject": owner_subject,
            "carrier_id": carrier_id,
            "commands": len(selected),
            "states": dict(sorted(counts.items())),
            "website_state_requires_authority_ref": True,
            "unknown_effect_replay_allowed": False,
            "browser_is_mission_authority": False,
            "provider_authority": False,
        }
