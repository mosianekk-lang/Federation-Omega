"""Federation Adobe Ω email print-to-PDF runtime v1.

Provider-neutral email -> print-ready PDF execution using the repository's existing
PyMuPDF dependency.  The runtime accepts RFC 5322 messages or normalized email
views, preserves evidentiary headers, sanitizes active HTML, resolves CID inline
images locally, renders A4/Letter/Legal portrait or landscape, supports margins,
scale, backgrounds, page ranges, headers/footers and attachment manifests, and
then independently re-opens the PDF for semantic readback.

No Gmail/Outlook/Adobe browser session is required.  Remote images are blocked by
default to prevent tracking and unapproved disclosure.  This is an email-print
runtime, not a claim of prepress/PDF-X compliance.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from email import policy
from email.parser import BytesParser
from hashlib import sha256
from html import escape
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import tempfile
from typing import Iterable, Mapping, Sequence
from urllib.parse import urlparse


SCHEMA = "FEDERATION_ADOBE_OMEGA_EMAIL_PRINT_V1"
PT_PER_MM = 72.0 / 25.4


@dataclass(frozen=True, slots=True)
class AttachmentInfo:
    filename: str
    content_type: str
    size_bytes: int
    content_id: str | None = None
    inline: bool = False
    payload: bytes = field(default=b"", repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class EmailMessageView:
    subject: str
    from_: str
    to: str
    cc: str
    date: str
    message_id: str
    html_body: str
    text_body: str
    attachments: tuple[AttachmentInfo, ...] = ()


@dataclass(frozen=True, slots=True)
class EmailPrintProfile:
    paper: str = "A4"
    orientation: str = "PORTRAIT"
    margin_top_mm: float = 14.0
    margin_right_mm: float = 14.0
    margin_bottom_mm: float = 16.0
    margin_left_mm: float = 14.0
    scale: float = 1.0
    print_backgrounds: bool = True
    display_header_footer: bool = True
    include_attachment_manifest: bool = True
    allow_remote_images: bool = False
    page_ranges: str = ""
    base_font_pt: float = 10.0

    def validate(self) -> "EmailPrintProfile":
        if self.paper.upper() not in {"A4", "LETTER", "LEGAL"}:
            raise ValueError("paper must be A4, LETTER or LEGAL")
        if self.orientation.upper() not in {"PORTRAIT", "LANDSCAPE"}:
            raise ValueError("orientation must be PORTRAIT or LANDSCAPE")
        if not 0.1 <= float(self.scale) <= 2.0:
            raise ValueError("scale must be between 0.1 and 2.0")
        if not 6 <= float(self.base_font_pt) <= 20:
            raise ValueError("base_font_pt must be between 6 and 20")
        margins = (
            self.margin_top_mm,
            self.margin_right_mm,
            self.margin_bottom_mm,
            self.margin_left_mm,
        )
        if any(float(value) < 0 or float(value) > 50 for value in margins):
            raise ValueError("margins must be between 0 and 50 mm")
        _parse_page_ranges(self.page_ranges, max_pages=None)
        return self

    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EmailPrintReceipt:
    schema: str
    source_sha256: str
    pdf_sha256: str
    profile_sha256: str
    page_count: int
    selected_page_count: int
    paper: str
    orientation: str
    page_width_pt: float
    page_height_pt: float
    attachment_count: int
    inline_image_count: int
    header_fields_present: tuple[str, ...]
    extracted_text_sha256: str
    semantic_readback_verified: bool
    active_content_removed: bool
    remote_images_blocked: int
    provider_effect_performed: bool
    receipt_sha256: str


class _EmailHTMLSanitizer(HTMLParser):
    SKIP_TAGS = {"script", "style", "iframe", "object", "embed", "form", "input", "button", "video", "audio"}
    ALLOWED_TAGS = {
        "p", "div", "span", "br", "hr", "b", "strong", "i", "em", "u", "s",
        "blockquote", "pre", "code", "ul", "ol", "li", "table", "thead", "tbody",
        "tfoot", "tr", "td", "th", "a", "img", "h1", "h2", "h3", "h4", "h5", "h6",
    }
    STYLE_ALLOW = {
        "color", "background-color", "font-weight", "font-style", "font-size",
        "font-family", "text-align", "text-decoration", "border", "border-width",
        "border-style", "border-color", "border-collapse", "padding", "padding-left",
        "padding-right", "padding-top", "padding-bottom", "margin", "margin-left",
        "margin-right", "margin-top", "margin-bottom", "white-space", "width",
        "max-width", "height", "vertical-align", "line-height",
    }

    def __init__(self, *, allow_remote_images: bool, cid_map: Mapping[str, str]):
        super().__init__(convert_charrefs=True)
        self.allow_remote_images = bool(allow_remote_images)
        self.cid_map = {str(key).strip("<>"): value for key, value in cid_map.items()}
        self.parts: list[str] = []
        self.skip_depth = 0
        self.active_content_removed = False
        self.remote_images_blocked = 0

    @classmethod
    def _clean_style(cls, value: str) -> str:
        if "url(" in value.lower() or "expression" in value.lower() or "javascript:" in value.lower():
            return ""
        clean: list[str] = []
        for declaration in value.split(";"):
            if ":" not in declaration:
                continue
            prop, val = declaration.split(":", 1)
            prop = prop.strip().lower()
            val = val.strip()
            if prop in cls.STYLE_ALLOW and val:
                clean.append(f"{prop}:{val}")
        return ";".join(clean)

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            self.active_content_removed = True
            return
        if self.skip_depth or tag not in self.ALLOWED_TAGS:
            return
        clean_attrs: list[tuple[str, str]] = []
        attr_map = {str(k).lower(): str(v or "") for k, v in attrs}
        if tag == "a":
            href = attr_map.get("href", "")
            scheme = urlparse(href).scheme.lower()
            if href and scheme in {"http", "https", "mailto"}:
                clean_attrs.append(("href", href))
        elif tag == "img":
            src = attr_map.get("src", "")
            alt = attr_map.get("alt", "image")
            if src.lower().startswith("cid:"):
                cid = src[4:].strip("<>")
                mapped = self.cid_map.get(cid)
                if mapped:
                    clean_attrs.append(("src", mapped))
                else:
                    self.parts.append(f"<span class='image-placeholder'>[{escape(alt)}]</span>")
                    return
            elif self.allow_remote_images and urlparse(src).scheme.lower() in {"http", "https"}:
                clean_attrs.append(("src", src))
            else:
                self.remote_images_blocked += 1
                self.parts.append(f"<span class='image-placeholder'>[{escape(alt)}]</span>")
                return
            clean_attrs.append(("alt", alt))
        for key in ("colspan", "rowspan", "width", "height", "title"):
            if key in attr_map and tag in {"td", "th", "img", "table", "a"}:
                clean_attrs.append((key, attr_map[key]))
        style = self._clean_style(attr_map.get("style", ""))
        if style:
            clean_attrs.append(("style", style))
        rendered = "".join(f" {escape(k)}=\"{escape(v, quote=True)}\"" for k, v in clean_attrs)
        self.parts.append(f"<{tag}{rendered}>")

    def handle_startendtag(self, tag: str, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in {"br", "hr", "img"}:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if not self.skip_depth and tag in self.ALLOWED_TAGS and tag not in {"br", "hr", "img"}:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str):
        if not self.skip_depth:
            self.parts.append(escape(data))

    def html(self) -> str:
        return "".join(self.parts)


def _safe_header(value: object) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_rfc822(data: bytes) -> EmailMessageView:
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ValueError("non-empty RFC 5322 bytes are required")
    msg = BytesParser(policy=policy.default).parsebytes(bytes(data))
    html_body = ""
    text_body = ""
    attachments: list[AttachmentInfo] = []

    for part in msg.walk():
        if part.is_multipart():
            continue
        ctype = part.get_content_type().lower()
        disposition = part.get_content_disposition()
        filename = _safe_header(part.get_filename())
        cid = _safe_header(part.get("Content-ID")).strip("<>") or None
        payload = part.get_payload(decode=True) or b""
        is_attachment = disposition == "attachment" or bool(filename)
        is_inline = disposition == "inline" or bool(cid)

        if ctype == "text/html" and not is_attachment and not html_body:
            try:
                html_body = str(part.get_content())
            except Exception:
                html_body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            continue
        if ctype == "text/plain" and not is_attachment and not text_body:
            try:
                text_body = str(part.get_content())
            except Exception:
                text_body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            continue
        if payload or filename or cid:
            attachments.append(
                AttachmentInfo(
                    filename=filename or (cid and f"inline-{cid}") or "attachment",
                    content_type=ctype,
                    size_bytes=len(payload),
                    content_id=cid,
                    inline=is_inline,
                    payload=payload,
                )
            )

    return EmailMessageView(
        subject=_safe_header(msg.get("Subject")),
        from_=_safe_header(msg.get("From")),
        to=_safe_header(msg.get("To")),
        cc=_safe_header(msg.get("Cc")),
        date=_safe_header(msg.get("Date")),
        message_id=_safe_header(msg.get("Message-ID")),
        html_body=html_body,
        text_body=text_body,
        attachments=tuple(attachments),
    )


def _paper_rect(pymupdf, profile: EmailPrintProfile):
    rect = pymupdf.paper_rect(profile.paper.lower())
    if profile.orientation.upper() == "LANDSCAPE":
        rect = pymupdf.Rect(0, 0, rect.height, rect.width)
    return rect


def _parse_page_ranges(value: str, max_pages: int | None) -> tuple[int, ...]:
    value = (value or "").strip()
    if not value:
        return tuple(range(1, max_pages + 1)) if max_pages is not None else ()
    result: list[int] = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            left, right = token.split("-", 1)
            if not left.isdigit() or not right.isdigit():
                raise ValueError("invalid page range")
            start, end = int(left), int(right)
            if start < 1 or end < start:
                raise ValueError("invalid page range")
            values = range(start, end + 1)
        else:
            if not token.isdigit() or int(token) < 1:
                raise ValueError("invalid page range")
            values = (int(token),)
        for page in values:
            if max_pages is None or page <= max_pages:
                if page not in result:
                    result.append(page)
    if max_pages is not None and not result:
        raise ValueError("page range selects no pages")
    return tuple(result)


def _attachment_manifest(view: EmailMessageView) -> str:
    if not view.attachments:
        return ""
    rows = []
    for item in view.attachments:
        rows.append(
            "<tr>"
            f"<td>{escape(item.filename)}</td>"
            f"<td>{escape(item.content_type)}</td>"
            f"<td>{item.size_bytes}</td>"
            f"<td>{'inline' if item.inline else 'attachment'}</td>"
            "</tr>"
        )
    return (
        "<section class='attachments'><h3>Attachments</h3>"
        "<table><thead><tr><th>Name</th><th>Type</th><th>Bytes</th><th>Disposition</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></section>"
    )


def _header_table(view: EmailMessageView) -> str:
    fields = (
        ("From", view.from_), ("To", view.to), ("Cc", view.cc),
        ("Date", view.date), ("Subject", view.subject), ("Message-ID", view.message_id),
    )
    rows = "".join(
        f"<tr><th>{escape(label)}</th><td>{escape(value or '—')}</td></tr>" for label, value in fields
    )
    return f"<table class='message-headers'><tbody>{rows}</tbody></table>"


def _print_css(profile: EmailPrintProfile) -> str:
    base = max(6.0, min(20.0, profile.base_font_pt * profile.scale))
    bg = "" if profile.print_backgrounds else "*{background-color:transparent!important;}"
    return f"""
    body {{ font-family: sans-serif; font-size: {base:.2f}pt; color: #111; line-height: 1.35; }}
    h1,h2,h3 {{ break-after: avoid; }}
    table {{ width: 100%; border-collapse: collapse; margin: 8pt 0; }}
    th,td {{ border: 0.5pt solid #bbb; padding: 4pt; vertical-align: top; }}
    .message-headers th {{ width: 82pt; text-align: left; background-color: #f2f2f2; }}
    blockquote {{ border-left: 2pt solid #bbb; margin-left: 8pt; padding-left: 8pt; color: #444; }}
    pre,code {{ white-space: pre-wrap; font-family: monospace; font-size: 8.5pt; }}
    img {{ max-width: 100%; height: auto; }}
    .image-placeholder {{ color: #666; font-style: italic; }}
    .message {{ break-after: page; }}
    .message:last-child {{ break-after: auto; }}
    .attachments {{ break-inside: avoid; }}
    a {{ color: #0645ad; text-decoration: underline; }}
    {bg}
    """


def _cid_assets(view: EmailMessageView, temp_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    index = 0
    for item in view.attachments:
        if not item.inline or not item.content_id or not item.payload or not item.content_type.startswith("image/"):
            continue
        index += 1
        subtype = item.content_type.split("/", 1)[1].split("+", 1)[0]
        ext = re.sub(r"[^a-zA-Z0-9]", "", subtype) or "img"
        name = f"cid-{index}.{ext}"
        (temp_dir / name).write_bytes(item.payload)
        result[item.content_id] = name
    return result


def _message_html(view: EmailMessageView, profile: EmailPrintProfile, cid_map: Mapping[str, str]):
    if view.html_body:
        sanitizer = _EmailHTMLSanitizer(allow_remote_images=profile.allow_remote_images, cid_map=cid_map)
        sanitizer.feed(view.html_body)
        body = sanitizer.html()
        active_removed = sanitizer.active_content_removed
        remote_blocked = sanitizer.remote_images_blocked
    else:
        body = f"<pre>{escape(view.text_body or '')}</pre>"
        active_removed = False
        remote_blocked = 0
    manifest = _attachment_manifest(view) if profile.include_attachment_manifest else ""
    html = (
        "<section class='message'>"
        f"<h2>{escape(view.subject or '(no subject)')}</h2>"
        f"{_header_table(view)}"
        f"<article class='email-body'>{body}</article>"
        f"{manifest}</section>"
    )
    return html, active_removed, remote_blocked


def compile_print_html(
    views: Sequence[EmailMessageView],
    profile: EmailPrintProfile,
    cid_maps: Sequence[Mapping[str, str]] | None = None,
) -> tuple[str, bool, int]:
    profile.validate()
    if not views:
        raise ValueError("at least one email view is required")
    cid_maps = cid_maps or tuple({} for _ in views)
    chunks: list[str] = []
    active_removed = False
    remote_blocked = 0
    for view, cid_map in zip(views, cid_maps):
        chunk, removed, blocked = _message_html(view, profile, cid_map)
        chunks.append(chunk)
        active_removed = active_removed or removed
        remote_blocked += blocked
    return "".join(chunks), active_removed, remote_blocked


def render_email_views(
    views: Sequence[EmailMessageView],
    output_path: str | Path,
    profile: EmailPrintProfile = EmailPrintProfile(),
    *,
    source_bytes: bytes | None = None,
) -> EmailPrintReceipt:
    profile.validate()
    if not views:
        raise ValueError("at least one email view is required")
    import pymupdf

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="adobe-omega-email-") as tmp:
        tmpdir = Path(tmp)
        cid_maps = tuple(_cid_assets(view, tmpdir) for view in views)
        html, active_removed, remote_blocked = compile_print_html(views, profile, cid_maps)
        archive = pymupdf.Archive(str(tmpdir))
        story = pymupdf.Story(html=html, user_css=_print_css(profile), archive=archive, em=profile.base_font_pt)
        mediabox = _paper_rect(pymupdf, profile)
        header_reserve = 14.0 if profile.display_header_footer else 0.0
        footer_reserve = 14.0 if profile.display_header_footer else 0.0
        where = mediabox + (
            profile.margin_left_mm * PT_PER_MM,
            profile.margin_top_mm * PT_PER_MM + header_reserve,
            -profile.margin_right_mm * PT_PER_MM,
            -(profile.margin_bottom_mm * PT_PER_MM + footer_reserve),
        )
        buffer = io.BytesIO()
        writer = pymupdf.DocumentWriter(buffer, "compress")
        more = True
        while more:
            device = writer.begin_page(mediabox)
            more, _filled = story.place(where)
            story.draw(device)
            writer.end_page()
        writer.close()
        initial = buffer.getvalue()

    doc = pymupdf.open(stream=initial, filetype="pdf")
    full_page_count = len(doc)
    if profile.display_header_footer:
        for index, page in enumerate(doc):
            footer = f"Page {index + 1} of {full_page_count}"
            header = views[0].subject or "Email"
            page.insert_text((profile.margin_left_mm * PT_PER_MM, profile.margin_top_mm * PT_PER_MM), header[:110], fontsize=7.5)
            page.insert_text((profile.margin_left_mm * PT_PER_MM, page.rect.height - profile.margin_bottom_mm * PT_PER_MM / 2), footer, fontsize=7.0)

    selected = _parse_page_ranges(profile.page_ranges, full_page_count)
    if selected and len(selected) != full_page_count:
        clipped = pymupdf.open()
        for number in selected:
            clipped.insert_pdf(doc, from_page=number - 1, to_page=number - 1)
        doc.close()
        doc = clipped

    subject = views[0].subject or "Email"
    metadata = dict(doc.metadata or {})
    metadata.update({
        "title": subject,
        "subject": "Print-ready email PDF generated by Federation Adobe Omega",
        "author": views[0].from_ or "",
        "keywords": "email, print-ready, Federation Adobe Omega",
    })
    doc.set_metadata(metadata)
    final_bytes = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    output_path.write_bytes(final_bytes)

    readback = pymupdf.open(stream=final_bytes, filetype="pdf")
    page_count = len(readback)
    text = "\n".join(page.get_text("text") for page in readback)
    first_rect = readback[0].rect if page_count else pymupdf.Rect()
    readback.close()

    expected_headers = {
        "From": views[0].from_, "To": views[0].to, "Date": views[0].date, "Subject": views[0].subject,
    }
    present = tuple(label for label, value in expected_headers.items() if value and value in text)
    semantic_ok = page_count > 0 and all(label in present for label, value in expected_headers.items() if value)
    source_payload = source_bytes if source_bytes is not None else json.dumps(
        [
            {
                "subject": view.subject, "from": view.from_, "to": view.to, "cc": view.cc,
                "date": view.date, "message_id": view.message_id,
                "html": view.html_body, "text": view.text_body,
                "attachments": [(a.filename, a.content_type, a.size_bytes, a.content_id, a.inline) for a in view.attachments],
            }
            for view in views
        ],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    body = {
        "schema": SCHEMA,
        "source_sha256": sha256(source_payload).hexdigest(),
        "pdf_sha256": sha256(final_bytes).hexdigest(),
        "profile_sha256": profile.fingerprint(),
        "page_count": full_page_count,
        "selected_page_count": page_count,
        "paper": profile.paper.upper(),
        "orientation": profile.orientation.upper(),
        "page_width_pt": round(float(first_rect.width), 3),
        "page_height_pt": round(float(first_rect.height), 3),
        "attachment_count": sum(len(v.attachments) for v in views),
        "inline_image_count": sum(sum(1 for a in v.attachments if a.inline and a.content_type.startswith("image/")) for v in views),
        "header_fields_present": present,
        "extracted_text_sha256": sha256(text.encode("utf-8")).hexdigest(),
        "semantic_readback_verified": semantic_ok,
        "active_content_removed": active_removed,
        "remote_images_blocked": remote_blocked,
        "provider_effect_performed": False,
    }
    receipt_sha = sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    return EmailPrintReceipt(**body, receipt_sha256=receipt_sha)


def render_rfc822(
    data: bytes,
    output_path: str | Path,
    profile: EmailPrintProfile = EmailPrintProfile(),
) -> EmailPrintReceipt:
    view = parse_rfc822(data)
    return render_email_views((view,), output_path, profile, source_bytes=bytes(data))


def render_thread_rfc822(
    messages: Iterable[bytes],
    output_path: str | Path,
    profile: EmailPrintProfile = EmailPrintProfile(),
) -> EmailPrintReceipt:
    raw = tuple(bytes(item) for item in messages)
    if not raw:
        raise ValueError("at least one message is required")
    views = tuple(parse_rfc822(item) for item in raw)
    return render_email_views(views, output_path, profile, source_bytes=b"\n--FEDERATION-THREAD--\n".join(raw))
