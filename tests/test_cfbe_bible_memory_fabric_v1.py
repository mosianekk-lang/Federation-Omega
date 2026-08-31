from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.bible_memory_benchmark_v1 import build_report
from benchmarking.cfbe_omega.bible_memory_fabric_v1 import (
    BibleRenderer,
    HybridRetrievalPlanner,
    InMemoryEventStore,
    MemoryDocument,
    MemoryEvent,
    ProjectionCompiler,
)


class CFBEBibleMemoryBenchmarkTests(unittest.TestCase):
    def test_current_and_target_scores_are_bounded_and_gap_is_material(self) -> None:
        report = build_report()
        self.assertAlmostEqual(report.architecture_score, 66.43, places=2)
        self.assertAlmostEqual(report.target_score, 96.66, places=2)
        self.assertAlmostEqual(report.proof_adjusted_operational_score, 50.49, places=2)
        self.assertGreater(report.gap, 25)
        self.assertEqual(24, len(report.genes))
        self.assertIn("EVENT_TRUTH_NEVER_REPLACED_BY_SUMMARY", report.hard_gates)


class CFBEBibleMemoryFabricTests(unittest.TestCase):
    def _event(self, version: int, event_id: str, event_type: str, payload: dict, **kwargs) -> MemoryEvent:
        return MemoryEvent(
            event_id=event_id,
            stream_id="WORKSTREAM-1",
            stream_version=version,
            event_type=event_type,
            recorded_at=f"2026-08-31T20:0{version}:00+02:00",
            valid_at=f"2026-08-31T20:0{version}:00+02:00",
            idempotency_key=f"idem-{event_id}",
            truth_class="EVENT_TRUTH",
            privacy_class="INTERNAL",
            payload=payload,
            **kwargs,
        )

    def test_append_requires_expected_version(self) -> None:
        store = InMemoryEventStore()
        store.append(self._event(1, "E1", "STATE_SET", {"state": "A"}), expected_version=0)
        with self.assertRaisesRegex(ValueError, "MEMORY_STREAM_VERSION_CONFLICT"):
            store.append(self._event(2, "E2", "STATE_SET", {"state": "B"}), expected_version=0)

    def test_idempotent_replay_and_parameter_mismatch(self) -> None:
        store = InMemoryEventStore()
        event = self._event(1, "E1", "STATE_SET", {"state": "A"})
        first = store.append(event, expected_version=0)
        replay = store.append(event, expected_version=1)
        self.assertEqual("APPENDED", first.state)
        self.assertEqual("IDEMPOTENT_REPLAY", replay.state)
        changed = MemoryEvent(**({**event.__dict__, "payload": {"state": "CHANGED"}})) if hasattr(event, "__dict__") else MemoryEvent(
            event_id=event.event_id, stream_id=event.stream_id, stream_version=event.stream_version,
            event_type=event.event_type, recorded_at=event.recorded_at, valid_at=event.valid_at,
            idempotency_key=event.idempotency_key, truth_class=event.truth_class,
            privacy_class=event.privacy_class, payload={"state": "CHANGED"}
        )
        with self.assertRaisesRegex(ValueError, "MEMORY_IDEMPOTENCY_PARAMETER_MISMATCH"):
            store.append(changed, expected_version=1)

    def test_current_and_as_of_projection_preserve_history(self) -> None:
        store = InMemoryEventStore()
        store.append(self._event(1, "E1", "STATE_SET", {"state": "A"}, directive_id="D1", mission_id="M1"), expected_version=0)
        store.append(self._event(2, "E2", "STATE_SET", {"state": "B"}, directive_id="D2", mission_id="M1", supersedes=("E1",)), expected_version=1)
        projector = ProjectionCompiler()
        current = projector.project(store.stream("WORKSTREAM-1"))
        past = projector.project(store.stream("WORKSTREAM-1"), as_of_recorded_at="2026-08-31T20:01:30+02:00")
        self.assertEqual("B", current.current["state"])
        self.assertEqual("A", past.current["state"])
        self.assertIn("E1", current.superseded_event_ids)
        self.assertEqual(("D1", "D2"), current.directive_ids)

    def test_global_sensitive_payload_is_rejected(self) -> None:
        event = MemoryEvent(
            event_id="E1", stream_id="GLOBAL", stream_version=1, event_type="STATE_SET",
            recorded_at="2026-08-31T20:00:00+02:00", valid_at="2026-08-31T20:00:00+02:00",
            idempotency_key="I1", truth_class="EVENT_TRUTH", privacy_class="GLOBAL",
            payload={"secret": "must-not-be-global"},
        )
        with self.assertRaisesRegex(ValueError, "GLOBAL_MEMORY_SENSITIVE_PAYLOAD_REJECTED"):
            event.validate()

    def test_hybrid_retrieval_respects_workstream_and_budget(self) -> None:
        docs = (
            MemoryDocument("A", "repair proof route", "VERIFIED", "INTERNAL", ("source:A",), workstream_id="W1", lexical_terms=("repair",), graph_keys=("proof",), embedding_ref="emb:A", token_cost=2),
            MemoryDocument("B", "unrelated private matter", "VERIFIED", "INTERNAL", ("source:B",), workstream_id="W2", lexical_terms=("repair",), token_cost=1),
            MemoryDocument("C", "repair note", "INFERENCE", "INTERNAL", ("source:C",), workstream_id="W1", lexical_terms=("repair",), token_cost=4),
        )
        selected = HybridRetrievalPlanner().select(docs, query="repair proof", token_budget=2, workstream_id="W1")
        self.assertEqual(("A",), tuple(item.memory_id for item in selected))

    def test_bible_renderer_is_projection_not_event_truth(self) -> None:
        store = InMemoryEventStore()
        store.append(self._event(1, "E1", "STATE_SET", {"state": "ACTIVE"}, directive_id="D1", mission_id="M1"), expected_version=0)
        projection = ProjectionCompiler().project(store.stream("WORKSTREAM-1"))
        rendered = BibleRenderer().render(projection, doctrine_ref="drive:canonical-bible", memory_refs=("event:E1",))
        self.assertEqual("ACTIVE", rendered["current_state"]["state"])
        self.assertIn("rendered_bible_is_a_projection_not_primary_event_truth", rendered["truth_boundary"])


if __name__ == "__main__":
    unittest.main()
