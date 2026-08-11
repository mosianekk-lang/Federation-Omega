import unittest

from evidenceops.connector_foundry.google_drive_adapter import (
    GoogleDriveCanaryRequest,
    ProviderReadbackMismatch,
    execute_google_drive_canary,
    verify_google_drive_receipt,
)


class FakeDriveProvider:
    def __init__(self, tamper: bool = False) -> None:
        self.tamper = tamper
        self.docs = {}
        self.parents = {}

    def create_document(self, title):
        file_id = "fake-drive-file-001"
        self.docs[file_id] = {"title": title, "text": "", "revision_id": "rev-1"}
        self.parents[file_id] = []
        return {"file_id": file_id, "title": title}

    def write_document(self, file_id, text):
        self.docs[file_id]["text"] = text
        self.docs[file_id]["revision_id"] = "rev-2"
        return {"revision_id": "rev-2"}

    def move_file(self, file_id, parent_folder_id):
        self.parents[file_id] = [parent_folder_id]
        return {"parent_ids": [parent_folder_id]}

    def read_document(self, file_id):
        text = self.docs[file_id]["text"]
        if self.tamper:
            text += "-tampered"
        return {
            "text": text,
            "revision_id": self.docs[file_id]["revision_id"],
        }

    def get_file_metadata(self, file_id):
        return {
            "name": self.docs[file_id]["title"],
            "parent_ids": self.parents[file_id],
        }


class GoogleDriveAdapterTests(unittest.TestCase):
    def setUp(self):
        self.request = GoogleDriveCanaryRequest(
            operation_id="ECTS-GDRIVE-TEST-001",
            title="ECTS Google Drive Test",
            parent_folder_id="folder-001",
            payload={
                "lane_id": "LANE-CONNECTOR-FOUNDRY",
                "message": "provider adapter test",
            },
        )

    def test_create_write_move_readback_receipt(self):
        receipt = execute_google_drive_canary(FakeDriveProvider(), self.request)
        self.assertEqual(receipt.state, "COMPLETED")
        self.assertEqual(receipt.written_text_sha256, receipt.readback_text_sha256)
        self.assertTrue(verify_google_drive_receipt(receipt))

    def test_tampered_readback_is_rejected(self):
        with self.assertRaises(ProviderReadbackMismatch):
            execute_google_drive_canary(FakeDriveProvider(tamper=True), self.request)


if __name__ == "__main__":
    unittest.main()
