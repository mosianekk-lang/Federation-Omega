from __future__ import annotations

from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from federation_consolidation.sovara_sovereign_backup import (  # noqa: E402
    ArtifactClass,
    ArtifactInput,
    BackupError,
    BackupEventType,
    BackupMode,
    IdempotencyLedger,
    PermissionReadback,
    ProviderFile,
    build_backup_plan,
    execute_private_backup,
    reject_secret_metadata,
    restore_snapshot_chain,
    verify_archive,
)


NOW = "2026-08-25T10:00:00+02:00"
OWNER = "owner@example.invalid"
ALIAS = "SOVARA_PRIVATE_BACKUP_REPOSITORY_V1"


def artifact(
    name: str,
    content: bytes | str,
    *,
    classification: ArtifactClass = ArtifactClass.PRIVATE_CONTROL,
    email_eligible: bool = False,
    media_type: str = "text/plain",
) -> ArtifactInput:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return ArtifactInput(
        logical_name=name,
        content=content,
        media_type=media_type,
        classification=classification,
        source_ref="source:fixture",
        email_eligible=email_eligible,
    )


def plan(
    artifacts,
    *,
    event_id="EVT-001",
    prior=None,
    prior_sha=None,
    sequence=None,
    checkpoint_every=7,
    force_full=False,
):
    return build_backup_plan(
        event_type=BackupEventType.ADMITTED_SOURCE_RELEASE,
        event_id=event_id,
        created_at=NOW,
        source_identity="repo:owner/project",
        source_version="commit:abc123",
        artifacts=artifacts,
        prior_manifest=prior,
        prior_manifest_sha256=prior_sha,
        sequence=sequence,
        checkpoint_every=checkpoint_every,
        force_full=force_full,
    )


class FakeProvider:
    def __init__(self):
        self.aliases = {ALIAS: "private-root"}
        self.containers = {}
        self.files = {}
        self.emails = []
        self.shared = False
        self.owners = (OWNER,)
        self.non_owners = ()
        self.corrupt_download = False
        self.counter = 0

    def resolve_destination(self, alias: str) -> str:
        return self.aliases.get(alias, "")

    def create_snapshot_container(self, destination: str, name: str) -> str:
        self.counter += 1
        container = f"{destination}/snapshot-{self.counter}"
        self.containers[container] = {"name": name}
        return container

    def upload_bytes(self, container, name, content, media_type):
        self.counter += 1
        file_id = f"file-{self.counter}"
        self.files[file_id] = bytes(content)
        return ProviderFile(
            file_id=file_id,
            name=name,
            size_bytes=len(content),
            url=f"private://{file_id}",
        )

    def download_bytes(self, file_id):
        data = self.files[file_id]
        return data + b"corruption" if self.corrupt_download else data

    def read_permissions(self, container):
        return PermissionReadback(
            shared=self.shared,
            owner_identities=self.owners,
            non_owner_identities=self.non_owners,
        )

    def send_continuity_email(self, *, subject, body, attachments):
        self.emails.append((subject, body, tuple(attachments)))
        return f"message-{len(self.emails)}"


