from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from benchmarking.cfbe_omega.mission_result_fabric_adapter_v1 import compile_mission_result_identity
from benchmarking.cfbe_omega.mission_result_index_v1 import DurableMissionResultIndex
from federation.mission_ir import MissionIR


class DurableMissionResultIndexTests(unittest.TestCase):
    def _identity(self, *, source: str = "main@test", fresh_until: str = "2026-09-01T00:00:00+02:00"):
        mission = MissionIR(
            mission_id="RESULT-INDEX-1",
            objective="Compile one deterministic shadow result.",
            domain="TEST",
            outcome_contract="One reusable proof-bound result.",
            source_frontier=source,
            privacy_class="PUBLIC",
            rights_state="NOT_APPLICABLE",
            effect_class="READ_ONLY",
            authority_requirements=(),
            proof_requirements=("READBACK",),
        ).normalized()
        return compile_mission_result_identity(
            mission,
            step_id="compile-shadow-plan",
            input_identity={"payload": "alpha"},
            policy_identity={"policy": "v1"},
            environment_identity={"runtime": "python312"},
            proof_scope="MISSIONIR_SHADOW",
            fresh_until=fresh_until,
        )

    def test_record_restart_and_exact_lookup_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result-index.jsonl"
            identity = self._identity()
            first = DurableMissionResultIndex(path)
            recorded = first.record(
                identity,
                result_ref="runtime-proof/result.json",
                result_sha256="a" * 64,
                proof_refs=("proof:shadow", "source:test"),
                recorded_at="2026-08-31T20:45:00+02:00",
                now="2026-08-31T20:45:00+02:00",
            )
            self.assertEqual("RECORDED", recorded.state)
            self.assertTrue(first.verify()["valid"])

            restored = DurableMissionResultIndex(path)
            hit = restored.lookup(identity, now="2026-08-31T20:46:00+02:00")
            self.assertEqual("HIT", hit.state)
            self.assertTrue(hit.reuse)
            self.assertEqual(("proof:shadow", "source:test"), hit.proof_refs)
            self.assertEqual(1, restored.verify()["record_count"])

    def test_exact_replay_is_idempotent_and_conflict_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result-index.jsonl"
            identity = self._identity()
            index = DurableMissionResultIndex(path)
            kwargs = dict(
                result_ref="runtime-proof/result.json",
                result_sha256="b" * 64,
                proof_refs=("proof:shadow",),
                recorded_at="2026-08-31T20:45:00+02:00",
                now="2026-08-31T20:45:00+02:00",
            )
            index.record(identity, **kwargs)
            size = path.stat().st_size
            replay = index.record(identity, **kwargs)
            self.assertEqual("HIT", replay.state)
            self.assertEqual(size, path.stat().st_size)
            with self.assertRaisesRegex(ValueError, "RESULT_INDEX_CONFLICTING_CACHE_KEY"):
                index.record(identity, **{**kwargs, "result_sha256": "c" * 64})

    def test_source_drift_misses_and_expired_identity_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result-index.jsonl"
            identity = self._identity()
            index = DurableMissionResultIndex(path)
            index.record(
                identity,
                result_ref="runtime-proof/result.json",
                result_sha256="d" * 64,
                proof_refs=("proof:shadow",),
                recorded_at="2026-08-31T20:45:00+02:00",
                now="2026-08-31T20:45:00+02:00",
            )
            drift = self._identity(source="main@changed")
            self.assertEqual("MISS", index.lookup(drift, now="2026-08-31T20:46:00+02:00").state)
            expired = self._identity(fresh_until="2026-08-31T20:45:30+02:00")
            self.assertEqual(
                "HOLD_FRESHNESS_EXPIRED",
                index.lookup(expired, now="2026-08-31T20:46:00+02:00").state,
            )

    def test_tamper_is_detected_on_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result-index.jsonl"
            identity = self._identity()
            index = DurableMissionResultIndex(path)
            index.record(
                identity,
                result_ref="runtime-proof/result.json",
                result_sha256="e" * 64,
                proof_refs=("proof:shadow",),
                recorded_at="2026-08-31T20:45:00+02:00",
                now="2026-08-31T20:45:00+02:00",
            )
            path.write_text(path.read_text(encoding="utf-8").replace("runtime-proof/result.json", "runtime-proof/tampered.json"), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "RESULT_INDEX_HASH_MISMATCH"):
                DurableMissionResultIndex(path)


if __name__ == "__main__":
    unittest.main()
