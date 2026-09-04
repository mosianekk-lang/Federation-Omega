from __future__ import annotations

import base64
import hashlib
import mimetypes
import zipfile
from contextlib import suppress
from dataclasses import dataclass
from email import policy
from email.message import Message
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from .schemas import InventoryItem, InventoryResult, ProofAppendRequest, ProofType


class InventoryLimitExceeded(ValueError):
    pass


@dataclass(frozen=True)
class InventoryLimits:
    max_file_bytes: int = 250 * 1024 * 1024
    max_parts: int = 20_000
    max_depth: int = 32
    max_decoded_bytes: int = 2 * 1024 * 1024 * 1024
    max_zip_entries: int = 20_000
    max_zip_expanded_bytes: int = 4 * 1024 * 1024 * 1024
    max_zip_ratio: float = 200.0

    def as_dict(self) -> dict[str, int | float]:
        return {
            "max_file_bytes": self.max_file_bytes,
            "max_parts": self.max_parts,
            "max_depth": self.max_depth,
            "max_decoded_bytes": self.max_decoded_bytes,
            "max_zip_entries": self.max_zip_entries,
            "max_zip_expanded_bytes": self.max_zip_expanded_bytes,
            "max_zip_ratio": self.max_zip_ratio,
        }


@dataclass
class _Budget:
    limits: InventoryLimits
    parts: int = 0
    decoded_bytes: int = 0

    def consume(self, *, size: int, depth: int) -> None:
        self.parts += 1
        self.decoded_bytes += size
        if self.parts > self.limits.max_parts:
            raise InventoryLimitExceeded("MIME part limit exceeded")
        if self.decoded_bytes > self.limits.max_decoded_bytes:
            raise InventoryLimitExceeded("Decoded-byte limit exceeded")
        if depth > self.limits.max_depth:
            raise InventoryLimitExceeded("MIME nesting depth exceeded")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_bytes(part: Message) -> bytes:
    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload
    raw = part.get_payload()
    if isinstance(raw, str):
        return raw.encode(part.get_content_charset() or "utf-8", errors="replace")
    return part.as_bytes(policy=policy.default)


def _nested_messages_and_raw(part: Message) -> tuple[list[Message], bytes]:
    payload = part.get_payload()
    cte = (part.get("Content-Transfer-Encoding") or "").lower()
    if isinstance(payload, list):
        nested = [item for item in payload if isinstance(item, Message)]
        if cte == "base64" and len(nested) == 1:
            encoded = nested[0].get_payload()
            if isinstance(encoded, str):
                with suppress(Exception):
                    raw = base64.b64decode("".join(encoded.split()), validate=False)
                    return [BytesParser(policy=policy.default).parsebytes(raw)], raw
        raw = b"\n".join(item.as_bytes(policy=policy.default) for item in nested)
        return nested, raw
    if isinstance(payload, str):
        raw = payload.encode(part.get_content_charset() or "utf-8", errors="replace")
        if cte == "base64":
            with suppress(Exception):
                raw = base64.b64decode("".join(payload.split()), validate=False)
        try:
            return [BytesParser(policy=policy.default).parsebytes(raw)], raw
        except Exception:
            return [], raw
    raw = part.as_bytes(policy=policy.default)
    return [], raw


