import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MCP = ROOT / "services" / "federation-omega-gcp-admin-mcp"
JARVIS = ROOT / "services" / "jarvis-ultimate"
MANIFEST_PATH = ROOT / "governance" / "jarvis_release_train_integration_20260818.json"
ADAPTER_PATH = JARVIS / "jarvis" / "resources" / "gcp_admin_mcp_adapter_v1.json"
CORE_MANIFEST_PATH = ROOT / "PHOENIX_CORE_MANIFEST.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class JarvisReleaseTrainIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = read_json(MANIFEST_PATH)
        cls.adapter = read_json(ADAPTER_PATH)
        cls.mcp_contract = read_json(MCP / "BUILD_CONTRACT.json")
        cls.jarvis_contract = read_json(JARVIS / "BUILD_CONTRACT.json")
        cls.core_manifest = (
            read_json(CORE_MANIFEST_PATH) if CORE_MANIFEST_PATH.is_file() else None
        )
        cls.core_exclusions = (
            {
                item["path"]: item["reason"]
                for item in cls.core_manifest.get("excluded", [])
            }
            if cls.core_manifest
            else {}
        )

    def test_integration_manifest_is_non_mergeable_by_policy(self):
        self.assertEqual(
            self.manifest["schema"], "JARVIS_RELEASE_TRAIN_INTEGRATION_V1"
        )
        self.assertFalse(
            self.manifest["releasePolicy"]["integrationCarrierMergeAllowed"]
        )
        self.assertFalse(
            self.manifest["releasePolicy"]["integrationCarrierAutoMergeAllowed"]
        )
        self.assertFalse(self.manifest["releasePolicy"]["productionClaimAllowed"])
        self.assertEqual(
            self.manifest["releasePolicy"]["requiredRealReleaseOrder"],
            [534, 546, 548, 549],
        )
        self.assertTrue(
            self.manifest["releasePolicy"]["postMergeAdapterRebindRequired"]
        )

    def test_exact_component_identities_are_bound(self):
        components = self.manifest["components"]
        self.assertEqual(
            components["gcpAdminMcp"]["head"],
            "bec80d87c5bb05e8a6a1a4453c71aef3d1d02ad6",
        )
        self.assertEqual(
            components["gcpAdminMcp"]["serviceTree"],
            "c72557e541a1be9c1b5205c79f5a18b9f3caf473",
        )
        self.assertEqual(
            components["jarvisFoundation"]["head"],
            "9b075fc64393e3b780a863860d59a082fe41ceb0",
        )
        self.assertEqual(
            components["t20Overlay"]["head"],
            "b6d95e15fd1b63fecabb63d00fd3565989fcfaf0",
        )
        self.assertEqual(
            components["disabledAdapter"]["head"],
            "72e6fa48bc9f4d33ecbfb3976bfce181c07f85c1",
        )

    def test_mcp_release_manifest_matches_every_listed_file(self):
        release_manifest = MCP / "RELEASE_MANIFEST.sha256"
        release_manifest_path = (
            "services/federation-omega-gcp-admin-mcp/RELEASE_MANIFEST.sha256"
        )
        if self.core_manifest:
            self.assertFalse(release_manifest.exists())
            self.assertEqual(
                "UNAPPROVED_EXTENSION",
                self.core_exclusions.get(release_manifest_path),
            )
            self.assertEqual(
                0, self.core_manifest["invariants"]["workflow_count"]
            )
            return

        lines = release_manifest.read_text(encoding="utf-8").splitlines()
        checked = 0
        for line in lines:
            if not line.strip():
                continue
            expected, relative = line.split(maxsplit=1)
            relative = relative.strip()
            if relative.startswith("./"):
                relative = relative[2:]
            target = MCP / relative
            self.assertTrue(target.is_file(), relative)
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            self.assertEqual(actual, expected, relative)
            checked += 1
        self.assertEqual(checked, 32)

    def test_exact_mcp_tool_surface_matches_adapter(self):
        source = (MCP / "src" / "toolNames.ts").read_text(encoding="utf-8")
        block = source.split("} as const;", 1)[0]
        names = set(re.findall(r':\s*"([a-z][a-z0-9_]+)"', block))
        self.assertEqual(names, set(self.adapter["exactToolNames"]))
        self.assertEqual(len(names), 17)
        self.assertIn('export const SERVER_VERSION = "0.2.2";', source)
        self.assertIn('proofBoundary: "transport_liveness_only"', source)

    def test_adapter_binds_exact_sources_and_remains_disabled(self):
        bindings = self.adapter["sourceBindings"]
        self.assertEqual(
            bindings["mcpHead"],
            self.manifest["components"]["gcpAdminMcp"]["head"],
        )
        self.assertEqual(
            bindings["mcpServiceTree"],
            self.manifest["components"]["gcpAdminMcp"]["serviceTree"],
        )
        self.assertEqual(
            bindings["jarvisBaseHead"],
            self.manifest["components"]["t20Overlay"]["head"],
        )
        self.assertEqual(
            self.adapter["adapterState"], "SOURCE_READY_PROVIDER_DISABLED"
        )
        for lane in self.adapter["authorityLanes"].values():
            self.assertFalse(lane["enabled"])
        self.assertFalse(
            self.manifest["truthBoundary"]["providerExecutionAllowed"]
        )

    def test_source_contracts_do_not_claim_deployment_or_production_proof(self):
        self.assertEqual(
            self.mcp_contract["mission"]["maturity"], "PROD_FOUNDATION"
        )
        self.assertFalse(self.mcp_contract["states"]["deployed"])
        self.assertFalse(self.mcp_contract["states"]["proven"])
        self.assertEqual(self.jarvis_contract["release_version"], "1.4.0")
        self.assertEqual(
            self.jarvis_contract["overlay_version"],
            "T20-AO-OMEGA-SCIENTIST-1.1",
        )
        self.assertFalse(self.jarvis_contract["states"]["ready"])
        self.assertFalse(self.jarvis_contract["states"]["deployed"])
        self.assertFalse(self.jarvis_contract["states"]["proven"])

    def test_nested_service_workflows_do_not_expand_root_actions_surface(self):
        release = (
            MCP / ".github" / "workflows" / "release-gcp-admin-mcp-v022.yml"
        )
        verify = (
            MCP / ".github" / "workflows" / "verify-gcp-admin-mcp-v022.yml"
        )
        release_path = (
            "services/federation-omega-gcp-admin-mcp/.github/workflows/"
            "release-gcp-admin-mcp-v022.yml"
        )
        verify_path = (
            "services/federation-omega-gcp-admin-mcp/.github/workflows/"
            "verify-gcp-admin-mcp-v022.yml"
        )

        if self.core_manifest:
            self.assertFalse(release.exists())
            self.assertFalse(verify.exists())
            self.assertEqual(
                "GITHUB_WORKFLOW_NOT_CORE_SOURCE",
                self.core_exclusions.get(release_path),
            )
            self.assertEqual(
                "GITHUB_WORKFLOW_NOT_CORE_SOURCE",
                self.core_exclusions.get(verify_path),
            )
        else:
            self.assertTrue(release.is_file())
            self.assertTrue(verify.is_file())

        self.assertFalse(
            (
                ROOT
                / ".github"
                / "workflows"
                / "release-gcp-admin-mcp-v022.yml"
            ).exists()
        )
        self.assertFalse(
            (
                ROOT
                / ".github"
                / "workflows"
                / "verify-gcp-admin-mcp-v022.yml"
            ).exists()
        )

    def test_no_external_effect_is_authorized_by_integration_carrier(self):
        boundary = self.manifest["truthBoundary"]
        for key in (
            "providerExecutionAllowed",
            "credentialDiscoveryAllowed",
            "iamMutationAllowed",
            "cloudDeploymentAllowed",
            "trafficMutationAllowed",
            "promotionAllowed",
            "emailActionsAllowed",
            "chatOrWorkstreamRestoreAllowed",
        ):
            self.assertFalse(boundary[key], key)


if __name__ == "__main__":
    unittest.main()
