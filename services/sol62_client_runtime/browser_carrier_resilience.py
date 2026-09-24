from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping

from sol_61_runtime.sol_62_frontier_primitives import ConstraintError, digest
from sol_61_runtime.sol_62_complete_client_runtime import Sol62CompleteClientRuntime


SCHEMA = "SOL62_BROWSER_CARRIER_RESILIENCE_V1"


class CarrierState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    CLOSED = "CLOSED"


class FailureDisposition(str, Enum):
    ROUTE_LOCAL = "ROUTE_LOCAL"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    HARD_BOUNDARY = "HARD_BOUNDARY"
    UNKNOWN = "UNKNOWN"


ROUTE_LOCAL_FAILURES = frozenset(
    {
        "CHATGPT_CONVERSATION_LOAD_FAILED",
        "CHATGPT_CHAT_LOAD_FAILED",
        "CHATGPT_TAB_CLOSED",
        "CHATGPT_UI_UNAVAILABLE",
        "BROWSER_TAB_CRASHED",
        "BROWSER_RENDER_FAILED",
        "NETWORK_TRANSIENT",
        "SERVICE_UNAVAILABLE",
        "PROVIDER_TIMEOUT",
        "CONVERSATION_TOO_LONG",
        "CONTEXT_LIMIT",
        "RATE_LIMIT",
        "QUOTA_EXHAUSTED",
        "MODEL_UNAVAILABLE",
        "TOOL_UNAVAILABLE",
    }
)

AUTH_FAILURES = frozenset(
    {
        "CHATGPT_AUTH_REQUIRED",
        "SESSION_EXPIRED",
        "AUTHENTICATION_REQUIRED",
        "OWNER_SESSION_REQUIRED",
    }
)

HARD_BOUNDARIES = frozenset(
    {
        "SAFETY_BOUNDARY",
        "PRIVACY_BOUNDARY",
        "LEGAL_BOUNDARY",
        "PERMISSION_DENIED",
        "OWNER_EFFECT_APPROVAL_REQUIRED",
    }
)


@dataclass(frozen=True, slots=True)
class CarrierFailure:
    code: str
    disposition: FailureDisposition
    mission_terminal: bool
    retry_same_carrier: bool
    goal_mutation_allowed: bool
    bypass_allowed: bool


@dataclass(frozen=True, slots=True)
class CarrierRegistration:
    carrier_id: str
    owner_subject: str
    session_id: str
    client_kind: str
    route_id: str = "CHATGPT_BROWSER"
    priority: int = 50
    conversation_ref_hash: str = ""
    capabilities: tuple[str, ...] = ()
    failure_domain: str = "CHATGPT_BROWSER"
    current: bool = True


def classify_carrier_failure(code: str) -> CarrierFailure:
    normalized = (code or "").strip().upper() or "UNKNOWN_CARRIER_FAILURE"
    if normalized in ROUTE_LOCAL_FAILURES:
        return CarrierFailure(
            normalized,
            FailureDisposition.ROUTE_LOCAL,
            mission_terminal=False,
            retry_same_carrier=False,
            goal_mutation_allowed=False,
            bypass_allowed=False,
        )
    if normalized in AUTH_FAILURES:
        return CarrierFailure(
            normalized,
            FailureDisposition.AUTH_REQUIRED,
            mission_terminal=False,
            retry_same_carrier=False,
            goal_mutation_allowed=False,
            bypass_allowed=False,
        )
    if normalized in HARD_BOUNDARIES:
        return CarrierFailure(
            normalized,
            FailureDisposition.HARD_BOUNDARY,
            mission_terminal=False,
            retry_same_carrier=False,
            goal_mutation_allowed=False,
            bypass_allowed=False,
        )
    return CarrierFailure(
        normalized,
        FailureDisposition.UNKNOWN,
        mission_terminal=False,
        retry_same_carrier=False,
        goal_mutation_allowed=False,
        bypass_allowed=False,
    )


