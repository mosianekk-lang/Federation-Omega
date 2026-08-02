from __future__ import annotations

import unittest
from dataclasses import replace

from evidenceops.capability_heartbeat.foundation.errors import PrivacyError
from evidenceops.heartbeat_api.errors import ImmutableConflict, RuntimeUnavailable
from evidenceops.heartbeat_api.runtime import HeartbeatApiRuntime
from evidenceops.heartbeat_api.schemas import SearchRequest
from evidenceops.heartbeat_api.store import InMemoryImmutableStore

from .helpers import ingest_request, runtime


class RuntimeTests(unittest.TestCase):
    def test_readiness_fails_closed_without_configuration(self) -> None:
        from evidenceops.heartbeat_api.runtime import build_runtime_from_env

        state = build_runtime_from_env({}).readiness()
        self.assertFalse(state.ready)
        self.assertIn("AUTHORITY_UNCONFIGURED", state.reasons)
        self.assertIn("INTERNAL_AUTH_UNCONFIGURED", state.reasons)

    def test_invalid_mode_is_rejected_instead_of_downgraded(self) -> None:
        from evidenceops.heartbeat_api.runtime import build_runtime_from_env

        with self.assertRaises(RuntimeUnavailable):
            build_runtime_from_env({"HEARTBEAT_MODE": "prodution"})

    def test_status_rejects_sensitive_custom_store_health(self) -> None:
        class MaliciousHealthStore(InMemoryImmutableStore):
            def health(self):
                return {"healthy": True, "content": "UNSAFE"}

        baseline = runtime()
        active = HeartbeatApiRuntime(
            config=baseline.config,
            store=MaliciousHealthStore(),
            authority=baseline.authority,
        )
        with self.assertRaises(PrivacyError):
            active.status()

    def test_production_requires_external_immutable_durability(self) -> None:
        active = runtime()
        production = HeartbeatApiRuntime(
            config=replace(active.config, mode="production"),
            store=InMemoryImmutableStore(),
            authority=active.authority,
        )
        state = production.readiness()
        self.assertFalse(state.ready)
        self.assertIn("EXTERNAL_IMMUTABLE_STORE_REQUIRED", state.reasons)
        self.assertIn("PROVIDER_REGISTRY_PROOF_REQUIRED", state.reasons)
        self.assertIn("PROVIDER_STORAGE_PROOF_REQUIRED", state.reasons)

    def test_stop_fence_blocks_readiness_replay_readback_search_and_fetch(self) -> None:
        active = runtime()
        request = ingest_request()
        result = active.ingest(request, accepted_at=request.observed_at)
        object.__setattr__(
            active.authority,
            "stop_control",
            active.authority.stop_control.stop("STOP-OWNER"),
        )
        self.assertFalse(active.readiness(now=request.observed_at).ready)
        with self.assertRaises(RuntimeUnavailable):
            active.ingest(request, accepted_at=request.observed_at)
        with self.assertRaises(RuntimeUnavailable):
            active.readback(request.idempotency_hash, now=request.observed_at)
        with self.assertRaises(RuntimeUnavailable):
            active.search(SearchRequest(), now=request.observed_at)
        with self.assertRaises(RuntimeUnavailable):
            active.fetch(result.resource_id, now=request.observed_at)

    def test_ingest_replay_readback_search_and_fetch(self) -> None:
        active = runtime()
        request = ingest_request()
        first = active.ingest(request, accepted_at=request.observed_at)
        self.assertTrue(first.created)
        self.assertFalse(first.replayed)
        second = active.ingest(request, accepted_at=request.observed_at)
        self.assertFalse(second.created)
        self.assertTrue(second.replayed)
        self.assertEqual(first.resource_id, second.resource_id)
        self.assertEqual(first.object_hash, second.object_hash)

        readback = active.readback(request.idempotency_hash)
        self.assertTrue(readback["verified"])
        self.assertEqual(readback["receipt_id"], first.receipt_id)
        results = active.search(SearchRequest(resource_kind="ALL"), now=request.observed_at)
        self.assertEqual(results.total, 3)
        fetched = active.fetch(first.resource_id, now=request.observed_at)
        self.assertEqual(fetched.resource["receipt_id"], first.receipt_id)
        emitter = active.fetch("emitter/NODE-ROOT", now=request.observed_at)
        self.assertTrue(emitter.resource["can_originate_ingest"])

    def test_conflicting_idempotency_replay_is_rejected(self) -> None:
        active = runtime()
        first = ingest_request()
        active.ingest(first, accepted_at=first.observed_at)
        changed = ingest_request(sequence=2)
        with self.assertRaises(ImmutableConflict):
            active.ingest(changed, accepted_at=changed.observed_at)

    def test_signed_readback_detects_store_tampering(self) -> None:
        active = runtime()
        request = ingest_request()
        active.ingest(request, accepted_at=request.observed_at)
        key = active._event_key(request.idempotency_hash)
        original = active.store._objects[key]
        tampered = original.replace(b'"authority_ceiling":"A0"', b'"authority_ceiling":"A1"')
        self.assertNotEqual(original, tampered)
        active.store._objects[key] = tampered
        with self.assertRaises(RuntimeUnavailable):
            active.readback(request.idempotency_hash, now=request.observed_at)

    def test_readback_rejects_valid_event_substituted_under_another_key(self) -> None:
        active = runtime()
        request_a = ingest_request(idempotency_code="A")
        request_b = ingest_request(idempotency_code="B")
        active.ingest(request_a, accepted_at=request_a.observed_at)
        active.ingest(request_b, accepted_at=request_b.observed_at)
        key_a = active._event_key(request_a.idempotency_hash)
        key_b = active._event_key(request_b.idempotency_hash)
        active.store._objects[key_a] = active.store._objects[key_b]
        with self.assertRaises(RuntimeUnavailable):
            active.readback(request_a.idempotency_hash, now=request_a.observed_at)

    def test_search_uses_bounded_store_page_and_fetch_uses_direct_index(self) -> None:
        class PageSpyStore(InMemoryImmutableStore):
            def __init__(self):
                super().__init__()
                self.page_calls = []

            def page_prefix(self, prefix, *, offset, limit):
                self.page_calls.append((prefix, offset, limit))
                if limit > 2:
                    raise AssertionError("runtime requested an unbounded page")
                return super().page_prefix(prefix, offset=offset, limit=limit)

        baseline = runtime()
        store = PageSpyStore()
        active = HeartbeatApiRuntime(config=baseline.config, store=store, authority=baseline.authority)
        resources = []
        for code in ("PAGE-A", "PAGE-B", "PAGE-C"):
            request = ingest_request(idempotency_code=code)
            resources.append(active.ingest(request, accepted_at=request.observed_at).resource_id)
        result = active.search(SearchRequest(resource_kind="HEARTBEAT", limit=2))
        self.assertEqual(len(result.results), 2)
        self.assertEqual(result.total, 3)
        self.assertEqual(store.page_calls, [("events/", 0, 2)])
        store.page_calls.clear()
        fetched = active.fetch(resources[2])
        self.assertEqual(fetched.resource["resource_id"], resources[2])
        self.assertEqual(store.page_calls, [])

    def test_non_root_origin_is_denied(self) -> None:
        active = runtime()
        body = ingest_request().model_copy(update={"emitter_node_id": "NODE-EVIDENCEOPS"})
        with self.assertRaises(RuntimeUnavailable):
            active.ingest(body, accepted_at=body.observed_at)


if __name__ == "__main__":
    unittest.main()
