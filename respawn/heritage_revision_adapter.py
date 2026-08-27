from __future__ import annotations

import hashlib
import io
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

DRIVE_READ_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
DRIVE_WRITE_SCOPE = "https://www.googleapis.com/auth/drive"
MUTATION_ENV = "FEDERATION_HERITAGE_REVISION_MUTATIONS"


class HeritageRevisionError(RuntimeError):
    """Base class for fail-closed historical revision recovery errors."""


class HeritageMutationDisabled(HeritageRevisionError):
    """Raised when a sticky provider mutation is attempted without explicit enablement."""


class HeritageIntegrityError(HeritageRevisionError):
    """Raised when provider bytes do not match the expected release identity."""


class HeritageRevisionNotPinned(HeritageRevisionError):
    """Raised when historical blob bytes are requested before keepForever is proven."""


@dataclass(frozen=True)
class VerifiedBytes:
    data: bytes
    size: int
    sha256: str


class HeritageRevisionAdapter:
    """Fail-closed Google Drive revision recovery for immutable heritage archives.

    This adapter deliberately lives beside the existing read-only Workspace adapter.
    It does not broaden that adapter's standing scope. Historical blob revisions are
    pinned only when ``FEDERATION_HERITAGE_REVISION_MUTATIONS=true`` (or an explicit
    constructor override is supplied), then downloaded, verified against the exact
    expected size/SHA-256, copied into a separate vault object, and downloaded again
    for readback verification.

    Archive creation is append-only: this code never overwrites or deletes a vault
    object. If a same-name object already exists, it is reused only when its bytes
    independently match the expected release hash.
    """

    REVISION_FIELDS = (
        "id,mimeType,modifiedTime,size,keepForever,originalFilename,md5Checksum"
    )
    FILE_FIELDS = "id,name,size,mimeType,md5Checksum,createdTime,modifiedTime"

    def __init__(
        self,
        drive_service: Any = None,
        *,
        allow_mutations: Optional[bool] = None,
        download_factory: Optional[Callable[[io.BytesIO, Any], Any]] = None,
        upload_factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        if allow_mutations is None:
            allow_mutations = os.getenv(MUTATION_ENV, "false").strip().lower() == "true"
        self.allow_mutations = bool(allow_mutations)

        if drive_service is None:
            import google.auth
            from googleapiclient.discovery import build

            scopes = [DRIVE_WRITE_SCOPE if self.allow_mutations else DRIVE_READ_SCOPE]
            credentials, _ = google.auth.default(scopes=scopes)
            drive_service = build(
                "drive", "v3", credentials=credentials, cache_discovery=False
            )
        self.drive = drive_service

        if download_factory is None:
            from googleapiclient.http import MediaIoBaseDownload

            download_factory = MediaIoBaseDownload
        if upload_factory is None:
            from googleapiclient.http import MediaIoBaseUpload

            upload_factory = MediaIoBaseUpload
        self._download_factory = download_factory
        self._upload_factory = upload_factory

    @staticmethod
    def _sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _escape_drive_query(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def revision_metadata(self, file_id: str, revision_id: str) -> Dict[str, Any]:
        if not file_id or not revision_id:
            raise ValueError("file_id and revision_id are required")
        return (
            self.drive.revisions()
            .get(fileId=file_id, revisionId=revision_id, fields=self.REVISION_FIELDS)
            .execute()
        )

    def ensure_keep_forever(self, file_id: str, revision_id: str) -> Dict[str, Any]:
        """Prove keepForever, setting it once only when explicit mutation is enabled."""
        before = self.revision_metadata(file_id, revision_id)
        if before.get("keepForever") is True:
            return {
                "state": "ALREADY_PINNED",
                "before": before,
                "after": before,
                "mutation_performed": False,
            }
        if not self.allow_mutations:
            raise HeritageMutationDisabled(
                f"Revision {revision_id} is not keepForever and {MUTATION_ENV} is not enabled"
            )

        self.drive.revisions().update(
            fileId=file_id,
            revisionId=revision_id,
            body={"keepForever": True},
            fields=self.REVISION_FIELDS,
        ).execute()
        after = self.revision_metadata(file_id, revision_id)
        if after.get("keepForever") is not True:
            raise HeritageRevisionError(
                f"Provider readback did not prove keepForever for revision {revision_id}"
            )
        return {
            "state": "PINNED_AND_READBACK_VERIFIED",
            "before": before,
            "after": after,
            "mutation_performed": True,
        }

    def _download_request(self, request: Any, *, max_bytes: int) -> bytes:
        buffer = io.BytesIO()
        downloader = self._download_factory(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
            if buffer.tell() > max_bytes:
                raise HeritageIntegrityError(
                    f"Download exceeded max_bytes={max_bytes}"
                )
        return buffer.getvalue()

    def _verified_bytes(
        self,
        data: bytes,
        *,
        expected_size: Optional[int],
        expected_sha256: Optional[str],
    ) -> VerifiedBytes:
        size = len(data)
        sha256 = self._sha256(data)
        if expected_size is not None and size != int(expected_size):
            raise HeritageIntegrityError(
                f"Byte-size mismatch: expected {expected_size}, got {size}"
            )
        if expected_sha256 is not None and sha256.lower() != expected_sha256.lower():
            raise HeritageIntegrityError(
                f"SHA-256 mismatch: expected {expected_sha256}, got {sha256}"
            )
        return VerifiedBytes(data=data, size=size, sha256=sha256)

    def download_revision(
        self,
        file_id: str,
        revision_id: str,
        *,
        expected_size: Optional[int] = None,
        expected_sha256: Optional[str] = None,
        max_bytes: int = 50_000_000,
    ) -> Tuple[VerifiedBytes, Dict[str, Any]]:
        metadata = self.revision_metadata(file_id, revision_id)
        if metadata.get("keepForever") is not True:
            raise HeritageRevisionNotPinned(
                f"Revision {revision_id} is not keepForever; historical bytes are not yet a safe recovery root"
            )
        request = self.drive.revisions().get_media(
            fileId=file_id, revisionId=revision_id
        )
        data = self._download_request(request, max_bytes=max_bytes)
        verified = self._verified_bytes(
            data,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
        )
        return verified, metadata

    def _download_file(
        self,
        file_id: str,
        *,
        expected_size: Optional[int],
        expected_sha256: Optional[str],
        max_bytes: int,
    ) -> VerifiedBytes:
        request = self.drive.files().get_media(fileId=file_id)
        data = self._download_request(request, max_bytes=max_bytes)
        return self._verified_bytes(
            data,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
        )

    def _find_existing_archive(
        self, parent_folder_id: str, destination_name: str
    ) -> Optional[Dict[str, Any]]:
        parent = self._escape_drive_query(parent_folder_id)
        name = self._escape_drive_query(destination_name)
        result = (
            self.drive.files()
            .list(
                q=f"'{parent}' in parents and name = '{name}' and trashed = false",
                fields=f"files({self.FILE_FIELDS})",
                pageSize=10,
            )
            .execute()
        )
        files = result.get("files", [])
        return files[0] if files else None

    def archive_revision_to_vault(
        self,
        *,
        source_file_id: str,
        revision_id: str,
        parent_folder_id: str,
        destination_name: str,
        expected_size: int,
        expected_sha256: str,
        mime_type: str = "application/zip",
        max_bytes: int = 50_000_000,
    ) -> Dict[str, Any]:
        """Pin, retrieve, verify, append to vault, and verify the new archive bytes."""
        if not all(
            [
                source_file_id,
                revision_id,
                parent_folder_id,
                destination_name,
                expected_sha256,
            ]
        ):
            raise ValueError("all recovery identities are required")

        pin = self.ensure_keep_forever(source_file_id, revision_id)
        source, source_meta = self.download_revision(
            source_file_id,
            revision_id,
            expected_size=expected_size,
            expected_sha256=expected_sha256,
            max_bytes=max_bytes,
        )

        existing = self._find_existing_archive(parent_folder_id, destination_name)
        if existing:
            archived = self._download_file(
                existing["id"],
                expected_size=expected_size,
                expected_sha256=expected_sha256,
                max_bytes=max_bytes,
            )
            archive_state = "EXISTING_EXACT_ARCHIVE_REUSED"
            archive_meta = existing
        else:
            if not self.allow_mutations:
                raise HeritageMutationDisabled(
                    f"Archive create requires {MUTATION_ENV}=true"
                )
            media = self._upload_factory(
                io.BytesIO(source.data), mimetype=mime_type, resumable=False
            )
            archive_meta = (
                self.drive.files()
                .create(
                    body={"name": destination_name, "parents": [parent_folder_id]},
                    media_body=media,
                    fields=self.FILE_FIELDS,
                )
                .execute()
            )
            archived = self._download_file(
                archive_meta["id"],
                expected_size=expected_size,
                expected_sha256=expected_sha256,
                max_bytes=max_bytes,
            )
            archive_state = "NEW_ARCHIVE_CREATED_READBACK_VERIFIED"

        return {
            "operation": "HERITAGE_REVISION_RECOVERY",
            "source_file_id": source_file_id,
            "source_revision_id": revision_id,
            "source_original_filename": source_meta.get("originalFilename"),
            "source_keep_forever": source_meta.get("keepForever"),
            "pin_state": pin["state"],
            "pin_mutation_performed": pin["mutation_performed"],
            "source_size": source.size,
            "source_sha256": source.sha256,
            "archive_file_id": archive_meta["id"],
            "archive_name": archive_meta.get("name", destination_name),
            "archive_state": archive_state,
            "archive_size": archived.size,
            "archive_sha256": archived.sha256,
            "integrity": "VERIFIED",
            "overwrite_performed": False,
            "provider_authority_inherited": False,
        }
