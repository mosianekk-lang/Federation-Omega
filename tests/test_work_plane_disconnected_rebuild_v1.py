from __future__ import annotations

from pathlib import Path
import json
import subprocess
import unittest

from federation.work_plane_disconnected_rebuild_v1 import (
    TARGET_PATHS,
    build_source_snapshot,
    collect_source_files,
    execute_disconnected_rebuild,
)


ROOT=Path(__file__).resolve().parents[1]


def current_head() -> str:
    p=subprocess.run(
        ["git","rev-parse","HEAD"],
        cwd=ROOT,text=True,capture_output=True,check=True
    )
    return p.stdout.strip()


class WorkPlaneDisconnectedRebuildV1Tests(unittest.TestCase):
    def test_target_slice_exists_and_is_small(self):
        records=collect_source_files(ROOT)
        self.assertEqual(len(records),len(TARGET_PATHS))
        self.assertEqual({x.path for x in records},set(TARGET_PATHS))
        self.assertTrue(all(len(x.sha256)==64 and x.size_bytes>0 for x in records))

    def test_snapshot_is_deterministic_and_provider_effect_free(self):
        head=current_head()
        a=build_source_snapshot(ROOT,source_head_sha=head,created_at="2026-09-19T00:00:00Z")
        b=build_source_snapshot(ROOT,source_head_sha=head,created_at="2026-09-19T00:00:00Z")
        self.assertEqual(a.archive_sha256,b.archive_sha256)
        self.assertEqual(a.manifest_sha256,b.manifest_sha256)
        self.assertFalse(a.manifest["truth_boundary"]["provider_upload_performed"])
        self.assertFalse(a.manifest["truth_boundary"]["external_effect"])

    def test_real_work_plane_slice_rebuilds_offline_in_fresh_workspace(self):
        receipt=execute_disconnected_rebuild(
            ROOT,
            source_head_sha=current_head(),
            created_at="2026-09-19T00:00:00Z",
        )
        self.assertTrue(receipt.archive_verified)
        self.assertTrue(receipt.first_restore_exact)
        self.assertTrue(receipt.second_restore_exact)
        self.assertTrue(receipt.network_guard_verified)
        self.assertEqual(receipt.compile_evidence.returncode,0)
        self.assertEqual(receipt.test_evidence.returncode,0)
        self.assertTrue(receipt.rollback_verified)
        self.assertTrue(receipt.disconnected_rebuild_proven)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.provider_runtime_proven)
        self.assertFalse(receipt.gcs_live_proven)
        self.assertFalse(receipt.cloud_run_proven)
        self.assertFalse(receipt.persistent_24x7_proven)
        self.assertFalse(receipt.cross_host_dr_proven)
        self.assertFalse(receipt.owner_value_proven)

    def test_governance_does_not_sovereign_wash_google_provider(self):
        g=json.loads((ROOT/"governance/work_plane_disconnected_rebuild_v1.json").read_text())
        boundary=g["claim_boundary"]
        self.assertTrue(boundary["disconnected_work_plane_core_rebuild_may_be_proven"])
        for key in (
            "gcs_live_proven_by_this_court",
            "cloud_run_proven_by_this_court",
            "google_identity_proven_by_this_court",
            "persistent_24x7_proven_by_this_court",
            "cross_host_dr_proven_by_this_court",
            "owner_value_proven_by_this_court",
        ):
            self.assertFalse(boundary[key])

if __name__=="__main__":
    unittest.main()