def _walk_message(
    message: Message,
    *,
    parent_id: str | None,
    depth: int,
    items: list[InventoryItem],
    top_message: bool,
    budget: _Budget,
) -> None:
    if depth > budget.limits.max_depth:
        raise InventoryLimitExceeded("MIME nesting depth exceeded")
    parts = list(message.iter_parts()) if message.is_multipart() else []  # type: ignore[attr-defined]
    for index, part in enumerate(parts):
        content_type = part.get_content_type()
        disposition = part.get_content_disposition()
        filename = part.get_filename()
        content_id = part.get("Content-ID")
        is_inline = disposition == "inline" or (content_id is not None and disposition != "attachment")

        if content_type == "message/rfc822":
            nested_messages, raw = _nested_messages_and_raw(part)
            budget.consume(size=len(raw), depth=depth)
            item_id = f"occ-{uuid4().hex}"
            items.append(
                InventoryItem(
                    occurrence_id=item_id,
                    parent_id=parent_id,
                    depth=depth,
                    filename=filename or f"nested-message-{index + 1}.eml",
                    content_type=content_type,
                    size_bytes=len(raw),
                    sha256=sha256_bytes(raw),
                    disposition=disposition,
                    content_id=content_id,
                    top_level=top_message,
                    inline=is_inline,
                )
            )
            for nested in nested_messages:
                _walk_message(
                    nested,
                    parent_id=item_id,
                    depth=depth + 1,
                    items=items,
                    top_message=False,
                    budget=budget,
                )
            continue

        is_file_bearing = bool(filename) or disposition == "attachment" or is_inline
        if is_file_bearing:
            raw = _payload_bytes(part)
            budget.consume(size=len(raw), depth=depth)
            item_id = f"occ-{uuid4().hex}"
            items.append(
                InventoryItem(
                    occurrence_id=item_id,
                    parent_id=parent_id,
                    depth=depth,
                    filename=filename or f"inline-{index + 1}",
                    content_type=content_type,
                    size_bytes=len(raw),
                    sha256=sha256_bytes(raw),
                    disposition=disposition,
                    content_id=content_id,
                    top_level=top_message,
                    inline=is_inline,
                )
            )

        if part.is_multipart():
            _walk_message(
                part,
                parent_id=parent_id,
                depth=depth,
                items=items,
                top_message=top_message,
                budget=budget,
            )


def inventory_eml(
    path: Path,
    application_visible_count: int | None = None,
    application_attachment_count: int | None = None,
    application_inline_count: int | None = None,
    *,
    limits: InventoryLimits | None = None,
) -> InventoryResult:
    limits = limits or InventoryLimits()
    if path.stat().st_size > limits.max_file_bytes:
        raise InventoryLimitExceeded("Carrier exceeds configured maximum file size")
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    items: list[InventoryItem] = []
    budget = _Budget(limits)
    _walk_message(
        message,
        parent_id=None,
        depth=1,
        items=items,
        top_message=True,
        budget=budget,
    )
    top_level_count = sum(item.top_level for item in items)
    unique_content_count = len({item.sha256 for item in items})
    recursive_count = len(items)
    native_inline_count = sum(item.inline for item in items)
    native_attachment_count = recursive_count - native_inline_count
    duplicate_count = recursive_count - unique_content_count

    if (
        application_visible_count is None
        and application_attachment_count is not None
        and application_inline_count is not None
    ):
        application_visible_count = application_attachment_count + application_inline_count

    comparisons: list[bool] = []
    if application_attachment_count is not None:
        comparisons.append(application_attachment_count == native_attachment_count)
    if application_inline_count is not None:
        comparisons.append(application_inline_count == native_inline_count)
    if application_visible_count is not None and application_attachment_count is None and application_inline_count is None:
        comparisons.append(application_visible_count == recursive_count)

    completeness: Literal["VERIFIED", "VERIFIED_WITH_CATEGORY_DIFFERENCE", "UNVERIFIED"]
    if comparisons:
        category_match = all(comparisons)
        total_match = application_visible_count == recursive_count if application_visible_count is not None else category_match
        content_id_attachment_images = sum(
            item.content_type.startswith("image/") and item.content_id is not None and not item.inline
            for item in items
        )
        if category_match:
            completeness = "VERIFIED"
            category_note = "category counts match"
        elif total_match:
            completeness = "VERIFIED_WITH_CATEGORY_DIFFERENCE"
            category_note = (
                "total counts match while category labels differ; "
                f"{content_id_attachment_images} native content-ID image part(s) may be surfaced inline by the application. "
                "This is a representation difference, not proof of loss, omission or alteration"
            )
        else:
            completeness = "UNVERIFIED"
            category_note = "total counts do not match; complete reconciliation has not been established"
        reconciliation = (
            f"Native MIME: {top_level_count} top-level, {native_attachment_count} recursive attachment-designated "
            f"instances and {native_inline_count} inline-designated instances ({recursive_count} total); application: "
            f"{application_attachment_count if application_attachment_count is not None else 'not supplied'} attachments "
            f"and {application_inline_count if application_inline_count is not None else 'not supplied'} inline items "
            f"({application_visible_count if application_visible_count is not None else 'total not supplied'} total); "
            f"{category_note}."
        )
    else:
        reconciliation = (
            f"Native MIME: {top_level_count} top-level, {native_attachment_count} recursive attachment instances and "
            f"{native_inline_count} inline instances ({recursive_count} total), with {unique_content_count} unique contents. "
            "Application-visible category counts were not supplied, so cross-platform reconciliation remains untested."
        )
        completeness = "VERIFIED"

    return InventoryResult(
        carrier_path=str(path),
        carrier_type="message/rfc822",
        top_level_count=top_level_count,
        recursive_instance_count=recursive_count,
        native_attachment_instance_count=native_attachment_count,
        native_inline_instance_count=native_inline_count,
        application_visible_count=application_visible_count,
        application_attachment_count=application_attachment_count,
        application_inline_count=application_inline_count,
        unique_content_count=unique_content_count,
        duplicate_instance_count=duplicate_count,
        items=items,
        count_reconciliation=reconciliation,
        completeness_state=completeness,
        limits_applied=limits.as_dict(),
    )


