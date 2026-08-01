from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Protocol

_OPERATION_ID = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


class ProviderAdapterError(RuntimeError):
    """Base error for provider adapter failures."""


class ProviderReadbackMismatch(ProviderAdapterError):
    """Raised when provider readback does not match the written payload."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class GoogleDriveProvider(Protocol):
    """Minimal provider surface required by the ECTS Google Drive canary."""

    def create_document(self, title: str) -> dict[str, Any]:
        ...

    def write_document(self, file_id: str, text: str) -> dict[str, Any]:
        ...

    def move_file(self, file_id: str, parent_folder_id: str) -> dict[str, Any]:
        ...

    def read_document(self, file_id: str) -> dict[str, Any]:
        ...

    def get_file_metadata(self, file_id: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class GoogleDriveCanaryRequest:
    operation_id: str
    title: str
    parent_folder_id: str
    payload: dict[str, Any]

    def canonical_text(self) -> str:
        return canonical_json(self.payload)

    def fingerprint(self) -> str:
        return sha256_text(
            canonical_json(
                {
                    "operation_id": self.operation_id,
                    "title": self.title,
                    "parent_folder_id": self.parent_folder_id,
                    "payload": self.payload,
                }
            )
        )


@dataclass(frozen=True)
class GoogleDriveCanaryReceipt:
    receipt_version: str
    provider: str
    operation_id: str
    request_sha256: str
    file_id: str
    document_revision_id: str
    parent_folder_id: str
    written_text_sha256: str
    readback_text_sha256: str
    metadata_name: str
    state: str
    receipt_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def execute_google_drive_canary(
    provider: GoogleDriveProvider,
    request: GoogleDriveCanaryRequest,
) -> GoogleDriveCanaryReceipt:
    """Create, write, move and read back one provider-native Google Doc."""

    if not _OPERATION_ID.fullmatch(request.operation_id):
        raise ProviderAdapterError("operation_id must be 8-128 safe characters")
    if not request.parent_folder_id:
        raise ProviderAdapterError("parent_folder_id is required")

    canonical_text = request.canonical_text()
    written_sha = sha256_text(canonical_text)

    created = provider.create_document(request.title)
    file_id = str(created["file_id"])

    write_result = provider.write_document(file_id, canonical_text)
    provider.move_file(file_id, request.parent_folder_id)

    readback = provider.read_document(file_id)
    readback_text = str(readback["text"])
    readback_sha = sha256_text(readback_text)
    if readback_text != canonical_text:
        raise ProviderReadbackMismatch(
            f"provider readback mismatch: expected {written_sha}, got {readback_sha}"
        )

    metadata = provider.get_file_metadata(file_id)
    parent_ids = [str(item) for item in metadata.get("parent_ids", [])]
    if request.parent_folder_id not in parent_ids:
        raise ProviderReadbackMismatch(
            f"file {file_id} was not read back in the required parent folder"
        )

    unsigned = {
        "receipt_version": "ECTS-GDRIVE-1.0",
        "provider": "google_drive",
        "operation_id": request.operation_id,
        "request_sha256": request.fingerprint(),
        "file_id": file_id,
        "document_revision_id": str(
            readback.get("revision_id") or write_result.get("revision_id") or ""
        ),
        "parent_folder_id": request.parent_folder_id,
        "written_text_sha256": written_sha,
        "readback_text_sha256": readback_sha,
        "metadata_name": str(metadata.get("name") or request.title),
        "state": "COMPLETED",
    }
    return GoogleDriveCanaryReceipt(
        **unsigned,
        receipt_sha256=sha256_text(canonical_json(unsigned)),
    )


def verify_google_drive_receipt(receipt: GoogleDriveCanaryReceipt) -> bool:
    unsigned = receipt.as_dict()
    expected = unsigned.pop("receipt_sha256")
    return sha256_text(canonical_json(unsigned)) == expected