class BackupPlanningTests(unittest.TestCase):
    def test_initial_snapshot_is_full_and_deterministic(self):
        inputs = [artifact("b.txt", "B"), artifact("a.txt", "A")]
        first = plan(inputs)
        second = plan(reversed(inputs))
        self.assertEqual(BackupMode.FULL, first.mode)
        self.assertEqual(first.manifest_bytes, second.manifest_bytes)
        self.assertEqual(first.archive_bytes, second.archive_bytes)
        self.assertEqual(first.archive_sha256, second.archive_sha256)
        self.assertTrue(verify_archive(first))

    def test_delta_contains_only_changed_and_new_artifacts(self):
        baseline = plan([artifact("a.txt", "A"), artifact("b.txt", "B")])
        delta = plan(
            [artifact("a.txt", "A2"), artifact("b.txt", "B"), artifact("c.txt", "C")],
            event_id="EVT-002",
            prior=baseline.manifest,
            prior_sha=baseline.manifest_sha256,
        )
        self.assertEqual(BackupMode.DELTA, delta.mode)
        self.assertEqual(["a.txt", "c.txt"], delta.manifest["selected_artifacts"])
        with zipfile.ZipFile(io.BytesIO(delta.archive_bytes)) as archive:
            self.assertIn("artifacts/a.txt", archive.namelist())
            self.assertIn("artifacts/c.txt", archive.namelist())
            self.assertNotIn("artifacts/b.txt", archive.namelist())

    def test_delta_records_removal_tombstones(self):
        baseline = plan([artifact("a.txt", "A"), artifact("b.txt", "B")])
        delta = plan(
            [artifact("a.txt", "A")],
            event_id="EVT-REMOVAL",
            prior=baseline.manifest,
            prior_sha=baseline.manifest_sha256,
        )
        self.assertEqual(BackupMode.DELTA, delta.mode)
        self.assertEqual(["b.txt"], delta.manifest["removed_artifacts"])
        self.assertEqual([], delta.manifest["selected_artifacts"])

    def test_periodic_checkpoint_forces_full_snapshot(self):
        baseline = plan([artifact("a.txt", "A")], sequence=6)
        checkpoint = plan(
            [artifact("a.txt", "A")],
            event_id="EVT-CHECKPOINT",
            prior=baseline.manifest,
            prior_sha=baseline.manifest_sha256,
            sequence=7,
            checkpoint_every=7,
        )
        self.assertEqual(BackupMode.FULL, checkpoint.mode)
        self.assertEqual(["a.txt"], checkpoint.manifest["selected_artifacts"])

    def test_no_change_emits_manifest_without_archive(self):
        baseline = plan([artifact("a.txt", "A")])
        no_change = plan(
            [artifact("a.txt", "A")],
            event_id="EVT-NO-CHANGE",
            prior=baseline.manifest,
            prior_sha=baseline.manifest_sha256,
        )
        self.assertEqual(BackupMode.NO_CHANGE, no_change.mode)
        self.assertIsNone(no_change.archive_bytes)
        self.assertTrue(verify_archive(no_change))

    def test_prior_manifest_hash_mismatch_fails_closed(self):
        baseline = plan([artifact("a.txt", "A")])
        with self.assertRaisesRegex(BackupError, "prior manifest SHA-256"):
            plan(
                [artifact("a.txt", "B")],
                event_id="EVT-BAD-PRIOR",
                prior=baseline.manifest,
                prior_sha="0" * 64,
            )

    def test_path_traversal_and_duplicate_names_are_rejected(self):
        with self.assertRaisesRegex(BackupError, "traverse"):
            plan([artifact("../escape.txt", "x")])
        with self.assertRaisesRegex(BackupError, "unique"):
            plan([artifact("same.txt", "x"), artifact("same.txt", "y")])

    def test_unsupported_event_and_non_advancing_sequence_are_rejected(self):
        with self.assertRaisesRegex(BackupError, "unsupported backup event"):
            build_backup_plan(
                event_type="NOT_REAL",
                event_id="EVT-BAD",
                created_at=NOW,
                source_identity="source",
                source_version="version",
                artifacts=[artifact("a.txt", "A")],
            )
        baseline = plan([artifact("a.txt", "A")], sequence=3)
        with self.assertRaisesRegex(BackupError, "sequence must advance"):
            plan(
                [artifact("a.txt", "B")],
                event_id="EVT-SEQ",
                prior=baseline.manifest,
                prior_sha=baseline.manifest_sha256,
                sequence=3,
            )


