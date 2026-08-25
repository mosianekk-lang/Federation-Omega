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


def item(name, value, *, public=False, email=False, media="text/plain"):
    content = value.encode() if isinstance(value, str) else value
    return ArtifactInput(
        name,
        content,
        media,
        ArtifactClass.PUBLIC_SAFE if public else ArtifactClass.PRIVATE_CONTROL,
        "source:fixture",
        email,
    )


def make(items, *, event="EVT-001", prior=None, prior_sha=None, sequence=None, every=7):
    return build_backup_plan(
        event_type=BackupEventType.ADMITTED_SOURCE_RELEASE,
        event_id=event,
        created_at=NOW,
        source_identity="repo:owner/project",
        source_version="commit:abc123",
        artifacts=items,
        prior_manifest=prior,
        prior_manifest_sha256=prior_sha,
        sequence=sequence,
        checkpoint_every=every,
    )


class FakeProvider:
    def __init__(self):
        self.aliases = {ALIAS: "private-root"}
        self.files, self.containers, self.emails = {}, {}, []
        self.shared, self.owners, self.non_owners = False, (OWNER,), ()
        self.corrupt, self.count = False, 0

    def resolve_destination(self, alias):
        return self.aliases.get(alias, "")

    def create_snapshot_container(self, destination, name):
        self.count += 1
        ref = f"{destination}/snapshot-{self.count}"
        self.containers[ref] = name
        return ref

    def upload_bytes(self, container, name, content, media_type):
        self.count += 1
        ref = f"file-{self.count}"
        self.files[ref] = bytes(content)
        return ProviderFile(ref, name, len(content), f"private://{ref}")

    def download_bytes(self, file_id):
        return self.files[file_id] + (b"corrupt" if self.corrupt else b"")

    def read_permissions(self, container):
        return PermissionReadback(self.shared, self.owners, self.non_owners)

    def send_continuity_email(self, *, subject, body, attachments):
        self.emails.append((subject, body, tuple(attachments)))
        return f"message-{len(self.emails)}"


