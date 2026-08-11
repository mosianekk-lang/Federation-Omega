from __future__ import annotations

import copy
import unittest

from federation_consolidation.awareness_opportunity_foundry import (
    FoundryError,
    classify_gmail_subject,
    credential_preflight,
    detect_drift,
    parse_credentials,
    parse_surfaces,
    route_mission,
    run_foundry,
    verify_public_private_binding,
)

MAIN = "1032b6131580225083346496f3fa1008feaf7a54"
PRIVATE_HASH = "8961706e5d0e9d1e379ce24b89bb7cf8546cf126adc88e1c93c152d2a979f438"
PUBLIC = {
    "schema": "FEDOMEGA-SURFACE-AWARENESS-V1",
    "owner": "Kim Kagiso Mosiane",
    "startup_block": "NCB-002",
    "private_manifest": {
        "version": "1.0.0",
        "logical_sha256": PRIVATE_HASH,
    },
}
PRIVATE = {
    "schema": "FEDOMEGA-PRIVATE-SURFACE-AWARENESS-1",
    "version": "1.0.0",
    "owner": "Kim Kagiso Mosiane",
    "logical_sha256": PRIVATE_HASH,
    "credential_value_recorded": False,
}
SURFACES = [
    [
        "Surface_ID",
        "Name",
        "Class",
        "Canonical_Alias",
        "Provider_or_Connector",
        "Current_State",
        "Proven_Capability",
        "Authority_Ceiling",
        "Freshness_Rule",
        "Runtime_Readback",
        "Private_Pointer_Class",
        "Notes",
    ],
    [
        "SURF-002",
        "Federation Omega GitHub repository",
        "SOURCE_AND_AUTOMATION",
        "FEDERATION_OMEGA_CONTROL_PLANE",
        "GitHub",
        "LIVE_VERIFIED_EXISTING_REPO_READ_WRITE",
        "Source and PRs",
        "A1",
        "Read main",
        "REQUIRED",
        "PUBLIC_SAFE_ALIAS",
        "main=7065290d98fa384858b8d609df4960a35ece563b",
    ],
    [
        "SURF-004",
        "Google Drive",
        "CANONICAL_STORE",
        "GOOGLE_WORKSPACE_CANONICAL_STORE",
        "Google Drive",
        "LIVE_VERIFIED_CANONICAL_WRITE_READBACK",
        "Canonical writes",
        "A1",
        "Revalidate",
        "REQUIRED",
        "PRIVATE",
        "",
    ],
    [
        "SURF-005",
        "Gmail",
        "COMMUNICATION",
        "GMAIL_SOURCE_CORPUS",
        "Gmail",
        "LIVE_VERIFIED_READ_SEARCH_SOURCE_EVIDENCE",
        "Search/read",
        "A1_READ",
        "Mission scoped",
        "ON_DEMAND",
        "PRIVATE",
        "",
    ],
    [
        "SURF-014",
        "Google Cloud",
        "CLOUD_RUNTIME",
        "GOOGLE_CLOUD_EXECUTION_PLANE",
        "Google Cloud",
        "SOURCE_CONTRACT_PRESENT_PROVIDER_INVENTORY_UNVERIFIED",
        "Cloud contracts",
        "A1_ROUTE_SPECIFIC",
        "Readback",
        "ON_DEMAND",
        "PRIVATE",
        "",
    ],
    [
        "SURF-017",
        "Microsoft Dataverse",
        "DATA_PLATFORM",
        "MICROSOFT_DATAVERSE_PARITY_ROUTE",
        "Microsoft Dataverse",
        "ADAPTER_SOURCE_PRESENT_PROVIDER_BINDING_UNVERIFIED",
        "Adapter source",
        "A1_ROUTE_SPECIFIC",
        "Readback",
        "ON_DEMAND",
        "PRIVATE",
        "",
    ],
]
CREDENTIALS = [
    [
        "Handle_ID",
        "Surface",
        "Reference_Name",
        "Storage_Location_Class",
        "Current_State",
        "Scope",
        "Raw_Value_Stored",
        "Runtime_Validation",
        "Rotation_or_Expiry",
        "Notes",
    ],
    [
        "CR-001",
        "Google Workspace",
        "GOOGLE_WORKSPACE_CONNECTOR_SESSION",
        "Platform",
        "LIVE_FOR_DRIVE_AND_GMAIL",
        "read/write",
        "FALSE",
        "revalidate",
        "session",
        "",
    ],
    [
        "CR-003",
        "GitHub mutation",
        "GH_ADMIN_TOKEN",
        "Private process",
        "NOT_PRESENT_IN_CHAT",
        "provider mutation",
        "FALSE",
        "probe",
        "short-lived",
        "",
    ],
]
AUTOMATION = [
    [
        "Asset_ID",
        "Alias",
        "Title",
        "Provider",
        "Exact_Private_Pointer",
        "Role",
        "Current_State",
        "Load_Order",
        "Readback_Evidence",
        "Secrets_Allowed",
        "Notes",
    ],
    [
        "AUTO-012",
        "FEDERATION_OMEGA_CONTROL_PLANE",
        "repo",
        "GitHub",
        "7065290d98fa384858b8d609df4960a35ece563b",
        "source",
        "LIVE_VERIFIED",
        "1",
        "old main",
        "FALSE",
        "",
    ],
]


