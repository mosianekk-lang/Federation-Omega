"""Federation Adobe Ω mailbox ingestion and batch PDF conversion v1.

Pure/provider-neutral adapters bridge read-only Gmail and Microsoft Outlook message
shapes into the existing Adobe Ω email print runtime.  This module performs no
mailbox mutation and does not contain provider credentials or connector calls.

Gmail's preferred path is original RFC 5322 MIME because it preserves the source
message most faithfully.  Outlook's connector shape is normalized into
``EmailMessageView`` because the available read surface exposes body and metadata
rather than RFC 822 bytes.

The batch converter is bounded, deterministic and fail-closed: it rejects duplicate
provider message identities, sanitizes output names, caps batch size, invokes the
existing renderer once per message, and emits a manifest whose entries are bound to
semantic PDF readback receipts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from federation.adobe_omega_email_print_v1 import (
    AttachmentInfo,
    EmailMessageView,
    EmailPrintProfile,
    EmailPrintReceipt,
    parse_rfc822,
    render_email_views,
)

SCHEMA = "FEDERATION_ADOBE_OMEGA_MAILBOX_BATCH_V1"
VERSION = "1.0.0"


class MailProvider(str, Enum):
    GMAIL = "GMAIL"
    OUTLOOK = "OUTLOOK"


@dataclass(frozen=True, slots=True)
class MailboxMessage:
    provider: MailProvider
    provider_message_id: str
    provider_thread_id: str
    internet_message_id: str
    view: EmailMessageView
    source_bytes: bytes = b""

    def validate(self) -> "MailboxMessage":
        if not self.provider_message_id.strip():
            raise ValueError("provider_message_id is required")
        if not self.view.subject and not self.view.text_body and not self.view.html_body:
            raise ValueError("message must contain subject or body")
        return self


@dataclass(frozen=True, slots=True)
class BatchItemReceipt:
    provider: str
    provider_message_id: str
    internet_message_id: str
    output_name: str
    pdf_sha256: str
    page_count: int
    semantic_readback_verified: bool
    renderer_receipt_sha256: str


@dataclass(frozen=True, slots=True)
class MailboxBatchReceipt:
    schema: str
    version: str
    requested_count: int
    converted_count: int
    failed_count: int
    provider_counts: tuple[tuple[str, int], ...]
    items: tuple[BatchItemReceipt, ...]
    provider_effect_performed: bool
    receipt_sha256: str


def _stable(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _digest(value: object) -> str:
    return sha256(_stable(value)).hexdigest()


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Mapping):
        if "emailAddress" in value:
            return _as_text(value.get("emailAddress"))
        address = value.get("address") or value.get("email") or ""
        name = value.get("name") or ""
        return f"{name} <{address}>".strip() if name and address else str(address or name)
    if isinstance(value, (list, tuple)):
        return ", ".join(filter(None, (_as_text(item) for item in value)))
    return str(value)


def _attachment_info(raw: Mapping[str, Any]) -> AttachmentInfo:
    filename = str(raw.get("filename") or raw.get("name") or "attachment")
    content_type = str(raw.get("mime_type") or raw.get("contentType") or raw.get("content_type") or "application/octet-stream")
    size = int(raw.get("size") or raw.get("size_bytes") or 0)
    cid = raw.get("content_id") or raw.get("contentId")
    inline = bool(raw.get("inline") or raw.get("isInline"))
    return AttachmentInfo(
        filename=filename,
        content_type=content_type,
        size_bytes=max(0, size),
        content_id=str(cid).strip("<>") if cid else None,
        inline=inline,
        payload=b"",
    )


def gmail_connector_message(raw: Mapping[str, Any]) -> MailboxMessage:
    """Normalize one Gmail connector read result.

    Prefer ``raw_mime`` when supplied because it preserves MIME boundaries,
    Message-ID, HTML and attachment metadata exactly as exposed by the connector.
    """
    provider_id = str(raw.get("id") or raw.get("message_id") or "").strip()
    thread_id = str(raw.get("thread_id") or "").strip()
    raw_mime = raw.get("raw_mime")
    if raw_mime:
        source = raw_mime if isinstance(raw_mime, bytes) else str(raw_mime).encode("utf-8", errors="surrogatepass")
        view = parse_rfc822(source)
        internet_id = view.message_id
    else:
        source = b""
        attachments = tuple(
            _attachment_info(item)
            for item in (raw.get("attachments") or ())
            if isinstance(item, Mapping)
        )
        view = EmailMessageView(
            subject=str(raw.get("subject") or ""),
            from_=_as_text(raw.get("from_") or raw.get("from")),
            to=_as_text(raw.get("to")),
            cc=_as_text(raw.get("cc")),
            date=str(raw.get("email_ts") or raw.get("date") or ""),
            message_id=str(raw.get("message_id_header") or raw.get("internet_message_id") or ""),
            html_body=str(raw.get("html_body") or ""),
            text_body=str(raw.get("body") or raw.get("snippet") or ""),
            attachments=attachments,
        )
        internet_id = view.message_id
    return MailboxMessage(
        provider=MailProvider.GMAIL,
        provider_message_id=provider_id,
        provider_thread_id=thread_id,
        internet_message_id=internet_id,
        view=view,
        source_bytes=source,
    ).validate()


def outlook_connector_message(raw: Mapping[str, Any]) -> MailboxMessage:
    """Normalize one Microsoft Outlook connector/Graph-style message result."""
    provider_id = str(raw.get("id") or raw.get("message_id") or "").strip()
    body = raw.get("body")
    html_body = ""
    text_body = ""
    if isinstance(body, Mapping):
        content = str(body.get("content") or "")
        content_type = str(body.get("contentType") or body.get("content_type") or "").lower()
        if content_type == "html":
            html_body = content
        else:
            text_body = content
    elif body:
        text_body = str(body)

    if not html_body and not text_body:
        text_body = str(
            raw.get("body_preview")
            or raw.get("bodyPreview")
            or raw.get("preview")
            or raw.get("snippet")
            or ""
        )

    sender = raw.get("from") or raw.get("from_") or raw.get("sender")
    attachments = tuple(
        _attachment_info(item)
        for item in (raw.get("attachments") or ())
        if isinstance(item, Mapping)
    )
    view = EmailMessageView(
        subject=str(raw.get("subject") or ""),
        from_=_as_text(sender),
        to=_as_text(raw.get("toRecipients") or raw.get("to_recipients") or raw.get("to")),
        cc=_as_text(raw.get("ccRecipients") or raw.get("cc_recipients") or raw.get("cc")),
        date=str(raw.get("receivedDateTime") or raw.get("received_datetime") or raw.get("sentDateTime") or raw.get("date") or ""),
        message_id=str(raw.get("internet_message_id") or raw.get("internetMessageId") or ""),
        html_body=html_body,
        text_body=text_body,
        attachments=attachments,
    )
    return MailboxMessage(
        provider=MailProvider.OUTLOOK,
        provider_message_id=provider_id,
        provider_thread_id=str(raw.get("conversationId") or raw.get("conversation_id") or "").strip(),
        internet_message_id=view.message_id,
        view=view,
        source_bytes=b"",
    ).validate()


def _safe_stem(subject: str, provider_message_id: str) -> str:
    text = (subject or "email").strip()
    text = re.sub(r"[^\w.\- ]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip(" ._")
    text = text[:90] or "email"
    suffix = sha256(provider_message_id.encode("utf-8")).hexdigest()[:10]
    return f"{text}__{suffix}"


def convert_mailbox_batch(
    messages: Sequence[MailboxMessage],
    output_dir: str | Path,
    profile: EmailPrintProfile = EmailPrintProfile(),
    *,
    max_messages: int = 250,
) -> MailboxBatchReceipt:
    """Convert a bounded set of already-read messages to individual PDFs.

    No connector calls occur here. Inputs are immutable read results supplied by a
    host. A single message failure fails the batch call instead of silently
    producing a partial success claim.
    """
    if max_messages < 1 or max_messages > 1000:
        raise ValueError("max_messages must be between 1 and 1000")
    if len(messages) > max_messages:
        raise ValueError("batch exceeds max_messages")
    if not messages:
        raise ValueError("at least one message is required")

    seen: set[tuple[str, str]] = set()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    items: list[BatchItemReceipt] = []
    counts: dict[str, int] = {}

    for message in messages:
        message.validate()
        key = (message.provider.value, message.provider_message_id)
        if key in seen:
            raise ValueError(f"duplicate provider message identity: {key[0]}:{key[1]}")
        seen.add(key)
        name = _safe_stem(message.view.subject, message.provider_message_id) + ".pdf"
        path = out / name
        receipt: EmailPrintReceipt = render_email_views(
            (message.view,),
            path,
            profile,
            source_bytes=message.source_bytes or None,
        )
        if not receipt.semantic_readback_verified:
            raise RuntimeError(f"semantic PDF readback failed for {message.provider_message_id}")
        items.append(
            BatchItemReceipt(
                provider=message.provider.value,
                provider_message_id=message.provider_message_id,
                internet_message_id=message.internet_message_id,
                output_name=name,
                pdf_sha256=receipt.pdf_sha256,
                page_count=receipt.page_count,
                semantic_readback_verified=receipt.semantic_readback_verified,
                renderer_receipt_sha256=receipt.receipt_sha256,
            )
        )
        counts[message.provider.value] = counts.get(message.provider.value, 0) + 1

    material = {
        "schema": SCHEMA,
        "version": VERSION,
        "requested_count": len(messages),
        "converted_count": len(items),
        "failed_count": 0,
        "provider_counts": tuple(sorted(counts.items())),
        "items": tuple(asdict(item) for item in items),
        "provider_effect_performed": False,
    }
    return MailboxBatchReceipt(
        schema=SCHEMA,
        version=VERSION,
        requested_count=len(messages),
        converted_count=len(items),
        failed_count=0,
        provider_counts=tuple(sorted(counts.items())),
        items=tuple(items),
        provider_effect_performed=False,
        receipt_sha256=_digest(material),
    )


__all__ = [
    "BatchItemReceipt",
    "MailProvider",
    "MailboxBatchReceipt",
    "MailboxMessage",
    "convert_mailbox_batch",
    "gmail_connector_message",
    "outlook_connector_message",
]
