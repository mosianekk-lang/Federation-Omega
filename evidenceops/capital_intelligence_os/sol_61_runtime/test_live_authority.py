from __future__ import annotations

import json
import unittest
from pathlib import Path

from live_authority import CanonicalLiveAuthority


class CanonicalLiveAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        path = Path(__file__).with_name("canonical_live_authority_manifest.json")
        self.manifest = json.loads(path.read_text(encoding="utf-8"))

    def test_canonical_manifest_passes(self) -> None:
        receipt = CanonicalLiveAuthority(self.manifest).validate()
        self.assertEqual(receipt["status"], "CANONICAL_LIVE_AUTHORITY_MANIFEST_VERIFIED")
        self.assertTrue(all(receipt["gates"].values()))

    def test_cloud_run_cannot_be_promoted_without_receipts(self) -> None:
        broken = json.loads(json.dumps(self.manifest))
        broken["cloud_run"]["promotion_receipts"] = ["request_id"]
        receipt = CanonicalLiveAuthority(broken).validate()
        self.assertFalse(receipt["gates"]["cloud_run_receipts_complete"])

    def test_apps_script_service_account_only_route_is_rejected(self) -> None:
        broken = json.loads(json.dumps(self.manifest))
        broken["apps_script"]["service_accounts_sufficient"] = True
        receipt = CanonicalLiveAuthority(broken).validate()
        self.assertFalse(receipt["gates"]["apps_script_service_account_rejected"])

    def test_pending_queue_is_not_live_authority(self) -> None:
        broken = json.loads(json.dumps(self.manifest))
        broken["supporting_routes"]["fo_gas"]["status"] = "VERIFIED_LIVE"
        receipt = CanonicalLiveAuthority(broken).validate()
        self.assertFalse(receipt["gates"]["queue_routes_not_promoted"])


if __name__ == "__main__":
    unittest.main()
