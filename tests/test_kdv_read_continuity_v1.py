from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
if not (ROOT/"federation_consolidation/sovara_sovereign_backup.py").exists():
    raise unittest.SkipTest(
        "Phoenix Core export intentionally excludes federation_consolidation backup source"
    )

from evidenceops.kim_dataverse.projection_contract import ProjectionContractError
from federation.fkcm_v1.models import (
    Authority,
    Effect,
    EventEnvelope,
    Privacy,
    TruthClass,
)
from federation.kdv_read_continuity_v1 import (
    build_continuity_snapshot,
    restore_continuity_snapshot,
)
from federation_consolidation.sovara_sovereign_backup import BackupError


SCHEMA_MANIFEST=ROOT/"config/kim-dataverse-schema-manifest-omega47-v1.json"


def schema_digest() -> str:
    return sha256(SCHEMA_MANIFEST.read_bytes()).hexdigest()


def event(event_id: str, event_type: str, *, seq: int, payload: dict) -> EventEnvelope:
    return EventEnvelope(
        event_id=event_id,
        event_type=event_type,
        entity_id="KIM::MISSION::DEMO",
        source_surface="KIM_DATAVERSE",
        source_key="CONTROL::DEMO",
        event_time=f"2026-09-19T00:0{seq}:00+00:00",
        observed_time=f"2026-09-19T00:0{seq}:01+00:00",
        valid_from=f"2026-09-19T00:0{seq}:00+00:00",
        payload=payload,
        proof_refs=(f"proof:{event_id}",),
        authority=Authority.A1,
        effect=Effect.NONE,
        truth_class=TruthClass.EVENT_TRUTH,
        privacy=Privacy.PRIVATE,
        transaction_id=f"txn:{event_id}",
        source_sequence=seq,
        lineage={"stream_id":"KDV-DEMO","mission_id":"DEMO"},
    )


def events() -> tuple[EventEnvelope,...]:
    return (
        event(
            "E1","STATE_SET",seq=1,
            payload={
                "fields":{"Status":"OPEN","Priority":1},
                "proof_dimensions":{"source":"PROVEN","authority":"READ_AUTHORITY"},
                "fresh_until":"2026-09-19T00:30:00+00:00",
            },
        ),
        event(
            "E2","STATE_SET",seq=2,
            payload={
                "fields":{"Status":"ACTIVE"},
                "proof_dimensions":{"source":"PROVEN","authority":"READ_AUTHORITY"},
                "fresh_until":"2026-09-19T00:30:00+00:00",
            },
        ),
        event(
            "E3","RELATION_ASSERTED",seq=3,
            payload={
                "relation_id":"REL-1",
                "subject_entity_id":"KIM::MISSION::DEMO",
                "predicate":"USES",
                "object_entity_id":"KIM::CAPABILITY::FORGE",
            },
        ),
    )


class KDVReadContinuityV1Tests(unittest.TestCase):
    def snapshot(self):
        return build_continuity_snapshot(
            events(),
            source_id="KIM_DATAVERSE",
            source_revision="provider-revision-demo-001",
            observed_at="2026-09-19T00:10:00+00:00",
            schema_sha256=schema_digest(),
            provider_read_verified_at_capture=True,
        )

    def test_snapshot_is_deterministic_and_non_authoritative(self):
        a=self.snapshot(); b=self.snapshot()
        self.assertEqual(a.archive_sha256,b.archive_sha256)
        self.assertEqual(a.manifest_sha256,b.manifest_sha256)
        self.assertEqual(a.projection_sha256,b.projection_sha256)
        self.assertFalse(a.canonical_authority)
        self.assertFalse(a.provider_effect_authorized)
        self.assertEqual(a.mirror_role,"NONAUTHORITATIVE_READ_CONTINUITY")

    def test_restore_replays_projection_and_serves_as_of_read(self):
        snap=self.snapshot()
        reader=restore_continuity_snapshot(
            snap.archive_bytes,
            expected_archive_sha256=snap.archive_sha256,
        )
        self.assertTrue(reader.restore_receipt.projection_replay_equal)
        self.assertTrue(reader.restore_receipt.archive_sha256_verified)
        self.assertTrue(reader.restore_receipt.as_of_only)
        self.assertFalse(reader.restore_receipt.present_tense_current_claim_allowed)
        r=reader.query("KIM::MISSION::DEMO","Status")
        self.assertTrue(r.found)
        self.assertEqual(r.value,"ACTIVE")
        self.assertTrue(r.as_of_only)
        self.assertFalse(r.canonical_authority)

    def test_present_tense_query_requires_fresh_provider_read(self):
        reader=restore_continuity_snapshot(self.snapshot().archive_bytes)
        with self.assertRaisesRegex(
            ProjectionContractError,
            "KDV_PROVIDER_READ_REQUIRED_FOR_PRESENT_TENSE",
        ):
            reader.query("KIM::MISSION::DEMO","Status",require_current=True)

    def test_provider_read_at_capture_does_not_become_permanent_currentness(self):
        reader=restore_continuity_snapshot(self.snapshot().archive_bytes)
        self.assertTrue(reader.restore_receipt.provider_read_verified_at_capture)
        currentness=reader.currentness()
        self.assertTrue(currentness.as_of_only)
        self.assertFalse(currentness.present_tense_source_claim_allowed)

    def test_corrupt_archive_fails_closed(self):
        snap=self.snapshot()
        corrupt=bytearray(snap.archive_bytes)
        corrupt[-24] ^= 1
        with self.assertRaises(BackupError):
            restore_continuity_snapshot(
                bytes(corrupt),
                expected_archive_sha256=snap.archive_sha256,
            )

    def test_schema_manifest_is_bound_to_real_repository_contract(self):
        snap=self.snapshot()
        self.assertEqual(snap.schema_sha256,schema_digest())
        manifest=json.loads(SCHEMA_MANIFEST.read_text())
        self.assertEqual(manifest["status"],"CURRENT_PUBLIC_SAFE_SUCCESSOR")

    def test_fkcm_reuse_boundary_remains_non_sovereign_and_read_only(self):
        admission=json.loads((ROOT/"governance/fkcm_v1_admission.json").read_text())
        self.assertEqual(
            admission["architecture_mode"],
            "ADDITIVE_CONVERGENCE_NOT_NEW_SOVEREIGN_PLANE",
        )
        self.assertFalse(admission["truth_boundary"]["provider_effect"])
        self.assertFalse(admission["truth_boundary"]["kdv_cutover"])
        self.assertFalse(admission["truth_boundary"]["new_master_created"])
        self.assertEqual(admission["qualification"]["restart_replay"],"9+10 STATE_AND_RELATIONS_EQUAL")

    def test_governance_exposes_no_write_or_cutover_authority(self):
        g=json.loads((ROOT/"governance/kdv_read_continuity_v1.json").read_text())
        self.assertFalse(g["new_sovereign_plane"])
        self.assertFalse(g["canonical_source_replaced"])
        self.assertFalse(g["authority"]["write_method_exposed"])
        self.assertFalse(g["authority"]["write_authority"])
        self.assertFalse(g["authority"]["provider_effect_authorized"])
        self.assertFalse(g["authority"]["canonical_authority"])
        self.assertFalse(g["authority"]["cutover_authorized"])
        self.assertEqual(g["read_modes"],["AS_OF_ONLY"])

if __name__=="__main__":
    unittest.main()