def inventory_zip(path: Path, *, limits: InventoryLimits | None = None) -> InventoryResult:
    limits = limits or InventoryLimits()
    if path.stat().st_size > limits.max_file_bytes:
        raise InventoryLimitExceeded("ZIP carrier exceeds configured maximum file size")
    items: list[InventoryItem] = []
    expanded = 0
    with zipfile.ZipFile(path) as archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        if len(members) > limits.max_zip_entries:
            raise InventoryLimitExceeded("ZIP entry count limit exceeded")
        for member in members:
            expanded += int(member.file_size)
            if expanded > limits.max_zip_expanded_bytes:
                raise InventoryLimitExceeded("ZIP expanded-byte limit exceeded")
            compressed = max(int(member.compress_size), 1)
            ratio = float(member.file_size) / compressed
            if ratio > limits.max_zip_ratio:
                raise InventoryLimitExceeded("ZIP expansion-ratio limit exceeded")
            depth = len(Path(member.filename).parts)
            if depth > limits.max_depth:
                raise InventoryLimitExceeded("ZIP path depth limit exceeded")
            data = archive.read(member)
            content_type = mimetypes.guess_type(member.filename)[0] or "application/octet-stream"
            items.append(
                InventoryItem(
                    occurrence_id=f"occ-{uuid4().hex}",
                    depth=depth,
                    filename=member.filename,
                    content_type=content_type,
                    size_bytes=len(data),
                    sha256=sha256_bytes(data),
                    top_level=depth == 1,
                )
            )
    unique = len({item.sha256 for item in items})
    return InventoryResult(
        carrier_path=str(path),
        carrier_type="application/zip",
        top_level_count=sum(item.top_level for item in items),
        recursive_instance_count=len(items),
        native_attachment_instance_count=len(items),
        native_inline_instance_count=0,
        unique_content_count=unique,
        duplicate_instance_count=len(items) - unique,
        items=items,
        count_reconciliation=(
            f"ZIP: {sum(item.top_level for item in items)} top-level files, {len(items)} recursive instances, "
            f"{unique} unique contents and {expanded} expanded bytes."
        ),
        completeness_state="VERIFIED",
        limits_applied=limits.as_dict(),
    )