class SecretAndIdentityBoundaryTests(unittest.TestCase):
    def test_raw_secret_metadata_is_rejected_but_reference_is_allowed(self):
        with self.assertRaisesRegex(BackupError, "secret-bearing metadata"):
            reject_secret_metadata({"access_token": "not-stored"})
        reject_secret_metadata({"secret_ref": "projects/project/secrets/name/versions/latest"})

    def test_public_or_email_text_with_credential_shape_is_rejected(self):
        with self.assertRaisesRegex(BackupError, "credential-shaped"):
            plan(
                [
                    artifact(
                        "public.txt",
                        "Bearer abcdefghijklmnopqrstuvwxyz123456",
                        classification=ArtifactClass.PUBLIC_SAFE,
                    )
                ]
            )
        with self.assertRaisesRegex(BackupError, "credential-shaped"):
            plan(
                [
                    artifact(
                        "email.txt",
                        "-----BEGIN PRIVATE KEY-----",
                        email_eligible=True,
                    )
                ]
            )

    def test_private_non_email_binary_is_opaque_to_content_scanner(self):
        private = artifact(
            "opaque.bin",
            b"Bearer abcdefghijklmnopqrstuvwxyz123456",
            classification=ArtifactClass.PRIVATE_SENSITIVE,
            email_eligible=False,
            media_type="application/octet-stream",
        )
        result = plan([private])
        self.assertTrue(verify_archive(result))

    def test_raw_provider_id_cannot_replace_private_alias(self):
        provider = FakeProvider()
        result = plan([artifact("a.txt", "A")])
        with self.assertRaisesRegex(BackupError, "private canonical alias"):
            execute_private_backup(
                plan=result,
                provider=provider,
                destination_alias="1AbCdEfGhIjKlMnOp",
                expected_owner_identity=OWNER,
                ledger=IdempotencyLedger(),
                send_email=False,
            )


class ProviderExecutionTests(unittest.TestCase):
    def test_private_provider_execution_uploads_downloads_and_emails(self):
        provider = FakeProvider()
        result = plan(
            [
                artifact(
                    "safe.txt",
                    "safe",
                    classification=ArtifactClass.PUBLIC_SAFE,
                    email_eligible=True,
                )
            ]
        )
        ledger = IdempotencyLedger()
        receipt = execute_private_backup(
            plan=result,
            provider=provider,
            destination_alias=ALIAS,
            expected_owner_identity=OWNER,
            ledger=ledger,
        )
        self.assertEqual("ADMITTED", receipt["idempotency_state"])
        self.assertEqual(result.archive_sha256, receipt["provider_download_sha256"])
        self.assertTrue(receipt["permission_readback"]["owner_only_private"])
        self.assertEqual(1, len(provider.emails))
        attachment_names = [item[0] for item in provider.emails[0][2]]
        self.assertIn(result.archive_name, attachment_names)
        self.assertTrue(ledger.verify_chain())

    def test_sensitive_archive_is_not_attached_to_email(self):
        provider = FakeProvider()
        result = plan([artifact("private.txt", "private", email_eligible=False)])
        execute_private_backup(
            plan=result,
            provider=provider,
            destination_alias=ALIAS,
            expected_owner_identity=OWNER,
            ledger=IdempotencyLedger(),
        )
        attachment_names = [item[0] for item in provider.emails[0][2]]
        self.assertNotIn(result.archive_name, attachment_names)
        self.assertEqual(["BACKUP_MANIFEST.json", "CHECKSUMS.sha256"], attachment_names)

    def test_provider_download_corruption_fails(self):
        provider = FakeProvider()
        provider.corrupt_download = True
        with self.assertRaisesRegex(BackupError, "provider-download"):
            execute_private_backup(
                plan=plan([artifact("a.txt", "A")]),
                provider=provider,
                destination_alias=ALIAS,
                expected_owner_identity=OWNER,
                ledger=IdempotencyLedger(),
                send_email=False,
            )

    def test_shared_or_wrong_owner_container_fails(self):
        provider = FakeProvider()
        provider.shared = True
        with self.assertRaisesRegex(BackupError, "owner-only"):
            execute_private_backup(
                plan=plan([artifact("a.txt", "A")]),
                provider=provider,
                destination_alias=ALIAS,
                expected_owner_identity=OWNER,
                ledger=IdempotencyLedger(),
                send_email=False,
            )
        provider = FakeProvider()
        provider.owners = ("other@example.invalid",)
        with self.assertRaisesRegex(BackupError, "owner-only"):
            execute_private_backup(
                plan=plan([artifact("a.txt", "A")]),
                provider=provider,
                destination_alias=ALIAS,
                expected_owner_identity=OWNER,
                ledger=IdempotencyLedger(),
                send_email=False,
            )

    def test_exact_retry_reuses_receipt_without_duplicate_provider_effect(self):
        provider = FakeProvider()
        ledger = IdempotencyLedger()
        current = plan([artifact("a.txt", "A")])
        first = execute_private_backup(
            plan=current,
            provider=provider,
            destination_alias=ALIAS,
            expected_owner_identity=OWNER,
            ledger=ledger,
            send_email=False,
        )
        container_count = len(provider.containers)
        second = execute_private_backup(
            plan=current,
            provider=provider,
            destination_alias=ALIAS,
            expected_owner_identity=OWNER,
            ledger=ledger,
            send_email=False,
        )
        self.assertEqual(container_count, len(provider.containers))
        self.assertEqual("ALREADY_ADMITTED_EXACT", second["idempotency_state"])
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])

    def test_changed_payload_collision_is_rejected(self):
        ledger = IdempotencyLedger()
        ledger.admit(
            key="same-key",
            payload_sha256="a" * 64,
            receipt={"state": "first"},
        )
        with self.assertRaisesRegex(BackupError, "changed payload"):
            ledger.admit(
                key="same-key",
                payload_sha256="b" * 64,
                receipt={"state": "second"},
            )

    def test_tampered_ledger_chain_is_rejected(self):
        ledger = IdempotencyLedger()
        ledger.admit(
            key="one",
            payload_sha256="a" * 64,
            receipt={"state": "ok"},
        )
        tampered = [dict(item) for item in ledger.events]
        tampered[0]["receipt"] = {"state": "tampered"}
        with self.assertRaisesRegex(BackupError, "hash chain"):
            IdempotencyLedger(tampered)


