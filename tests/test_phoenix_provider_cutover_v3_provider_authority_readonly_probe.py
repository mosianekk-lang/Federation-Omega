from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from ops.provider_authority_readonly_probe import (
    CANONICAL_PROJECT_ID,
    CANONICAL_PROJECT_NUMBER,
    CommandResult,
    ProbeError,
    build_probe_receipt,
    canonical_sha256,
    write_receipt,
)


class FakeRunner:
    def __init__(
        self,
        *,
        authenticated: bool = True,
        project_id: str = CANONICAL_PROJECT_ID,
        project_number: str = CANONICAL_PROJECT_NUMBER,
    ):
        self.authenticated = authenticated
        self.project_id = project_id
        self.project_number = project_number
        self.calls: list[tuple[list[str], bool]] = []

    def __call__(
        self,
        args: list[str],
        discard_stdout: bool = False,
    ) -> CommandResult:
        self.calls.append((list(args), discard_stdout))
        joined = " ".join(args)
        if "auth list" in joined:
            if self.authenticated:
                return CommandResult(True, 0, "operator@example.com", "")
            return CommandResult(True, 0, "", "")
        if "auth print-access-token" in joined:
            if self.authenticated:
                self.assert_token_discarded(discard_stdout)
                return CommandResult(True, 0, "", "")
            return CommandResult(False, 1, "", "not authenticated")
        if "projects describe" in joined:
            return CommandResult(
                True,
                0,
                json.dumps(
                    {
                        "projectId": self.project_id,
                        "projectNumber": self.project_number,
                        "lifecycleState": "ACTIVE",
                    }
                ),
                "",
            )
        return CommandResult(True, 0, json.dumps({"state": "ACTIVE"}), "")

    @staticmethod
    def assert_token_discarded(discard_stdout: bool) -> None:
        if not discard_stdout:
            raise AssertionError("access-token stdout must be discarded")


class ProviderAuthorityReadOnlyProbeTests(unittest.TestCase):
    def test_canonical_provider_identity_is_verified(self) -> None:
        runner = FakeRunner()
        receipt = build_probe_receipt(
            runner=runner,
            recorded_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
        )
        self.assertEqual("VERIFIED", receipt["status"])
        self.assertEqual(
            "GOOGLE_PROVIDER_AUTH_VERIFIED_READ_ONLY",
            receipt["classification"],
        )
        self.assertEqual(
            CANONICAL_PROJECT_NUMBER,
            receipt["actual_project_number"],
        )
        self.assertTrue(receipt["provider_authenticated"])
        self.assertTrue(receipt["access_token_check"]["stdout_discarded"])

    def test_missing_provider_auth_fails_closed(self) -> None:
        runner = FakeRunner(authenticated=False)
        receipt = build_probe_receipt(runner=runner)
        self.assertEqual("BLOCKED", receipt["status"])
        self.assertEqual(
            "TRUSTED_PROVIDER_AUTHORITY_STILL_BLOCKED",
            receipt["classification"],
        )
        self.assertFalse(receipt["provider_authenticated"])
        commands = [" ".join(args) for args, _ in runner.calls]
        self.assertFalse(any("projects describe" in item for item in commands))

    def test_wrong_project_number_fails_closed(self) -> None:
        runner = FakeRunner(project_number="516699068552")
        receipt = build_probe_receipt(runner=runner)
        self.assertEqual("BLOCKED", receipt["status"])
        self.assertEqual("516699068552", receipt["actual_project_number"])

    def test_noncanonical_requested_target_is_rejected(self) -> None:
        with self.assertRaisesRegex(ProbeError, "non-canonical project target"):
            build_probe_receipt(
                runner=FakeRunner(),
                project_id="legacy-project",
            )

    def test_receipt_cannot_claim_mutation_or_secret_access(self) -> None:
        receipt = build_probe_receipt(runner=FakeRunner())
        self.assertFalse(receipt["provider_mutation_attempted"])
        self.assertFalse(receipt["source_write_attempted"])
        self.assertFalse(receipt["secret_values_accessed"])
        self.assertFalse(receipt["credential_values_recorded"])

    def test_probe_commands_are_read_only_and_keyless(self) -> None:
        runner = FakeRunner()
        build_probe_receipt(runner=runner)
        command_text = "\n".join(
            " ".join(args).lower() for args, _ in runner.calls
        )
        self.assertNotIn("credentials_json", command_text)
        self.assertNotIn("service-account key", command_text)
        self.assertNotIn("secrets versions access", command_text)
        for forbidden in (
            " services enable ",
            " iam service-accounts create ",
            " run deploy ",
            " secrets versions add ",
            " projects add-iam-policy-binding ",
        ):
            self.assertNotIn(forbidden, f" {command_text} ")

    def test_receipt_hash_is_bound(self) -> None:
        receipt = build_probe_receipt(runner=FakeRunner())
        claimed = receipt.pop("receipt_sha256")
        self.assertEqual(claimed, canonical_sha256(receipt))

    def test_write_receipt_persists_exact_json(self) -> None:
        receipt = build_probe_receipt(runner=FakeRunner())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "receipt.json"
            write_receipt(receipt, output)
            self.assertEqual(
                receipt,
                json.loads(output.read_text(encoding="utf-8")),
            )


if __name__ == "__main__":
    unittest.main()