class BrowserCarrierSupervisor:
    """Durable browser/client carrier failover over the existing SOL 6.2 state root.

    A carrier is a replaceable client surface such as a ChatGPT browser tab or
    FUSE-owned web client. Carrier loss never becomes mission completion or
    mission failure by itself. Handoff never grants provider/effect authority.
    """

    def __init__(self, client: Sol62CompleteClientRuntime, *, heartbeat_ttl_seconds: int = 45) -> None:
        if heartbeat_ttl_seconds < 5:
            raise ValueError("HEARTBEAT_TTL_TOO_LOW")
        self.client = client
        self.heartbeat_ttl_seconds = int(heartbeat_ttl_seconds)

    def _now(self, now_epoch: int | None) -> int:
        return int(time.time()) if now_epoch is None else int(now_epoch)

    def register(
        self,
        registration: CarrierRegistration,
        *,
        now_epoch: int | None = None,
    ) -> dict[str, Any]:
        if not registration.carrier_id or not registration.owner_subject or not registration.session_id:
            raise ConstraintError("CARRIER_ID_OWNER_SESSION_REQUIRED")
        now = self._now(now_epoch)
        existing = self.client._get("sol62.browser.carrier", registration.carrier_id)
        prior_epoch = int(existing["value"].get("carrier_epoch", 0)) if existing else 0
        body = {
            "schema": SCHEMA,
            **asdict(registration),
            "capabilities": list(registration.capabilities),
            "carrier_epoch": prior_epoch + 1,
            "state": CarrierState.HEALTHY.value,
            "registered_epoch": int(existing["value"].get("registered_epoch", now)) if existing else now,
            "last_seen_epoch": now,
            "last_failure": "",
            "last_failure_disposition": "",
            "mission_authority": False,
            "effect_authority": False,
            "provider_authority": False,
            "chat_is_detachable": True,
        }
        stored = self.client._put("sol62.browser.carrier", registration.carrier_id, body)
        self.client.runtime.control.append_event(
            registration.carrier_id,
            "SOL62_BROWSER_CARRIER_REGISTERED",
            {
                "carrier_epoch": body["carrier_epoch"],
                "owner_subject": registration.owner_subject,
                "client_kind": registration.client_kind,
                "route_id": registration.route_id,
            },
        )
        return stored

    def heartbeat(
        self,
        carrier_id: str,
        *,
        observed_state: str = "HEALTHY",
        conversation_ref_hash: str = "",
        now_epoch: int | None = None,
    ) -> dict[str, Any]:
        row = self.client._get("sol62.browser.carrier", carrier_id)
        if not row:
            raise KeyError(carrier_id)
        now = self._now(now_epoch)
        state = CarrierState(observed_state.upper())
        body = dict(row["value"])
        body.update(
            {
                "state": state.value,
                "last_seen_epoch": now,
                "conversation_ref_hash": conversation_ref_hash or body.get("conversation_ref_hash", ""),
            }
        )
        stored = self.client._put("sol62.browser.carrier", carrier_id, body)
        self.client.runtime.control.append_event(
            carrier_id,
            "SOL62_BROWSER_CARRIER_HEARTBEAT",
            {"state": state.value, "carrier_epoch": body["carrier_epoch"]},
        )
        return stored

    def report_failure(
        self,
        carrier_id: str,
        *,
        code: str,
        now_epoch: int | None = None,
    ) -> dict[str, Any]:
        row = self.client._get("sol62.browser.carrier", carrier_id)
        if not row:
            raise KeyError(carrier_id)
        now = self._now(now_epoch)
        failure = classify_carrier_failure(code)
        body = dict(row["value"])
        body.update(
            {
                "state": CarrierState.FAILED.value,
                "last_seen_epoch": now,
                "last_failure": failure.code,
                "last_failure_disposition": failure.disposition.value,
            }
        )
        stored = self.client._put("sol62.browser.carrier", carrier_id, body)
        self.client.runtime.control.append_event(
            carrier_id,
            "SOL62_BROWSER_CARRIER_FAILED",
            {
                "code": failure.code,
                "disposition": failure.disposition.value,
                "mission_terminal": failure.mission_terminal,
                "retry_same_carrier": failure.retry_same_carrier,
                "bypass_allowed": failure.bypass_allowed,
            },
        )
        return {
            "carrier": stored,
            "failure": asdict(failure),
            "mission_continuity": "PRESERVED",
        }

    def _eligible(self, owner_subject: str, *, now_epoch: int) -> list[dict[str, Any]]:
        rows = self.client._rows("sol62.browser.carrier")
        eligible: list[dict[str, Any]] = []
        for row in rows:
            value = row["value"]
            if value.get("owner_subject") != owner_subject:
                continue
            if not bool(value.get("current", True)):
                continue
            if value.get("state") not in {CarrierState.HEALTHY.value, CarrierState.DEGRADED.value}:
                continue
            age = now_epoch - int(value.get("last_seen_epoch", 0))
            if age > self.heartbeat_ttl_seconds:
                continue
            eligible.append(value)
        return eligible

    def elect(
        self,
        *,
        owner_subject: str,
        now_epoch: int | None = None,
        exclude_carrier_id: str = "",
    ) -> dict[str, Any] | None:
        now = self._now(now_epoch)
        candidates = [
            value
            for value in self._eligible(owner_subject, now_epoch=now)
            if value.get("carrier_id") != exclude_carrier_id
        ]
        if not candidates:
            return None
        candidates.sort(
            key=lambda value: (
                0 if value.get("state") == CarrierState.HEALTHY.value else 1,
                -int(value.get("priority", 50)),
                -int(value.get("last_seen_epoch", 0)),
                str(value.get("carrier_id")),
            )
        )
        return dict(candidates[0])

    def attach_mission(
        self,
        mission_id: str,
        *,
        owner_subject: str,
        carrier_id: str,
        now_epoch: int | None = None,
    ) -> dict[str, Any]:
        carrier = self.client._get("sol62.browser.carrier", carrier_id)
        if not carrier:
            raise KeyError(carrier_id)
        if carrier["value"].get("owner_subject") != owner_subject:
            raise ConstraintError("CARRIER_OWNER_MISMATCH")
        now = self._now(now_epoch)
        existing = self.client._get("sol62.browser.mission_carrier", mission_id)
        previous_epoch = int(existing["value"].get("mission_carrier_epoch", 0)) if existing else 0
        previous_carrier = existing["value"].get("carrier_id", "") if existing else ""
        body = {
            "schema": SCHEMA,
            "mission_id": mission_id,
            "owner_subject": owner_subject,
            "carrier_id": carrier_id,
            "carrier_epoch": int(carrier["value"]["carrier_epoch"]),
            "mission_carrier_epoch": previous_epoch + 1,
            "previous_carrier_id": previous_carrier,
            "attached_epoch": now,
            "state": "ATTACHED",
            "effect_replay_allowed": False,
            "effect_readback_before_retry": True,
        }
        stored = self.client._put("sol62.browser.mission_carrier", mission_id, body)
        self.client.runtime.control.append_event(
            mission_id,
            "SOL62_BROWSER_MISSION_CARRIER_ATTACHED",
            {
                "carrier_id": carrier_id,
                "previous_carrier_id": previous_carrier,
                "mission_carrier_epoch": body["mission_carrier_epoch"],
                "effect_replay_allowed": False,
            },
        )
        return stored

    def failover(
        self,
        mission_id: str,
        *,
        owner_subject: str,
        failed_carrier_id: str,
        failure_code: str,
        now_epoch: int | None = None,
    ) -> dict[str, Any]:
        now = self._now(now_epoch)
        failure_result = self.report_failure(failed_carrier_id, code=failure_code, now_epoch=now)
        replacement = self.elect(
            owner_subject=owner_subject,
            now_epoch=now,
            exclude_carrier_id=failed_carrier_id,
        )
        inflight = self.client._inflight_for_mission(mission_id)
        if replacement is None:
            return {
                "schema": SCHEMA,
                "state": "WAITING_CARRIER",
                "mission_id": mission_id,
                "failed_carrier_id": failed_carrier_id,
                "failure": failure_result["failure"],
                "mission_terminal": False,
                "resume_packet": self.client.resume_packet(mission_id, reason="WAITING_CARRIER"),
                "effect_replay_allowed": False,
                "inflight_effects": inflight,
            }
        attachment = self.attach_mission(
            mission_id,
            owner_subject=owner_subject,
            carrier_id=str(replacement["carrier_id"]),
            now_epoch=now,
        )
        state = "WAITING_EFFECT_READBACK" if inflight else "HYDRATE_REPLACEMENT"
        return {
            "schema": SCHEMA,
            "state": state,
            "mission_id": mission_id,
            "failed_carrier_id": failed_carrier_id,
            "replacement_carrier_id": replacement["carrier_id"],
            "failure": failure_result["failure"],
            "mission_terminal": False,
            "attachment": attachment,
            "effect_replay_allowed": False,
            "effect_readback_before_retry": True,
            "inflight_effects": inflight,
            "hydration": self.hydration_packet(
                mission_id,
                carrier_id=str(replacement["carrier_id"]),
                now_epoch=now,
            ),
        }

    def hydration_packet(
        self,
        mission_id: str,
        *,
        carrier_id: str,
        now_epoch: int | None = None,
    ) -> dict[str, Any]:
        now = self._now(now_epoch)
        carrier = self.client._get("sol62.browser.carrier", carrier_id)
        binding = self.client._get("sol62.browser.mission_carrier", mission_id)
        mission = self.client._get("sol62.client.mission", mission_id)
        if not carrier or not mission:
            raise ConstraintError("HYDRATION_SOURCE_MISSING")
        if carrier["value"].get("owner_subject") != mission["value"].get("owner_subject"):
            raise ConstraintError("HYDRATION_OWNER_MISMATCH")
        events = self.client.runtime.control.db.execute(
            "SELECT seq,event_hash,kind FROM events WHERE aggregate=? ORDER BY seq DESC LIMIT 1",
            (mission_id,),
        ).fetchone()
        return {
            "schema": "SOL62_BROWSER_HYDRATION_PACKET_V1",
            "mission_id": mission_id,
            "carrier_id": carrier_id,
            "carrier_epoch": int(carrier["value"]["carrier_epoch"]),
            "mission_carrier_epoch": int(binding["value"]["mission_carrier_epoch"]) if binding else 0,
            "created_epoch": now,
            "client_state": {
                "state": mission["value"].get("state"),
                "last_reason": mission["value"].get("last_reason"),
                "total_attempts": mission["value"].get("total_attempts", 0),
                "next_retry_epoch": mission["value"].get("next_retry_epoch", 0),
            },
            "continuity_anchor": {
                "last_event_seq": int(events["seq"]) if events else 0,
                "last_event_hash": events["event_hash"] if events else "",
                "last_event_kind": events["kind"] if events else "",
            },
            "resume_packet": self.client.resume_packet(mission_id, reason="CARRIER_HYDRATION"),
            "effect_replay_allowed": False,
            "effect_readback_before_retry": True,
            "conversation_identity_is_nonauthoritative": True,
            "provider_credentials_in_packet": False,
            "packet_sha256": digest(
                {
                    "mission_id": mission_id,
                    "carrier_id": carrier_id,
                    "carrier_epoch": int(carrier["value"]["carrier_epoch"]),
                    "mission_carrier_epoch": int(binding["value"]["mission_carrier_epoch"]) if binding else 0,
                    "last_event_hash": events["event_hash"] if events else "",
                }
            ),
        }
