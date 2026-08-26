from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest
import urllib.parse

from bubbles.apps_script_provider_inventory import TARGETS, run_provider_proof


class FakeProvider:
    def __init__(self) -> None:
        self.receipt_ids: set[str] = set()
        self.calls: list[tuple[str, str]] = []
        self.fail_content_label: str | None = None

    def __call__(
        self,
        url: str,
        *,
        access_token: str,
        method: str = "GET",
        body=None,
        timeout: int = 30,
    ):
        self.calls.append((method, url))
        self.assert_token = access_token
        if "script.googleapis.com" in url and url.endswith("/content"):
            script_id = urllib.parse.unquote(url.split("/projects/", 1)[1].split("/", 1)[0])
            label = next(label for label, value in TARGETS if value == script_id)
            if label == self.fail_content_label:
                return 403, {"error": {"status": "PERMISSION_DENIED"}}
            return 200, {
                "scriptId": script_id,
                "files": [
                    {"name": "Code", "type": "SERVER_JS", "source": f"SECRET_SOURCE_{label}"},
                    {"name": "appsscript", "type": "JSON", "source": "{}"},
                ],
            }
        if "script.googleapis.com" in url and "/deployments?" in url:
            script_id = urllib.parse.unquote(url.split("/projects/", 1)[1].split("/", 1)[0])
            return 200, {
                "deployments": [
                    {"deploymentId": f"SECRET_DEPLOYMENT_{script_id}", "deploymentConfig": {"versionNumber": 7}}
                ]
            }
        if "sheets.googleapis.com" in url and method == "GET":
            return 200, {"values": [[value] for value in sorted(self.receipt_ids)]}
        if "sheets.googleapis.com" in url and method == "POST":
            for row in body["values"]:
                self.receipt_ids.add(str(row[0]))
            return 200, {"updates": {"updatedRows": len(body["values"])}}
        raise AssertionError((method, url))


class AppsScriptProviderInventoryTests(unittest.TestCase):
    def _prove(self, provider: FakeProvider):
        return run_provider_proof(
            access_token="TOP_SECRET_ACCESS_TOKEN",
            source_sha="abc123",
            credential_alias="GCP_WIF_PAIR",
            request_json=provider,
            now=datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc),
        )

    def test_three_target_inventory_appends_and_reads_back_redacted_rows(self) -> None:
        provider = FakeProvider()
        receipt = self._prove(provider)
        self.assertEqual("GAS_PRIMARY_PROVIDER_PROOF_CONFIRMED", receipt["classification"])
        self.assertTrue(receipt["provider_reads_proven"])
        self.assertEqual(3, receipt["proof_sheet"]["rows_appended"])
        self.assertEqual(3, receipt["proof_sheet"]["rows_confirmed"])
        self.assertTrue(receipt["mutation_attempted"])
        serialized = json.dumps(receipt)
        self.assertNotIn("TOP_SECRET_ACCESS_TOKEN", serialized)
        self.assertNotIn("SECRET_SOURCE_", serialized)
        self.assertNotIn("SECRET_DEPLOYMENT_", serialized)

    def test_failed_provider_read_blocks_sheet_mutation(self) -> None:
        provider = FakeProvider()
        provider.fail_content_label = "CHATOPS_FRESH"
        receipt = self._prove(provider)
        self.assertEqual("APPS_SCRIPT_PROVIDER_READS_UNPROVEN", receipt["classification"])
        self.assertFalse(receipt["mutation_attempted"])
        self.assertFalse(any(method == "POST" for method, _ in provider.calls))

    def test_deterministic_receipt_ids_make_replay_idempotent(self) -> None:
        provider = FakeProvider()
        first = self._prove(provider)
        posts_after_first = sum(method == "POST" for method, _ in provider.calls)
        second = self._prove(provider)
        posts_after_second = sum(method == "POST" for method, _ in provider.calls)
        self.assertEqual("GAS_PRIMARY_PROVIDER_PROOF_CONFIRMED", first["classification"])
        self.assertEqual("GAS_PRIMARY_PROVIDER_PROOF_CONFIRMED", second["classification"])
        self.assertEqual(posts_after_first, posts_after_second)
        self.assertEqual(3, second["proof_sheet"]["rows_preexisting"])
        self.assertEqual(0, second["proof_sheet"]["rows_appended"])

    def test_missing_access_token_is_fail_closed(self) -> None:
        receipt = run_provider_proof(
            access_token="",
            source_sha="abc123",
            credential_alias="NONE",
            request_json=FakeProvider(),
        )
        self.assertEqual("GOOGLE_ACCESS_TOKEN_UNAVAILABLE", receipt["classification"])
        self.assertFalse(receipt["mutation_attempted"])


if __name__ == "__main__":
    unittest.main()