def inventory_directory(path: Path, *, limits: InventoryLimits | None = None) -> InventoryResult:
    limits = limits or InventoryLimits()
    files = sorted(p for p in path.rglob("*") if p.is_file())
    if len(files) > limits.max_parts:
        raise InventoryLimitExceeded("Directory file-count limit exceeded")
    items: list[InventoryItem] = []
    total = 0
    for file_path in files:
        relative = file_path.relative_to(path)
        depth = len(relative.parts)
        if depth > limits.max_depth:
            raise InventoryLimitExceeded("Directory depth limit exceeded")
        size = file_path.stat().st_size
        total += size
        if total > limits.max_decoded_bytes:
            raise InventoryLimitExceeded("Directory total-byte limit exceeded")
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        items.append(
            InventoryItem(
                occurrence_id=f"occ-{uuid4().hex}",
                depth=depth,
                filename=str(relative),
                content_type=content_type,
                size_bytes=size,
                sha256=sha256_file(file_path),
                top_level=depth == 1,
            )
        )
    unique = len({item.sha256 for item in items})
    return InventoryResult(
        carrier_path=str(path),
        carrier_type="inode/directory",
        top_level_count=sum(item.top_level for item in items),
        recursive_instance_count=len(items),
        native_attachment_instance_count=len(items),
        native_inline_instance_count=0,
        unique_content_count=unique,
        duplicate_instance_count=len(items) - unique,
        items=items,
        count_reconciliation=(
            f"Directory: {sum(item.top_level for item in items)} top-level files, {len(items)} recursive instances, "
            f"{unique} unique contents and {total} bytes."
        ),
        completeness_state="VERIFIED",
        limits_applied=limits.as_dict(),
    )


def inventory_path(
    path: Path,
    application_visible_count: int | None = None,
    application_attachment_count: int | None = None,
    application_inline_count: int | None = None,
    *,
    limits: InventoryLimits | None = None,
) -> InventoryResult:
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    limits = limits or InventoryLimits()
    if path.is_dir():
        return inventory_directory(path, limits=limits)
    suffix = path.suffix.lower()
    if suffix == ".eml":
        return inventory_eml(
            path,
            application_visible_count=application_visible_count,
            application_attachment_count=application_attachment_count,
            application_inline_count=application_inline_count,
            limits=limits,
        )
    if suffix == ".zip":
        return inventory_zip(path, limits=limits)
    if path.stat().st_size > limits.max_file_bytes:
        raise InventoryLimitExceeded("File exceeds configured maximum")
    item = InventoryItem(
        occurrence_id=f"occ-{uuid4().hex}",
        depth=1,
        filename=path.name,
        content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
        top_level=True,
    )
    return InventoryResult(
        carrier_path=str(path),
        carrier_type=item.content_type,
        top_level_count=1,
        recursive_instance_count=1,
        native_attachment_instance_count=1,
        native_inline_instance_count=0,
        unique_content_count=1,
        duplicate_instance_count=0,
        items=[item],
        count_reconciliation="Single native file; top-level and recursive counts are both 1.",
        completeness_state="VERIFIED",
        limits_applied=limits.as_dict(),
    )


def inventory_proof_payload(result: InventoryResult) -> dict[str, object]:
    return {
        "carrier_path": result.carrier_path,
        "carrier_type": result.carrier_type,
        "top_level_count": result.top_level_count,
        "recursive_instance_count": result.recursive_instance_count,
        "native_attachment_instance_count": result.native_attachment_instance_count,
        "native_inline_instance_count": result.native_inline_instance_count,
        "application_visible_count": result.application_visible_count,
        "application_attachment_count": result.application_attachment_count,
        "application_inline_count": result.application_inline_count,
        "unique_content_count": result.unique_content_count,
        "duplicate_instance_count": result.duplicate_instance_count,
        "completeness_state": result.completeness_state,
        "item_hashes": [item.sha256 for item in result.items],
        "count_reconciliation": result.count_reconciliation,
        "limits_applied": result.limits_applied,
    }


def append_inventory_proof(
    ledger: Any,
    *,
    matter_id: str,
    mission_id: str,
    subject_id: str,
    actor_id: str,
    source_ids: list[str],
    result: InventoryResult,
) -> str:
    proof = ledger.append(
        ProofAppendRequest(
            matter_id=matter_id,
            mission_id=mission_id,
            proof_type=ProofType.INVENTORY_RECONCILIATION,
            subject_id=subject_id,
            actor_id=actor_id,
            source_ids=source_ids,
            payload=inventory_proof_payload(result),
        )
    )
    return str(proof.proof_id)
