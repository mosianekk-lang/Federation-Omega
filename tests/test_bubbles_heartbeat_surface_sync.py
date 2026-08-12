import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "evidenceops" / "capability_heartbeat" / "surface_registry.json"


class BubblesHeartbeatSurfaceSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.surfaces = {item["surface_id"]: item for item in cls.registry["surfaces"]}

    def test_registry_version_is_current(self):
        self.assertEqual(self.registry["schema"], "EVIDENCEOPS-HEARTBEAT-SURFACES-1")
        self.assertGreaterEqual(self.registry["registry_version"], 2)

    def test_github_uses_bubbles_and_admitted_pointer(self):
        github = self.surfaces["github"]
        self.assertEqual(github["adapter_ref"], "bubbles-command-bus")
        routes = {item["route"] for item in github["workaround_routes"]}
        self.assertIn("BUBBLES_COMMAND_BUS", routes)
        self.assertIn("KDV_LAST_ADMITTED_COMMIT_POINTER", routes)

    def test_apps_script_does_not_claim_provider_deployment(self):
        apps = self.surfaces["apps-script"]
        self.assertEqual(apps["heartbeat_state"], "CONTROL_PLANE_REACHABLE_PROVIDER_DEPLOYMENT_HELD")
        self.assertEqual(apps["adapter_ref"], "bubbles-private-kdv-queue")
        route = apps["workaround_routes"][0]
        self.assertEqual(route["route"], "FO_GAS_V23_HARDENED_PROVIDER_DEPLOYMENT")
        self.assertEqual(route["proof_state"], "SOURCE_PRESENT")
        self.assertTrue(route["effectful"])

    def test_google_cloud_remains_provider_authority_held(self):
        cloud = self.surfaces["google-cloud"]
        self.assertEqual(cloud["heartbeat_state"], "PROVIDER_AUTHORITY_REQUIRED")
        route = cloud["workaround_routes"][0]
        self.assertEqual(route["route"], "FEDOMEGA_WIF_LEAST_PRIVILEGE_RECOVERY")
        self.assertTrue(route["effectful"])
        self.assertIn("FEDOMEGA-WIF-CLOUD-VERIFIED", route["next_action"])

    def test_ai_studio_remains_control_plane_only(self):
        ai = self.surfaces["google-ai-studio"]
        self.assertEqual(ai["heartbeat_state"], "CONTROL_PLANE_ONLY")
        self.assertFalse(ai["workaround_routes"][0]["effectful"])

    def test_federation_omega_command_bus_is_internal_not_provider_write(self):
        federation = self.surfaces["federation-omega"]
        self.assertEqual(federation["adapter_ref"], "bubbles-command-bus")
        route = federation["workaround_routes"][0]
        self.assertFalse(route["effectful"])
        self.assertIn("privileged provider execution separate", route["next_action"])


if __name__ == "__main__":
    unittest.main()