class RestoreAndIntegrityTests(unittest.TestCase):
    def test_full_plus_delta_restores_current_snapshot(self):
        full = plan([artifact("a.txt", "A"), artifact("b.txt", "B")])
        delta = plan(
            [artifact("a.txt", "A2"), artifact("c.txt", "C")],
            event_id="EVT-RESTORE-2",
            prior=full.manifest,
            prior_sha=full.manifest_sha256,
        )
        restored = restore_snapshot_chain([full.archive_bytes, delta.archive_bytes])
        self.assertEqual({"a.txt": b"A2", "c.txt": b"C"}, restored)

    def test_restore_requires_full_first_and_bound_chain(self):
        full = plan([artifact("a.txt", "A")])
        delta = plan(
            [artifact("a.txt", "B")],
            event_id="EVT-DELTA",
            prior=full.manifest,
            prior_sha=full.manifest_sha256,
        )
        with self.assertRaisesRegex(BackupError, "begin with a full"):
            restore_snapshot_chain([delta.archive_bytes])
        bad_manifest = deepcopy(delta.manifest)
        bad_manifest["previous_manifest_sha256"] = "0" * 64
        bad_manifest_bytes = (
            json.dumps(bad_manifest, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(delta.archive_bytes)) as source, zipfile.ZipFile(
            output, "w", zipfile.ZIP_DEFLATED
        ) as target:
            for name in source.namelist():
                target.writestr(
                    name,
                    bad_manifest_bytes
                    if name == "BACKUP_MANIFEST.json"
                    else source.read(name),
                )
        with self.assertRaisesRegex(BackupError, "previous-manifest binding"):
            restore_snapshot_chain([full.archive_bytes, output.getvalue()])

    def test_corrupted_archive_is_rejected(self):
        current = plan([artifact("a.txt", "A")])
        corrupted = current.archive_bytes[:-8] + b"corrupt!"
        with self.assertRaises(BackupError):
            verify_archive(current, corrupted)

    def test_truth_boundary_does_not_claim_provider_effect_during_planning(self):
        current = plan([artifact("a.txt", "A")])
        truth = current.manifest["truth_boundary"]
        self.assertFalse(truth["provider_upload_performed"])
        self.assertFalse(truth["gmail_receipt_sent"])
        self.assertFalse(truth["provider_runtime_proven"])
        self.assertFalse(truth["external_effect"])


if __name__ == "__main__":
    unittest.main()
