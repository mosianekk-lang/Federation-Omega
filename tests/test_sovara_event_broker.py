from __future__ import annotations

import hashlib
import json
import unittest

from federation_consolidation.sovara_event_broker import (
    PubSubPublishError,
    SovaraEventBroker,
)


class FakeFuture:
    def __init__(self, message_id: str | None = "msg-123", error: Exception | None = None):
        self.message_id = message_id
        self.error = error
        self.timeouts: list[float | None] = []

    def result(self, timeout: float | None = None):
        self.timeouts.append(timeout)
        if self.error is not None:
            raise self.error
        return self.message_id


class FakePublisher:
    def __init__(self, future: FakeFuture | None = None, publish_error: Exception | None = None):
        self.future = future or FakeFuture()
        self.publish_error = publish_error
        self.calls: list[tuple[str, bytes, dict[str, str]]] = []

    def publish(self, topic: str, data: bytes, **attrs: str):
        self.calls.append((topic, data, attrs))
        if self.publish_error is not None:
            raise self.publish_error
        return self.future


class SovaraEventBrokerTests(unittest.TestCase):
    def test_provider_message_id_is_required_for_published_state(self):
        publisher = FakePublisher(FakeFuture("provider-message-42"))
        broker = SovaraEventBroker(project_id="sov-hybrid-suite", publisher=publisher)

        receipt = broker.publish_command(
            "GEMINI_NONCE_READBACK",
            {"nonce": "SYNTHETIC-NONCE"},
            requested_by="CHATGPT",
        )

        self.assertEqual("PUBLISHED_PROVIDER_ACKED", receipt["status"])
        self.assertEqual("google_pubsub", receipt["provider"])
        self.assertEqual("provider-message-42", receipt["provider_message_id"])
        self.assertTrue(receipt["provider_ack"])
        self.assertTrue(receipt["provider_message_id_present"])
        self.assertFalse(receipt["credential_value_recorded"])
        self.assertEqual(1, len(publisher.calls))

        topic, raw, attrs = publisher.calls[0]
        self.assertEqual("projects/sov-hybrid-suite/topics/sovara-commands", topic)
        event = json.loads(raw.decode("utf-8"))
        self.assertEqual("1.0", event["specversion"])
        self.assertEqual("com.sovara.command.gemini_nonce_readback", event["type"])
        self.assertEqual("sovara://chatgpt", event["source"])
        self.assertEqual("SYNTHETIC-NONCE", event["data"]["payload"]["nonce"])
        expected = hashlib.sha256(
            json.dumps(event["data"], sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self.assertEqual(expected, event["data_sha256"])
        self.assertEqual(event["id"], attrs["ce_id"])
        self.assertEqual(event["data_sha256"], attrs["data_sha256"])

    def test_empty_provider_message_id_fails_closed(self):
        broker = SovaraEventBroker(
            project_id="sov-hybrid-suite",
            publisher=FakePublisher(FakeFuture("")),
        )
        with self.assertRaisesRegex(PubSubPublishError, "without a provider message ID"):
            broker.publish_command("STATUS", {})

    def test_provider_future_failure_fails_closed(self):
        broker = SovaraEventBroker(
            project_id="sov-hybrid-suite",
            publisher=FakePublisher(FakeFuture(error=RuntimeError("synthetic provider failure"))),
        )
        with self.assertRaisesRegex(PubSubPublishError, "provider acknowledgement"):
            broker.publish_command("STATUS", {})

    def test_publish_call_failure_fails_closed(self):
        broker = SovaraEventBroker(
            project_id="sov-hybrid-suite",
            publisher=FakePublisher(publish_error=RuntimeError("synthetic transport failure")),
        )
        with self.assertRaisesRegex(PubSubPublishError, "provider acknowledgement"):
            broker.publish_command("STATUS", {})

    def test_invalid_action_fails_before_provider_effect(self):
        publisher = FakePublisher()
        broker = SovaraEventBroker(project_id="sov-hybrid-suite", publisher=publisher)
        with self.assertRaisesRegex(ValueError, "action must be non-empty"):
            broker.publish_command("  ", {})
        self.assertEqual([], publisher.calls)

    def test_non_mapping_payload_fails_before_provider_effect(self):
        publisher = FakePublisher()
        broker = SovaraEventBroker(project_id="sov-hybrid-suite", publisher=publisher)
        with self.assertRaisesRegex(TypeError, "payload must be a mapping"):
            broker.publish_command("STATUS", ["not", "a", "mapping"])  # type: ignore[arg-type]
        self.assertEqual([], publisher.calls)

    def test_timeout_is_forwarded_to_provider_future(self):
        future = FakeFuture("msg-timeout")
        broker = SovaraEventBroker(
            project_id="sov-hybrid-suite",
            publisher=FakePublisher(future),
            publish_timeout_seconds=7.5,
        )
        broker.publish_command("STATUS", {})
        self.assertEqual([7.5], future.timeouts)

    def test_cloud_event_can_be_made_deterministic_for_proof_tests(self):
        broker = SovaraEventBroker(project_id="sov-hybrid-suite", publisher=FakePublisher())
        event = broker.create_cloudevent(
            "proof.synthetic",
            "unit-test",
            {"b": 2, "a": 1},
            event_id="evt-fixed",
            event_time="2026-08-25T10:00:00Z",
        )
        self.assertEqual("evt-fixed", event["id"])
        self.assertEqual("2026-08-25T10:00:00Z", event["time"])
        expected = hashlib.sha256(b'{"a":1,"b":2}').hexdigest()
        self.assertEqual(expected, event["data_sha256"])

    def test_invalid_timeout_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            SovaraEventBroker(
                project_id="sov-hybrid-suite",
                publisher=FakePublisher(),
                publish_timeout_seconds=0,
            )


if __name__ == "__main__":
    unittest.main()
