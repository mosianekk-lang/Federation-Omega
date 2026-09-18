from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import unittest
from unittest.mock import patch

from respawn.work_plane_cloud_service_v1 import ALLOWED_ACTIONS, contract, execute_payload


@dataclass
class FakeReceipt:
    adapter_version: str = "1.1.0"
    operation: str = "PROJECTION"
    mission_id: str = "M"
    prior_generation: int = 4
    committed_generation: int = 4
    bundle_sha256: str = "a" * 64
    result: dict = None
    provider_effect_authorized: bool = False
    receipt_sha256: str = "b" * 64

    def __post_init__(self):
        if self.result is None:
            self.result = {"state": "CHECKPOINTED", "fence": 2}


class FakeRuntime:
    def __init__(self): self.calls=[]
    def execute(self, **kw):
        self.calls.append(kw)
        r=FakeReceipt(operation=kw["operation"],mission_id=kw["mission_id"])
        return r


class WorkPlaneCloudServiceTests(unittest.TestCase):
    def test_contract_is_private_and_shell_free(self):
        c=contract()
        self.assertTrue(c["private_cloud_run_iam_required"])
        self.assertFalse(c["arbitrary_shell"])
        self.assertFalse(c["inline_python"])
        self.assertFalse(c["public_ingress_authorized"])
        self.assertFalse(c["traffic_promotion_authorized"])

    def test_exact_action_surface(self):
        self.assertIn("PROJECTION",ALLOWED_ACTIONS)
        self.assertIn("RECOVER_ORPHAN",ALLOWED_ACTIONS)
        self.assertNotIn("SHELL",ALLOWED_ACTIONS)
        self.assertNotIn("PYTHON",ALLOWED_ACTIONS)
        self.assertNotIn("DELETE",ALLOWED_ACTIONS)

    def test_execute_projection_maps_to_admitted_runtime(self):
        fake=FakeRuntime()
        out=execute_payload({"action":"PROJECTION","mission_id":"M","actor":"reader"},fake)
        self.assertTrue(out["ok"])
        self.assertEqual(out["operation"],"PROJECTION")
        self.assertEqual(fake.calls[0]["operation"],"PROJECTION")
        self.assertFalse(out["provider_effect_authorized"])

    def test_execute_takeover_preserves_readback_and_ttl(self):
        fake=FakeRuntime()
        execute_payload({"action":"RECOVER_ORPHAN","mission_id":"M","actor":"B","readback":"ABSENT","ttl_seconds":33},fake)
        call=fake.calls[0]
        self.assertEqual(call["readback"],"ABSENT")
        self.assertEqual(call["ttl_seconds"],33)

    def test_missing_mission_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"MISSION_ID_REQUIRED"):
            execute_payload({"action":"PROJECTION"},FakeRuntime())

    def test_unknown_action_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"ACTION_NOT_ALLOWED"):
            execute_payload({"action":"SHELL","mission_id":"M"},FakeRuntime())

    def test_dockerfile_runs_nonroot_and_pins_google_auth(self):
        root=Path(__file__).resolve().parents[1]
        text=(root/"deployments/work_plane/Dockerfile").read_text()
        self.assertIn("USER 65532:65532",text)
        self.assertIn("google-auth==2.40.3",text)
        self.assertIn("requests==2.32.5",text)
        self.assertNotIn("latest",text.lower())

    def test_governance_keeps_maturity_separate(self):
        root=Path(__file__).resolve().parents[1]
        g=json.loads((root/"governance/fuse_work_plane_cloud_service_v1.json").read_text())
        self.assertFalse(g["public_invocation"])
        self.assertFalse(g["provider_effect_authorized_by_source"])
        self.assertFalse(g["proof_boundary"]["provider_canary_proves_24x7"])
        self.assertEqual(g["state_bucket"],"fo-control-plane-sov-hybrid-suite")

    def test_workflow_is_owner_scoped_keyless_and_no_iam_widening(self):
        root=Path(__file__).resolve().parents[1]
        text=(root/".github/workflows/work-plane-private-gcp-canary-v1.yml").read_text()
        self.assertIn("github.event.issue.author_association == 'OWNER'",text)
        self.assertIn("google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093",text)
        self.assertIn("--no-allow-unauthenticated",text)
        self.assertIn("--no-traffic",text)
        self.assertNotIn("gcloud projects add-iam-policy-binding",text)
        self.assertNotIn("gcloud run services add-iam-policy-binding",text)
        self.assertNotIn("gcloud services enable",text)
        self.assertNotIn("gcloud secrets versions access",text)

    def test_workflow_proves_cross_revision_and_stale_fence(self):
        root=Path(__file__).resolve().parents[1]
        text=(root/".github/workflows/work-plane-private-gcp-canary-v1.yml").read_text()
        for marker in ("cross_revision_projection_verified","stale_actor_rejected","generation_monotonic","runtime_service_account"):
            self.assertIn(marker,text)


if __name__ == "__main__":
    unittest.main()
