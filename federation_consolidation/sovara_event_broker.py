from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Protocol


class PubSubPublishError(RuntimeError):
    """Raised when Google Pub/Sub did not return a usable provider acknowledgement."""


class _PublishFuture(Protocol):
    def result(self, timeout: float | None = None) -> Any: ...


class _Publisher(Protocol):
    def publish(self, topic: str, data: bytes, **attrs: str) -> _PublishFuture: ...


@dataclass(frozen=True)
class PublishReceipt:
    status: str
    provider: str
    project_id: str
    topic: str
    event_id: str
    provider_message_id: str
    data_sha256: str
    event_time: str
    acknowledged_at_utc: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "provider": self.provider,
            "project_id": self.project_id,
            "topic": self.topic,
            "event_id": self.event_id,
            "provider_message_id": self.provider_message_id,
            "data_sha256": self.data_sha256,
            "event_time": self.event_time,
            "acknowledged_at_utc": self.acknowledged_at_utc,
            "provider_ack": True,
            "provider_message_id_present": True,
            "credential_value_recorded": False,
        }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _rfc3339_utc(epoch_seconds: float | None = None) -> str:
    epoch_seconds = time.time() if epoch_seconds is None else epoch_seconds
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch_seconds))


def _require_nonempty(value: str, field: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError(f"{field} must be non-empty")
    return cleaned


def _default_publisher() -> _Publisher:
    try:
        from google.cloud import pubsub_v1  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on deployment image
        raise PubSubPublishError(
            "google-cloud-pubsub is not installed; provider transport is unavailable"
        ) from exc
    return pubsub_v1.PublisherClient()


class SovaraEventBroker:
    """Fail-closed CloudEvents publisher for the SOVARA command bus.

    The broker never reports a published state merely because an envelope was
    constructed. A successful result requires the Google Pub/Sub publish future
    to return a non-empty provider message ID.
    """

    def __init__(
        self,
        project_id: str | None = None,
        *,
        commands_topic: str = "sovara-commands",
        events_topic: str = "sovara-events",
        publisher: _Publisher | None = None,
        publish_timeout_seconds: float = 30.0,
    ) -> None:
        self.project_id = _require_nonempty(
            project_id or os.getenv("GCP_PROJECT", "sov-hybrid-suite"),
            "project_id",
        )
        self.commands_topic = _require_nonempty(commands_topic, "commands_topic")
        self.events_topic = _require_nonempty(events_topic, "events_topic")
        if publish_timeout_seconds <= 0:
            raise ValueError("publish_timeout_seconds must be greater than zero")
        self.publish_timeout_seconds = float(publish_timeout_seconds)
        self._publisher = publisher

    @property
    def publisher(self) -> _Publisher:
        if self._publisher is None:
            self._publisher = _default_publisher()
        return self._publisher

    def create_cloudevent(
        self,
        event_type: str,
        source: str,
        data: Mapping[str, Any],
        *,
        event_id: str | None = None,
        event_time: str | None = None,
    ) -> dict[str, Any]:
        event_type = _require_nonempty(event_type, "event_type")
        source = _require_nonempty(source, "source")
        if not isinstance(data, Mapping):
            raise TypeError("data must be a mapping")
        payload = dict(data)
        return {
            "specversion": "1.0",
            "id": event_id or f"evt-{uuid.uuid4()}",
            "source": f"sovara://{source}",
            "type": f"com.sovara.{event_type}",
            "datacontenttype": "application/json",
            "time": event_time or _rfc3339_utc(),
            "data": payload,
            "data_sha256": hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest(),
        }

    def publish_command(
        self,
        action: str,
        payload: Mapping[str, Any],
        *,
        requested_by: str = "GEMINI_SPARK",
    ) -> dict[str, Any]:
        action = _require_nonempty(action, "action")
        requested_by = _require_nonempty(requested_by, "requested_by")
        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a mapping")

        event = self.create_cloudevent(
            event_type=f"command.{action.lower()}",
            source=requested_by.lower(),
            data={
                "action": action,
                "payload": dict(payload),
                "requested_by": requested_by,
                "idempotency_key": f"idemp-{uuid.uuid4()}",
            },
        )
        topic = f"projects/{self.project_id}/topics/{self.commands_topic}"
        serialized = _canonical_json(event).encode("utf-8")

        try:
            future = self.publisher.publish(
                topic,
                serialized,
                content_type="application/cloudevents+json",
                ce_specversion="1.0",
                ce_id=str(event["id"]),
                ce_source=str(event["source"]),
                ce_type=str(event["type"]),
                data_sha256=str(event["data_sha256"]),
            )
            raw_message_id = future.result(timeout=self.publish_timeout_seconds)
        except Exception as exc:
            if isinstance(exc, PubSubPublishError):
                raise
            raise PubSubPublishError(
                "Google Pub/Sub publish did not return a provider acknowledgement"
            ) from exc

        message_id = str(raw_message_id or "").strip()
        if not message_id:
            raise PubSubPublishError(
                "Google Pub/Sub publish completed without a provider message ID"
            )

        return PublishReceipt(
            status="PUBLISHED_PROVIDER_ACKED",
            provider="google_pubsub",
            project_id=self.project_id,
            topic=topic,
            event_id=str(event["id"]),
            provider_message_id=message_id,
            data_sha256=str(event["data_sha256"]),
            event_time=str(event["time"]),
            acknowledged_at_utc=_rfc3339_utc(),
        ).to_mapping()


__all__ = ["PubSubPublishError", "PublishReceipt", "SovaraEventBroker"]
