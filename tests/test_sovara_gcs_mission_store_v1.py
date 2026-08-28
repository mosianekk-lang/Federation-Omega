from dataclasses import asdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "ops"
for p in (OPS, ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from sovara_sovereign_intelligence_court_v2 import CourtResult, MissionSnapshot, _canonical_json, _sha256_text
from sovara_gcs_mission_store_v1 import GCSMissionStore


class FakeBlob:
    def __init__(self, bucket, name):
        self.bucket = bucket
        self.name = name

    @property
    def generation(self):
        return self.bucket.objects[self.name][1]

    def download_as_bytes(self):
        return self.bucket.objects[self.name][0]

    def upload_from_string(self, data, content_type=None, if_generation_match=None):
        current = self.bucket.objects.get(self.name)
        current_generation = current[1] if current else 0
        if if_generation_match != current_generation:
            raise RuntimeError("PreconditionFailed")
        self.bucket.objects[self.name] = (bytes(data), current_generation + 1)


class FakeBucket:
    def __init__(self):
        self.objects = {}

    def get_blob(self, name):
        return FakeBlob(self, name) if name in self.objects else None

    def blob(self, name):
        return FakeBlob(self, name)


class FakeClient:
    def __init__(self):
        self.fake_bucket = FakeBucket()

    def bucket(self, name):
        return self.fake_bucket


def snapshot():
    return MissionSnapshot(
        schema="TEST",
        mission_id="SOV-EVAL-TEST",
        created_at_utc="2026-08-28T00:00:00+00:00",
        updated_at_utc="2026-08-28T00:00:00+00:00",
        state="RECEIVED",
        source_sha256="0" * 64,
        source_bytes=1,
        language="python",
        objective="review",
        mode="AUTO",
        max_models=4,
        degradation_mode="DEGRADED_DETERMINISTIC_ONLY",
        checkpoint_seq=1,
        completed_states=["RECEIVED"],
        boundary_events=[],
        lane_receipts=[],
    )


def sealed_result():
    result = CourtResult(
        schema="TEST",
        mission_id="SOV-EVAL-TEST",
        source_sha256="0" * 64,
        terminal_state="TEST",
        degradation_mode="DEGRADED_DETERMINISTIC_ONLY",
        panel_summary={},
        consensus_findings=[],
        material_disagreements=[],
        novel_ideas=[],
        adversarial_findings=[],
        ao5_assessment={},
        scientist_assessment={},
        cfbe_assessment={},
        zero_dilution={},
        recommendation="hold incumbent",
        unresolved_unknowns=[],
        receipts=[],
    )
    material = asdict(result)
    material["result_sha256"] = None
    result.result_sha256 = _sha256_text(_canonical_json(material))
    return result


def test_gcs_store_round_trip_is_generation_fenced():
    client = FakeClient()
    store = GCSMissionStore(bucket_name="test-bucket", client=client)
    item = snapshot()
    store.save_snapshot(item)
    loaded = store.load_snapshot(item.mission_id)
    assert loaded is not None
    assert loaded.source_sha256 == item.source_sha256
    item.checkpoint_seq = 2
    store.save_snapshot(item)
    loaded2 = store.load_snapshot(item.mission_id)
    assert loaded2.checkpoint_seq == 2


def test_sealed_result_is_idempotent_but_not_overwritable():
    client = FakeClient()
    store = GCSMissionStore(bucket_name="test-bucket", client=client)
    result = sealed_result()
    store.save_result(result)
    store.save_result(result)
    loaded = store.load_result(result.mission_id)
    assert loaded is not None
    assert loaded.result_sha256 == result.result_sha256