class BackupPipelineTests(unittest.TestCase):
    def test_01_initial_full_is_deterministic(self):
        left = make([item("b.txt", "B"), item("a.txt", "A")])
        right = make([item("a.txt", "A"), item("b.txt", "B")])
        self.assertEqual(BackupMode.FULL, left.mode)
        self.assertEqual(left.archive_bytes, right.archive_bytes)
        self.assertTrue(verify_archive(left))

    def test_02_delta_selects_changed_and_new(self):
        full = make([item("a.txt", "A"), item("b.txt", "B")])
        delta = make(
            [item("a.txt", "A2"), item("b.txt", "B"), item("c.txt", "C")],
            event="EVT-002",
            prior=full.manifest,
            prior_sha=full.manifest_sha256,
        )
        self.assertEqual(BackupMode.DELTA, delta.mode)
        self.assertEqual(["a.txt", "c.txt"], delta.manifest["selected_artifacts"])

    def test_03_removal_is_tombstoned(self):
        full = make([item("a.txt", "A"), item("b.txt", "B")])
        delta = make(
            [item("a.txt", "A")],
            event="EVT-REMOVE",
            prior=full.manifest,
            prior_sha=full.manifest_sha256,
        )
        self.assertEqual(["b.txt"], delta.manifest["removed_artifacts"])

    def test_04_seventh_cycle_is_full_checkpoint(self):
        full = make([item("a.txt", "A")], sequence=6)
        checkpoint = make(
            [item("a.txt", "A")],
            event="EVT-CHECKPOINT",
            prior=full.manifest,
            prior_sha=full.manifest_sha256,
            sequence=7,
        )
        self.assertEqual(BackupMode.FULL, checkpoint.mode)

    def test_05_no_change_has_no_archive(self):
        full = make([item("a.txt", "A")])
        same = make(
            [item("a.txt", "A")],
            event="EVT-SAME",
            prior=full.manifest,
            prior_sha=full.manifest_sha256,
        )
        self.assertEqual(BackupMode.NO_CHANGE, same.mode)
        self.assertIsNone(same.archive_bytes)
        self.assertTrue(verify_archive(same))

    def test_06_bad_prior_hash_and_sequence_fail(self):
        full = make([item("a.txt", "A")], sequence=3)
        with self.assertRaisesRegex(BackupError, "prior manifest"):
            make([item("a.txt", "B")], event="EVT-HASH", prior=full.manifest, prior_sha="0" * 64)
        with self.assertRaisesRegex(BackupError, "sequence must advance"):
            make(
                [item("a.txt", "B")],
                event="EVT-SEQ",
                prior=full.manifest,
                prior_sha=full.manifest_sha256,
                sequence=3,
            )

    def test_07_unsafe_and_duplicate_names_fail(self):
        with self.assertRaisesRegex(BackupError, "traverse"):
            make([item("../escape.txt", "x")])
        with self.assertRaisesRegex(BackupError, "unique"):
            make([item("same.txt", "x"), item("same.txt", "y")])

    def test_08_unknown_event_fails(self):
        with self.assertRaisesRegex(BackupError, "unsupported backup event"):
            build_backup_plan(
                event_type="NOT_REAL",
                event_id="EVT-BAD",
                created_at=NOW,
                source_identity="source",
                source_version="version",
                artifacts=[item("a.txt", "A")],
            )

    def test_09_secret_metadata_fails_but_reference_passes(self):
        with self.assertRaisesRegex(BackupError, "secret-bearing metadata"):
            reject_secret_metadata({"access_token": "not-stored"})
        reject_secret_metadata({"secret_ref": "projects/project/secrets/name/versions/latest"})

    def test_10_public_and_email_secret_shapes_fail(self):
        with self.assertRaisesRegex(BackupError, "credential-shaped"):
            make([item("public.txt", "Bearer abcdefghijklmnopqrstuvwxyz123456", public=True)])
        marker = "-----BEGIN " + "PRIVATE" + " KEY-----"
        with self.assertRaisesRegex(BackupError, "credential-shaped"):
            make([item("email.txt", marker, email=True)])

    def test_11_private_binary_is_opaque(self):
        binary = item(
            "opaque.bin",
            b"Bearer abcdefghijklmnopqrstuvwxyz123456",
            media="application/octet-stream",
        )
        self.assertTrue(verify_archive(make([binary])))

    def test_12_raw_provider_id_is_not_an_alias(self):
        with self.assertRaisesRegex(BackupError, "private canonical alias"):
            execute_private_backup(
                plan=make([item("a.txt", "A")]),
                provider=FakeProvider(),
                destination_alias="1AbCdEfGhIjKlMnOp",
                expected_owner_identity=OWNER,
                ledger=IdempotencyLedger(),
                send_email=False,
            )

    def test_13_provider_readback_email_and_ledger_pass(self):
        provider, ledger = FakeProvider(), IdempotencyLedger()
        current = make([item("safe.txt", "safe", public=True, email=True)])
        receipt = execute_private_backup(
            plan=current,
            provider=provider,
            destination_alias=ALIAS,
            expected_owner_identity=OWNER,
            ledger=ledger,
        )
        self.assertEqual(current.archive_sha256, receipt["provider_download_sha256"])
        self.assertEqual("ADMITTED", receipt["idempotency_state"])
        self.assertIn(current.archive_name, [a[0] for a in provider.emails[0][2]])
        self.assertTrue(ledger.verify_chain())

    def test_14_sensitive_archive_is_not_emailed(self):
        provider = FakeProvider()
        current = make([item("private.txt", "private")])
        execute_private_backup(
            plan=current,
            provider=provider,
            destination_alias=ALIAS,
            expected_owner_identity=OWNER,
            ledger=IdempotencyLedger(),
        )
        self.assertEqual(
            ["BACKUP_MANIFEST.json", "CHECKSUMS.sha256"],
            [a[0] for a in provider.emails[0][2]],
        )

    def test_15_corrupt_provider_download_fails(self):
        provider = FakeProvider()
        provider.corrupt = True
        with self.assertRaisesRegex(BackupError, "provider-download"):
            execute_private_backup(
                plan=make([item("a.txt", "A")]),
                provider=provider,
                destination_alias=ALIAS,
                expected_owner_identity=OWNER,
                ledger=IdempotencyLedger(),
                send_email=False,
            )

    def test_16_shared_wrong_owner_or_extra_permission_fails(self):
        for setup in ("shared", "owner", "extra"):
            provider = FakeProvider()
            if setup == "shared":
                provider.shared = True
            elif setup == "owner":
                provider.owners = ("other@example.invalid",)
            else:
                provider.non_owners = ("reader@example.invalid",)
            with self.assertRaisesRegex(BackupError, "owner-only"):
                execute_private_backup(
                    plan=make([item("a.txt", "A")]),
                    provider=provider,
                    destination_alias=ALIAS,
                    expected_owner_identity=OWNER,
                    ledger=IdempotencyLedger(),
                    send_email=False,
                )

    def test_17_exact_retry_does_not_repeat_provider_effect(self):
        provider, ledger = FakeProvider(), IdempotencyLedger()
        current = make([item("a.txt", "A")])
        first = execute_private_backup(
            plan=current,
            provider=provider,
            destination_alias=ALIAS,
            expected_owner_identity=OWNER,
            ledger=ledger,
            send_email=False,
        )
        count = len(provider.containers)
        second = execute_private_backup(
            plan=current,
            provider=provider,
            destination_alias=ALIAS,
            expected_owner_identity=OWNER,
            ledger=ledger,
            send_email=False,
        )
        self.assertEqual(count, len(provider.containers))
        self.assertEqual("ALREADY_ADMITTED_EXACT", second["idempotency_state"])
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])

    def test_18_changed_payload_collision_and_tamper_fail(self):
        ledger = IdempotencyLedger()
        ledger.admit(key="same", payload_sha256="a" * 64, receipt={"state": "first"})
        with self.assertRaisesRegex(BackupError, "changed payload"):
            ledger.admit(key="same", payload_sha256="b" * 64, receipt={"state": "second"})
        tampered = [dict(event) for event in ledger.events]
        tampered[0]["receipt"] = {"state": "tampered"}
        with self.assertRaisesRegex(BackupError, "hash chain"):
            IdempotencyLedger(tampered)

    def test_19_full_delta_restore_is_exact(self):
        full = make([item("a.txt", "A"), item("b.txt", "B")])
        delta = make(
            [item("a.txt", "A2"), item("c.txt", "C")],
            event="EVT-RESTORE",
            prior=full.manifest,
            prior_sha=full.manifest_sha256,
        )
        self.assertEqual(
            {"a.txt": b"A2", "c.txt": b"C"},
            restore_snapshot_chain([full.archive_bytes, delta.archive_bytes]),
        )

    def test_20_restore_binding_and_corrupt_archive_fail(self):
        full = make([item("a.txt", "A")])
        delta = make(
            [item("a.txt", "B")],
            event="EVT-DELTA",
            prior=full.manifest,
            prior_sha=full.manifest_sha256,
        )
        with self.assertRaisesRegex(BackupError, "begin with a full"):
            restore_snapshot_chain([delta.archive_bytes])
        bad = deepcopy(delta.manifest)
        bad["previous_manifest_sha256"] = "0" * 64
        changed_manifest = (json.dumps(bad, sort_keys=True, separators=(",", ":")) + "\n").encode()
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(delta.archive_bytes)) as source, zipfile.ZipFile(
            output, "w", zipfile.ZIP_DEFLATED
        ) as target:
            for name in source.namelist():
                target.writestr(name, changed_manifest if name == "BACKUP_MANIFEST.json" else source.read(name))
        with self.assertRaisesRegex(BackupError, "previous-manifest binding"):
            restore_snapshot_chain([full.archive_bytes, output.getvalue()])
        with self.assertRaises(BackupError):
            verify_archive(full, full.archive_bytes[:-8] + b"corrupt!")

    def test_21_planning_truth_boundary_has_no_provider_claim(self):
        truth = make([item("a.txt", "A")]).manifest["truth_boundary"]
        self.assertFalse(truth["provider_upload_performed"])
        self.assertFalse(truth["gmail_receipt_sent"])
        self.assertFalse(truth["provider_runtime_proven"])
        self.assertFalse(truth["external_effect"])


if __name__ == "__main__":
    unittest.main()
