import hashlib
import unittest

from heritage_revision_adapter import (
    HeritageIntegrityError,
    HeritageMutationDisabled,
    HeritageRevisionAdapter,
    HeritageRevisionNotPinned,
)


class Executable:
    def __init__(self, value=None, fn=None):
        self.value = value
        self.fn = fn

    def execute(self):
        return self.fn() if self.fn else self.value


class Request:
    def __init__(self, data: bytes):
        self.data = data


class Downloader:
    def __init__(self, buffer, request):
        self.buffer = buffer
        self.request = request
        self.done = False

    def next_chunk(self):
        if not self.done:
            self.buffer.write(self.request.data)
            self.done = True
        return None, True


class Upload:
    def __init__(self, buffer, mimetype=None, resumable=False):
        self.data = buffer.getvalue()
        self.mimetype = mimetype
        self.resumable = resumable


class Revisions:
    def __init__(self, revision_meta, revision_bytes):
        self.meta = revision_meta
        self.bytes = revision_bytes
        self.update_calls = 0

    def get(self, **kwargs):
        return Executable(fn=lambda: dict(self.meta))

    def update(self, **kwargs):
        def apply():
            self.update_calls += 1
            self.meta["keepForever"] = kwargs["body"]["keepForever"]
            return dict(self.meta)

        return Executable(fn=apply)

    def get_media(self, **kwargs):
        return Request(self.bytes)


class Files:
    def __init__(self, existing=None):
        self.objects = existing or {}
        self.create_calls = 0

    def list(self, **kwargs):
        q = kwargs["q"]
        name = q.split("name = '", 1)[1].split("'", 1)[0]
        found = [
            dict(value["meta"])
            for value in self.objects.values()
            if value["meta"]["name"] == name
        ]
        return Executable(value={"files": found})

    def create(self, **kwargs):
        def apply():
            self.create_calls += 1
            file_id = f"archive-{self.create_calls}"
            data = kwargs["media_body"].data
            meta = {
                "id": file_id,
                "name": kwargs["body"]["name"],
                "size": str(len(data)),
                "mimeType": kwargs["media_body"].mimetype,
            }
            self.objects[file_id] = {"meta": meta, "data": data}
            return dict(meta)

        return Executable(fn=apply)

    def get_media(self, **kwargs):
        return Request(self.objects[kwargs["fileId"]]["data"])


class Drive:
    def __init__(self, revision_meta, revision_bytes, existing=None):
        self._revisions = Revisions(revision_meta, revision_bytes)
        self._files = Files(existing=existing)

    def revisions(self):
        return self._revisions

    def files(self):
        return self._files


def make_adapter(drive, allow_mutations):
    return HeritageRevisionAdapter(
        drive,
        allow_mutations=allow_mutations,
        download_factory=Downloader,
        upload_factory=Upload,
    )


class HeritageRevisionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.data = b"historical-release-bytes"
        self.sha = hashlib.sha256(self.data).hexdigest()

    def test_pin_refuses_without_explicit_mutation_enable(self):
        drive = Drive({"id": "r1", "keepForever": False}, self.data)
        adapter = make_adapter(drive, False)
        with self.assertRaises(HeritageMutationDisabled):
            adapter.ensure_keep_forever("f", "r1")
        self.assertEqual(drive._revisions.update_calls, 0)

    def test_pin_sets_keep_forever_and_reads_back(self):
        drive = Drive({"id": "r1", "keepForever": False}, self.data)
        adapter = make_adapter(drive, True)
        receipt = adapter.ensure_keep_forever("f", "r1")
        self.assertEqual(receipt["state"], "PINNED_AND_READBACK_VERIFIED")
        self.assertTrue(receipt["after"]["keepForever"])
        self.assertEqual(drive._revisions.update_calls, 1)

    def test_download_refuses_unpinned_revision(self):
        drive = Drive({"id": "r1", "keepForever": False}, self.data)
        adapter = make_adapter(drive, False)
        with self.assertRaises(HeritageRevisionNotPinned):
            adapter.download_revision(
                "f", "r1", expected_size=len(self.data), expected_sha256=self.sha
            )

    def test_download_rejects_hash_mismatch(self):
        drive = Drive({"id": "r1", "keepForever": True}, self.data)
        adapter = make_adapter(drive, False)
        with self.assertRaises(HeritageIntegrityError):
            adapter.download_revision(
                "f", "r1", expected_size=len(self.data), expected_sha256="0" * 64
            )

    def test_archive_creates_new_object_and_verifies_readback(self):
        drive = Drive(
            {"id": "r1", "keepForever": False, "originalFilename": "old.zip"},
            self.data,
        )
        adapter = make_adapter(drive, True)
        receipt = adapter.archive_revision_to_vault(
            source_file_id="f",
            revision_id="r1",
            parent_folder_id="vault",
            destination_name="v0.5.1.zip",
            expected_size=len(self.data),
            expected_sha256=self.sha,
        )
        self.assertEqual(receipt["integrity"], "VERIFIED")
        self.assertEqual(
            receipt["archive_state"], "NEW_ARCHIVE_CREATED_READBACK_VERIFIED"
        )
        self.assertEqual(receipt["archive_sha256"], self.sha)
        self.assertFalse(receipt["overwrite_performed"])
        self.assertEqual(drive._files.create_calls, 1)

    def test_archive_reuses_only_exact_existing_object(self):
        existing = {
            "already": {
                "meta": {
                    "id": "already",
                    "name": "v0.5.1.zip",
                    "size": str(len(self.data)),
                    "mimeType": "application/zip",
                },
                "data": self.data,
            }
        }
        drive = Drive({"id": "r1", "keepForever": True}, self.data, existing=existing)
        adapter = make_adapter(drive, True)
        receipt = adapter.archive_revision_to_vault(
            source_file_id="f",
            revision_id="r1",
            parent_folder_id="vault",
            destination_name="v0.5.1.zip",
            expected_size=len(self.data),
            expected_sha256=self.sha,
        )
        self.assertEqual(receipt["archive_file_id"], "already")
        self.assertEqual(receipt["archive_state"], "EXISTING_EXACT_ARCHIVE_REUSED")
        self.assertEqual(drive._files.create_calls, 0)

    def test_existing_same_name_wrong_bytes_fails_closed(self):
        existing = {
            "already": {
                "meta": {
                    "id": "already",
                    "name": "v0.5.1.zip",
                    "size": "3",
                    "mimeType": "application/zip",
                },
                "data": b"bad",
            }
        }
        drive = Drive({"id": "r1", "keepForever": True}, self.data, existing=existing)
        adapter = make_adapter(drive, True)
        with self.assertRaises(HeritageIntegrityError):
            adapter.archive_revision_to_vault(
                source_file_id="f",
                revision_id="r1",
                parent_folder_id="vault",
                destination_name="v0.5.1.zip",
                expected_size=len(self.data),
                expected_sha256=self.sha,
            )
        self.assertEqual(drive._files.create_calls, 0)


if __name__ == "__main__":
    unittest.main()
