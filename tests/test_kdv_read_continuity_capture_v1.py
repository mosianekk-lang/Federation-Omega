from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import unittest

from federation.kdv_read_continuity_capture_v1 import (
    REQUIRED_BMF_FIELDS,
    capture_provider_bmf_rows,
)
from federation.kdv_read_continuity_v1 import restore_continuity_snapshot


ROOT=Path(__file__).resolve().parents[1]
SCHEMA_MANIFEST=ROOT/"config/kim-dataverse-schema-manifest-omega47-v1.json"


def schema_digest():
    return sha256(SCHEMA_MANIFEST.read_bytes()).hexdigest()


def row(event_id: str, version: int, event_type: str, payload: dict):
    return {
        "event_id":event_id,
        "stream_id":"workstream:test",
        "stream_version":str(version),
        "event_type":event_type,
        "recorded_at":f"2026-09-19T00:0{version}:00Z",
        "valid_at":f"2026-09-19T00:0{version}:00Z",
        "idempotency_key":f"idem-{event_id}",
        "truth_class":"EVENT_TRUTH",
        "privacy_class":"PUBLIC_SAFE",
        "payload_json":json.dumps(payload,sort_keys=True),
        "source_refs_json":json.dumps([f"github:test/{event_id}"]),
        "directive_id":"DIRECTIVE-TEST",
        "mission_id":"MISSION-TEST",
        "workstream_id":"TEST",
        "supersedes_json":"[]",
        "event_sha256":sha256(event_id.encode()).hexdigest(),
        "provider_persisted_at_sast":f"2026-09-19T02:0{version}:01+02:00",
        "proof_refs_json":"[]",
        "causal_parent_ids_json":"[]",
        "contradicts_json":"[]",
        "schema_version":"1",
    }


def rows():
    return (
        row("evt-1",1,"STATE_SET",{"status":"OPEN","count":1}),
        row("evt-2",2,"RESULT_VERIFIED",{"status":"DONE","count":2}),
    )


class KDVReadContinuityCaptureV1Tests(unittest.TestCase):
    def capture(self):
        return capture_provider_bmf_rows(
            rows(),
            source_ref="KDV:test:BMF_SHADOW_EVENTS!A1:U3",
            observed_at="2026-09-19T02:05:00+02:00",
            schema_sha256=schema_digest(),
            provider_read_verified_at_capture=True,
        )

    def test_required_live_shape_has_twenty_one_fields(self):
        self.assertEqual(len(REQUIRED_BMF_FIELDS),21)

    def test_capture_composes_fkcm_and_f312_without_authority(self):
        package=self.capture()
        self.assertEqual(package.receipt.row_count,2)
        self.assertEqual(package.receipt.stream_count,1)
        self.assertEqual(package.receipt.normalized_event_count,2)
        self.assertFalse(package.receipt.canonical_authority)
        self.assertFalse(package.receipt.write_authority)
        self.assertFalse(package.receipt.provider_effect_authorized)
        self.assertFalse(package.receipt.runtime_deployment_proven)
        self.assertTrue(package.receipt.source_revision.startswith("kdv-bmf-snapshot-sha256:"))
        reader=restore_continuity_snapshot(
            package.snapshot.archive_bytes,
            expected_archive_sha256=package.snapshot.archive_sha256,
        )
        self.assertTrue(reader.restore_receipt.projection_replay_equal)
        self.assertTrue(reader.restore_receipt.as_of_only)
        self.assertFalse(reader.restore_receipt.present_tense_current_claim_allowed)

    def test_capture_is_order_independent_for_same_provider_set(self):
        a=self.capture()
        b=capture_provider_bmf_rows(
            tuple(reversed(rows())),
            source_ref="KDV:test:BMF_SHADOW_EVENTS!A1:U3",
            observed_at="2026-09-19T02:05:00+02:00",
            schema_sha256=schema_digest(),
            provider_read_verified_at_capture=True,
        )
        self.assertEqual(a.receipt.rowset_sha256,b.receipt.rowset_sha256)
        self.assertEqual(a.snapshot.archive_sha256,b.snapshot.archive_sha256)

    def test_unverified_provider_rows_are_rejected(self):
        with self.assertRaisesRegex(ValueError,"REQUIRES_VERIFIED_PROVIDER_READ"):
            capture_provider_bmf_rows(
                rows(),
                source_ref="KDV:test",
                observed_at="2026-09-19T02:05:00+02:00",
                schema_sha256=schema_digest(),
                provider_read_verified_at_capture=False,
            )

    def test_missing_live_field_fails_closed(self):
        bad=dict(rows()[0]); bad.pop("provider_persisted_at_sast")
        with self.assertRaisesRegex(ValueError,"BMF_FIELDS_MISSING"):
            capture_provider_bmf_rows(
                (bad,),
                source_ref="KDV:test",
                observed_at="2026-09-19T02:05:00+02:00",
                schema_sha256=schema_digest(),
                provider_read_verified_at_capture=True,
            )

    def test_invalid_provider_event_hash_fails_closed(self):
        bad=dict(rows()[0]); bad["event_sha256"]="not-a-sha"
        with self.assertRaisesRegex(ValueError,"EVENT_SHA256_INVALID"):
            capture_provider_bmf_rows(
                (bad,),
                source_ref="KDV:test",
                observed_at="2026-09-19T02:05:00+02:00",
                schema_sha256=schema_digest(),
                provider_read_verified_at_capture=True,
            )

    def test_duplicate_event_id_fails_closed(self):
        a=dict(rows()[0]); b=dict(rows()[1]); b["event_id"]=a["event_id"]
        with self.assertRaisesRegex(ValueError,"DUPLICATE_EVENT_ID"):
            capture_provider_bmf_rows(
                (a,b),
                source_ref="KDV:test",
                observed_at="2026-09-19T02:05:00+02:00",
                schema_sha256=schema_digest(),
                provider_read_verified_at_capture=True,
            )

    def test_governance_confirms_composition_not_new_runtime_or_store(self):
        g=json.loads((ROOT/"governance/kdv_read_continuity_capture_v1.json").read_text())
        self.assertFalse(g["provider_transport_implemented_here"])
        self.assertFalse(g["provider_credentials_accepted_here"])
        self.assertFalse(g["new_store_created"])
        self.assertFalse(g["new_writer_created"])
        self.assertTrue(g["live_shape_canary"]["shape_matches_fkcm_from_bmf_row"])
        self.assertFalse(g["authority"]["canonical_authority"])
        self.assertFalse(g["authority"]["write_authority"])
        self.assertFalse(g["authority"]["provider_effect_authorized"])

if __name__=="__main__":
    unittest.main()
