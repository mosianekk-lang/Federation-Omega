from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace

from live_provider_expansion import LiveProviderExpansionFabric, ProviderObservation, digest

NOW = "2026-08-04T00:10:00Z"
GENERATED = "2026-08-03T22:00:00Z"


def register() -> dict:
    return {
        "programme": "SOL-6.1-LIVE-ADAPTER-CERTIFICATION",
        "generated_at": GENERATED,
        "status": "REVERSIBLE_PROVIDER_ADAPTERS_CERTIFIED",
        "providers": {
            "github": {"status": "VERIFIED_OPERATIONAL", "scope": ["create_file", "readback", "delete_file"]},
            "google_drive": {"status": "VERIFIED_OPERATIONAL", "scope": ["create_native_doc", "fetch_readback", "permanent_delete"]},
            "gmail_draft": {"status": "VERIFIED_OPERATIONAL", "scope": ["create_draft", "list_readback", "trash_message"], "send_performed": False},
            "google_calendar": {"status": "VERIFIED_OPERATIONAL", "scope": ["create_private_event", "provider_readback", "delete_event"]},
            "outlook_draft": {"status": "VERIFIED_OPERATIONAL", "scope": ["create_draft", "provider_readback", "move_to_deleted_items"], "send_performed": False},
            "canva_transaction": {"status": "VERIFIED_OPERATIONAL", "scope": ["start_transaction", "temporary_title_edit", "cancel_transaction"], "persistent_change": False},
        },
        "truth_boundary": {
            "gmail_send_certified": False,
            "outlook_send_certified": False,
            "apps_script_source_mutation_certified": False,
            "cloud_run_invocation_certified": False,
            "canva_permanent_commit_certified": False,
        },
    }


def cloud_observation(observed_at: str = "2026-08-04T00:05:00Z") -> ProviderObservation:
    metadata = {
        "project": "sov-hybrid-suite",
        "region": "africa-south1",
        "service": "fo-transcription-bridge",
        "revision": "fo-transcription-bridge-00001-abc",
        "private": True,
        "tag_removed": True,
    }
    return ProviderObservation(
        observation_id="cloud-run-proof-001",
        provider="google_cloud_run",
        provider_native=True,
        scopes=(
            "authenticated_invoke",
            "service_readback",
            "health_readback",
            "persistence_readback",
            "reversible_tag_rollback",
        ),
        proofs={
            "execution": True,
            "readback": True,
            "health": True,
            "persistence": True,
            "rollback": True,
            "private_invocation": True,
        },
        observed_at=observed_at,
        locator="projects/sov-hybrid-suite/locations/africa-south1/services/fo-transcription-bridge",
        content_sha256=digest(metadata),
        metadata=metadata,
    )


class LiveProviderExpansionTests(unittest.TestCase):
    def test_imports_six_reversible_providers_and_cloud_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fabric = LiveProviderExpansionFabric(tmp)
            decisions = fabric.import_certification_register(register(), now=NOW)
            self.assertEqual(6, len(decisions))
            self.assertTrue(all(row["admitted"] for row in decisions))
            self.assertTrue(fabric.admit(cloud_observation(), now=NOW)["admitted"])
            projection = fabric.project(now=NOW)
            self.assertEqual("LIVE_PROVIDER_EXPANSION_VERIFIED_EXTERNAL_GATES_UNCHANGED", projection["status"])
            self.assertEqual(7, projection["live_provider_count"])
            self.assertTrue(projection["live_cloud_provider_execution"])
            self.assertEqual(0, projection["verified_revenue_events"])
            self.assertFalse(projection["full_commercial_maturity"])

    def test_rejects_overstated_register(self) -> None:
        bad = register()
        bad["truth_boundary"]["gmail_send_certified"] = True
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                LiveProviderExpansionFabric(tmp).import_certification_register(bad, now=NOW)

    def test_rejects_stale_and_unauthorised_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fabric = LiveProviderExpansionFabric(tmp)
            stale = replace(cloud_observation("2026-08-01T00:00:00Z"), scopes=cloud_observation().scopes + ("deploy_production",))
            decision = fabric.admit(stale, now=NOW)
            self.assertFalse(decision["admitted"])
            self.assertTrue(any(reason.startswith("UNAUTHORISED_SCOPE") for reason in decision["reasons"]))
            self.assertIn("OBSERVATION_STALE", decision["reasons"])

    def test_rejects_tampered_hash_and_missing_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fabric = LiveProviderExpansionFabric(tmp)
            proof = cloud_observation()
            broken = replace(proof, content_sha256="not-a-sha", proofs={**proof.proofs, "rollback": False})
            decision = fabric.admit(broken, now=NOW)
            self.assertFalse(decision["admitted"])
            self.assertIn("INVALID_CONTENT_SHA256", decision["reasons"])
            self.assertIn("MISSING_PROOF:rollback", decision["reasons"])

    def test_restart_and_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = LiveProviderExpansionFabric(tmp)
            first.import_certification_register(register(), now=NOW)
            first.admit(cloud_observation(), now=NOW)
            lines = first.ledger_file.read_text().splitlines()
            second = LiveProviderExpansionFabric(tmp)
            duplicate = second.admit(cloud_observation(), now=NOW)
            self.assertTrue(duplicate["admitted"])
            self.assertEqual(lines, second.ledger_file.read_text().splitlines())
            self.assertTrue(second.verify_ledger())

    def test_exact_rollback_restores_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fabric = LiveProviderExpansionFabric(tmp)
            fabric.import_certification_register(register(), now=NOW)
            fabric.admit(cloud_observation(), now=NOW)
            before = fabric.state_file.read_bytes()
            snapshot = fabric.snapshot("before-marker")
            fabric.record_probe_marker("temporary")
            self.assertNotEqual(before, fabric.state_file.read_bytes())
            receipt = fabric.restore(snapshot)
            self.assertEqual("ROLLBACK_RESTORED", receipt["status"])
            self.assertEqual(before, fabric.state_file.read_bytes())
            self.assertTrue(receipt["ledger_integrity"])


if __name__ == "__main__":
    unittest.main()
