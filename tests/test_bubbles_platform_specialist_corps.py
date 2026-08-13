from __future__ import annotations

import unittest

from bubbles.platform_specialist_corps import (
    CapabilityRequest,
    PlatformCapabilitySnapshot,
    SurfaceState,
    build_default_corps,
)


class PlatformSpecialistCorpsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.corps = build_default_corps()

    def test_core_corps_has_distinct_platform_roles(self) -> None:
        required = {
            "ChatGPT",
            "Gmail",
            "Google Drive",
            "Google Calendar",
            "Google Contacts",
            "Canva",
            "Adobe",
            "GitHub",
            "OpenAI Platform",
            "Outlook Email",
            "Outlook Calendar",
            "Booking.com",
            "Google Apps Script",
            "Google Cloud",
            "Google AI Studio",
            "Microsoft Teams",
            "Microsoft SharePoint",
            "Microsoft Dataverse",
            "Power Automate",
        }
        self.assertTrue(required.issubset(self.corps.roles))
        role_ids = [role.role_id for role in self.corps.roles.values()]
        self.assertEqual(len(role_ids), len(set(role_ids)))

    def test_verified_bidirectional_surface_is_selected(self) -> None:
        request = CapabilityRequest("update a design", frozenset({"design", "visual"}))
        snapshots = {
            "Canva": PlatformCapabilitySnapshot(
                platform="Canva",
                state=SurfaceState.VERIFIED_OPERATIONAL,
                connector_connected=True,
                provider_identity_verified=True,
                read_verified=True,
                write_verified=True,
                semantic_readback_verified=True,
                native_ai_callable=True,
                native_ai_readback_verified=True,
            )
        }
        decisions = self.corps.route(request, snapshots)
        canva = next(item for item in decisions if item.platform == "Canva")
        self.assertTrue(canva.selected)
        self.assertEqual("BIDIRECTIONAL_VERIFIED", canva.mode)
        self.assertFalse(canva.ao_cra_builds)

    def test_native_ai_gap_becomes_engineering_build_not_fake_access(self) -> None:
        request = CapabilityRequest(
            "run a model diversity experiment",
            frozenset({"ai", "model", "experimentation"}),
            native_ai_preferred=True,
        )
        snapshots = {
            "Google AI Studio": PlatformCapabilitySnapshot(
                platform="Google AI Studio",
                state=SurfaceState.CONTROL_PLANE_ONLY,
                connector_connected=False,
                provider_identity_verified=False,
                read_verified=False,
                write_verified=False,
                semantic_readback_verified=False,
                native_ai_callable=False,
                native_ai_readback_verified=False,
                known_gaps=("NO_DIRECT_CONNECTOR",),
            )
        }
        decisions = self.corps.route(request, snapshots)
        studio = next(item for item in decisions if item.platform == "Google AI Studio")
        self.assertEqual("CONTROL_PLANE_ONLY", studio.mode)
        self.assertIn("AO-CRA:PLATFORM:Google AI Studio:NATIVE_AI_BRIDGE", studio.ao_cra_builds)
        self.assertIn("AO-CRA:PLATFORM:Google AI Studio:FULL_BIDIRECTIONAL_PROOF", studio.ao_cra_builds)

    def test_consequential_request_requires_owner_gate(self) -> None:
        request = CapabilityRequest(
            "send external email",
            frozenset({"email", "communications"}),
            consequential=True,
        )
        snapshots = {
            "Gmail": PlatformCapabilitySnapshot(
                platform="Gmail",
                state=SurfaceState.VERIFIED_OPERATIONAL,
                connector_connected=True,
                provider_identity_verified=True,
                read_verified=True,
                write_verified=True,
                semantic_readback_verified=True,
                native_ai_callable=False,
                native_ai_readback_verified=False,
            )
        }
        gmail = next(item for item in self.corps.route(request, snapshots) if item.platform == "Gmail")
        self.assertFalse(gmail.selected)
        self.assertTrue(gmail.owner_gate)
        self.assertEqual("OWNER_GATE_REQUIRED", gmail.reason)

    def test_missing_snapshot_is_not_promoted(self) -> None:
        request = CapabilityRequest("inspect structured data", frozenset({"database", "structured_data"}))
        dataverse = next(
            item for item in self.corps.route(request, {}) if item.platform == "Microsoft Dataverse"
        )
        self.assertFalse(dataverse.selected)
        self.assertEqual("UNVERIFIED", dataverse.mode)
        self.assertEqual(
            ("AO-CRA:PLATFORM:Microsoft Dataverse:CAPABILITY_SNAPSHOT",),
            dataverse.ao_cra_builds,
        )


if __name__ == "__main__":
    unittest.main()