class FoundryTests(unittest.TestCase):
    def test_binding_verified(self) -> None:
        self.assertEqual(
            "VERIFIED", verify_public_private_binding(PUBLIC, PRIVATE)["status"]
        )

    def test_binding_hash_mismatch_blocks(self) -> None:
        private = dict(PRIVATE, logical_sha256="0" * 64)
        self.assertEqual(
            "BLOCKED", verify_public_private_binding(PUBLIC, private)["status"]
        )

    def test_secret_shaped_value_rejected(self) -> None:
        private = copy.deepcopy(PRIVATE)
        private["note"] = "github_pat_" + "A" * 30
        with self.assertRaises(FoundryError):
            verify_public_private_binding(PUBLIC, private)

    def test_stale_main_detected_twice(self) -> None:
        drifts = detect_drift(parse_surfaces(SURFACES), AUTOMATION, MAIN)
        self.assertEqual(2, len(drifts))
        self.assertTrue(all(item["observed"] == MAIN for item in drifts))

    def test_credential_preflight_never_allows_effectful_use(self) -> None:
        results = credential_preflight(parse_credentials(CREDENTIALS))
        self.assertTrue(
            all(item["effectful_use_allowed"] is False for item in results)
        )
        self.assertEqual("READY_READ_SCOPED", results[0]["status"])
        self.assertEqual("REVALIDATION_REQUIRED", results[1]["status"])

    def test_raw_credential_flag_rejected(self) -> None:
        table = copy.deepcopy(CREDENTIALS)
        table[1][6] = "TRUE"
        with self.assertRaises(FoundryError):
            credential_preflight(parse_credentials(table))

    def test_gmail_ci_noise_separated(self) -> None:
        self.assertEqual(
            "CI_TELEMETRY",
            classify_gmail_subject(
                "Run failed: Federation Omega Airlock",
                "notifications@github.com",
            ),
        )
        self.assertEqual(
            "CONTINUITY_SOURCE",
            classify_gmail_subject(
                "Federation Omega Formation Engine continuation", "Kim"
            ),
        )

    def test_router_prefers_live_drive_for_drive_mission(self) -> None:
        routes = route_mission(
            parse_surfaces(SURFACES), "update canonical Drive manifest"
        )
        self.assertEqual("GOOGLE_WORKSPACE_CANONICAL_STORE", routes[0]["alias"])
        self.assertGreater(routes[0]["score"], routes[-1]["score"])

    def test_foundry_builds_internal_and_provider_records(self) -> None:
        result = run_foundry(
            public=PUBLIC,
            private=PRIVATE,
            surfaces_table=SURFACES,
            credentials_table=CREDENTIALS,
            automation_table=AUTOMATION,
            observed_main=MAIN,
            mission="restore federation awareness",
            gmail_messages=[
                {
                    "subject": "Run failed: Federation Omega Airlock",
                    "sender": "notifications@github.com",
                }
            ],
        )
        self.assertEqual("VERIFIED_LOCAL_BUILD_SET", result["status"])
        self.assertGreaterEqual(len(result["internal_build_ids"]), 1)
        self.assertGreaterEqual(len(result["provider_gated_build_ids"]), 2)
        self.assertEqual(
            "CI_TELEMETRY", result["gmail_signal_map"][0]["classification"]
        )
        self.assertFalse(result["provider_mutation_performed"])

    def test_node_packet_includes_ao_cra_and_foundry(self) -> None:
        result = run_foundry(
            public=PUBLIC,
            private=PRIVATE,
            surfaces_table=SURFACES,
            credentials_table=CREDENTIALS,
            automation_table=AUTOMATION,
            observed_main=MAIN,
            mission="restore federation awareness",
        )
        packet = result["node_packet"]
        self.assertEqual("NCB-002", packet["startup_block"])
        self.assertIn(
            "governance/ao_cra_federation_inheritance_v1.json",
            packet["required_contracts"],
        )
        self.assertIn(
            "governance/federation_awareness_opportunity_foundry_v1.json",
            packet["required_contracts"],
        )
        self.assertEqual("REQUIRED_ON_BOUNDARY", packet["ao_cra"])

    def test_receipt_is_deterministic_for_same_input(self) -> None:
        first = run_foundry(
            public=PUBLIC,
            private=PRIVATE,
            surfaces_table=SURFACES,
            credentials_table=CREDENTIALS,
            automation_table=AUTOMATION,
            observed_main=MAIN,
            mission="restore federation awareness",
        )
        second = run_foundry(
            public=PUBLIC,
            private=PRIVATE,
            surfaces_table=SURFACES,
            credentials_table=CREDENTIALS,
            automation_table=AUTOMATION,
            observed_main=MAIN,
            mission="restore federation awareness",
        )
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])


if __name__ == "__main__":
    unittest.main()
