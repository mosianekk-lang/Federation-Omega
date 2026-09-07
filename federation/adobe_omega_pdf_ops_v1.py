"""Federation Adobe Ω local Acrobat-class PDF operations engine v1.

Local-only, provider-neutral PDF operations implemented with the repository's
admitted PyMuPDF runtime. Every transforming operation writes a new file and
then reopens it for semantic readback before issuing a verified receipt.

Capabilities:
- properties / structural inspection;
- combine;
- extract / split / reorder / delete-by-omission;
- rotate;
- optimize / compress;
- text / rectangle redaction;
- highlight and text-note annotation;
- searchable OCR via local Tesseract when installed.

No Adobe, Gmail, Outlook or other provider call occurs in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Iterable, Mapping, Sequence

SCHEMA = "FEDERATION_ADOBE_OMEGA_PDF_OPS_V1"
VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class PdfProperties:
    source_sha256: str
    file_size_bytes: int
    page_count: int
    metadata: tuple[tuple[str, str], ...]
    rotations: tuple[int, ...]
    page_sizes_pt: tuple[tuple[float, float], ...]
    encrypted: bool
    needs_password: bool
    xref_length: int
    text_char_count: int
    annotation_count: int
    extracted_text_sha256: str


@dataclass(frozen=True, slots=True)
class PdfOperationReceipt:
    schema: str
    version: str
    operation: str
    source_sha256: tuple[str, ...]
    output_sha256: str
    input_page_count: int
    output_page_count: int
    source_text_sha256: tuple[str, ...]
    output_text_sha256: str
    semantic_readback_verified: bool
    provider_effect_performed: bool
    details: tuple[tuple[str, str], ...]
    receipt_sha256: str


def _stable(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _sha256_path(path: str | Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _document_text(doc) -> str:
    return "\n--FEDERATION-PAGE--\n".join(page.get_text("text") for page in doc)


def _text_hash(doc) -> str:
    return _sha256_bytes(_document_text(doc).encode("utf-8"))


def _page_text_hashes(doc) -> tuple[str, ...]:
    return tuple(_sha256_bytes(page.get_text("text").encode("utf-8")) for page in doc)


def _require_pdf(path: str | Path) -> Path:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size <= 0:
        raise ValueError("PDF file is empty")
    return path


def _require_distinct_output(inputs: Iterable[str | Path], output_path: str | Path) -> Path:
    out = Path(output_path)
    resolved_out = out.resolve()
    for source in inputs:
        if Path(source).resolve() == resolved_out:
            raise ValueError("output_path must differ from every input path")
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def _save(doc, output_path: Path, *, optimize: bool = True) -> None:
    kwargs = {}
    if optimize:
        kwargs = {
            "garbage": 4,
            "deflate": True,
            "deflate_images": True,
            "deflate_fonts": True,
            "use_objstms": 1,
        }
    doc.save(str(output_path), **kwargs)


def _receipt(
    *,
    operation: str,
    sources: Sequence[Path],
    output: Path,
    input_page_count: int,
    source_text_sha256: Sequence[str],
    semantic_ok: bool,
    details: Mapping[str, object],
) -> PdfOperationReceipt:
    import pymupdf

    with pymupdf.open(str(output)) as readback:
        output_page_count = len(readback)
        output_text_sha256 = _text_hash(readback)
    body = {
        "schema": SCHEMA,
        "version": VERSION,
        "operation": operation,
        "source_sha256": tuple(_sha256_path(p) for p in sources),
        "output_sha256": _sha256_path(output),
        "input_page_count": int(input_page_count),
        "output_page_count": int(output_page_count),
        "source_text_sha256": tuple(source_text_sha256),
        "output_text_sha256": output_text_sha256,
        "semantic_readback_verified": bool(semantic_ok),
        "provider_effect_performed": False,
        "details": tuple(sorted((str(k), str(v)) for k, v in details.items())),
    }
    receipt_sha = _sha256_bytes(_stable(body))
    return PdfOperationReceipt(**body, receipt_sha256=receipt_sha)


def pdf_properties(path: str | Path) -> PdfProperties:
    """Read structural properties and independently extracted text identity."""
    import pymupdf

    path = _require_pdf(path)
    with pymupdf.open(str(path)) as doc:
        metadata = tuple(sorted((str(k), str(v or "")) for k, v in (doc.metadata or {}).items()))
        rotations = tuple(int(page.rotation) for page in doc)
        page_sizes = tuple((round(float(page.rect.width), 3), round(float(page.rect.height), 3)) for page in doc)
        text = _document_text(doc)
        annotation_count = 0
        for page in doc:
            annot = page.first_annot
            while annot:
                annotation_count += 1
                annot = annot.next
        return PdfProperties(
            source_sha256=_sha256_path(path),
            file_size_bytes=path.stat().st_size,
            page_count=len(doc),
            metadata=metadata,
            rotations=rotations,
            page_sizes_pt=page_sizes,
            encrypted=bool(doc.is_encrypted),
            needs_password=bool(doc.needs_pass),
            xref_length=int(doc.xref_length()),
            text_char_count=len(text),
            annotation_count=annotation_count,
            extracted_text_sha256=_sha256_bytes(text.encode("utf-8")),
        )


def combine_pdfs(inputs: Sequence[str | Path], output_path: str | Path) -> PdfOperationReceipt:
    """Combine PDFs in source order and verify page/text sequence after reopening."""
    import pymupdf

    if len(inputs) < 2:
        raise ValueError("combine requires at least two PDFs")
    sources = tuple(_require_pdf(p) for p in inputs)
    out = _require_distinct_output(sources, output_path)

    source_page_hashes: list[str] = []
    source_text_hashes: list[str] = []
    input_pages = 0
    output_doc = pymupdf.open()
    try:
        for source in sources:
            with pymupdf.open(str(source)) as doc:
                if doc.needs_pass:
                    raise ValueError("encrypted input requires prior authorization/decryption")
                input_pages += len(doc)
                source_text_hashes.append(_text_hash(doc))
                source_page_hashes.extend(_page_text_hashes(doc))
                output_doc.insert_pdf(doc)
        _save(output_doc, out)
    finally:
        output_doc.close()

    with pymupdf.open(str(out)) as readback:
        semantic_ok = len(readback) == input_pages and tuple(source_page_hashes) == _page_text_hashes(readback)

    return _receipt(
        operation="COMBINE",
        sources=sources,
        output=out,
        input_page_count=input_pages,
        source_text_sha256=source_text_hashes,
        semantic_ok=semantic_ok,
        details={"source_count": len(sources), "sequence_verified": semantic_ok},
    )


def extract_pages(
    input_path: str | Path,
    output_path: str | Path,
    pages: Sequence[int],
) -> PdfOperationReceipt:
    """Extract/reorder pages using 1-based page numbers; omission is deletion."""
    import pymupdf

    source = _require_pdf(input_path)
    out = _require_distinct_output((source,), output_path)
    selected = tuple(int(n) for n in pages)
    if not selected:
        raise ValueError("at least one page must be selected")

    with pymupdf.open(str(source)) as doc:
        if doc.needs_pass:
            raise ValueError("encrypted input requires prior authorization/decryption")
        input_pages = len(doc)
        if any(n < 1 or n > input_pages for n in selected):
            raise ValueError("page selection out of range")
        source_text = _text_hash(doc)
        expected_hashes = tuple(_sha256_bytes(doc[n - 1].get_text("text").encode("utf-8")) for n in selected)
        output_doc = pymupdf.open()
        try:
            for number in selected:
                output_doc.insert_pdf(doc, from_page=number - 1, to_page=number - 1)
            _save(output_doc, out)
        finally:
            output_doc.close()

    with pymupdf.open(str(out)) as readback:
        semantic_ok = len(readback) == len(selected) and _page_text_hashes(readback) == expected_hashes

    return _receipt(
        operation="EXTRACT_REORDER",
        sources=(source,),
        output=out,
        input_page_count=input_pages,
        source_text_sha256=(source_text,),
        semantic_ok=semantic_ok,
        details={"selected_pages": ",".join(str(n) for n in selected), "sequence_verified": semantic_ok},
    )


def split_pdf(
    input_path: str | Path,
    output_dir: str | Path,
    groups: Sequence[Sequence[int]] | None = None,
) -> tuple[PdfOperationReceipt, ...]:
    """Split a PDF into explicit groups, or one output PDF per page when groups is omitted."""
    import pymupdf

    source = _require_pdf(input_path)
    with pymupdf.open(str(source)) as doc:
        count = len(doc)
    if groups is None:
        groups = tuple((i,) for i in range(1, count + 1))
    if not groups:
        raise ValueError("at least one split group is required")
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    receipts: list[PdfOperationReceipt] = []
    for index, group in enumerate(groups, start=1):
        receipts.append(extract_pages(source, outdir / f"split-{index:04d}.pdf", tuple(group)))
    return tuple(receipts)


def rotate_pdf(
    input_path: str | Path,
    output_path: str | Path,
    rotations: Mapping[int, int] | int,
) -> PdfOperationReceipt:
    """Rotate selected pages or every page; rotations must be multiples of 90 degrees."""
    import pymupdf

    source = _require_pdf(input_path)
    out = _require_distinct_output((source,), output_path)

    with pymupdf.open(str(source)) as doc:
        if doc.needs_pass:
            raise ValueError("encrypted input requires prior authorization/decryption")
        input_pages = len(doc)
        source_text = _text_hash(doc)
        source_page_hashes = _page_text_hashes(doc)
        before = tuple(int(page.rotation) for page in doc)

        if isinstance(rotations, int):
            mapping = {n: int(rotations) for n in range(1, input_pages + 1)}
        else:
            mapping = {int(k): int(v) for k, v in rotations.items()}
        if not mapping:
            raise ValueError("at least one rotation is required")
        for page_number, delta in mapping.items():
            if page_number < 1 or page_number > input_pages:
                raise ValueError("rotation page out of range")
            if delta % 90:
                raise ValueError("rotation must be a multiple of 90 degrees")
            page = doc[page_number - 1]
            page.set_rotation((int(page.rotation) + delta) % 360)
        expected = tuple(int(page.rotation) for page in doc)
        _save(doc, out)

    with pymupdf.open(str(out)) as readback:
        actual = tuple(int(page.rotation) for page in readback)
        semantic_ok = actual == expected and _page_text_hashes(readback) == source_page_hashes

    return _receipt(
        operation="ROTATE",
        sources=(source,),
        output=out,
        input_page_count=input_pages,
        source_text_sha256=(source_text,),
        semantic_ok=semantic_ok,
        details={"before": before, "after": actual, "text_preserved": semantic_ok},
    )


def optimize_pdf(input_path: str | Path, output_path: str | Path) -> PdfOperationReceipt:
    """Rewrite PDF with object cleanup and stream/font/image deflation, preserving text/page semantics."""
    import pymupdf

    source = _require_pdf(input_path)
    out = _require_distinct_output((source,), output_path)
    source_size = source.stat().st_size
    with pymupdf.open(str(source)) as doc:
        if doc.needs_pass:
            raise ValueError("encrypted input requires prior authorization/decryption")
        input_pages = len(doc)
        source_text = _text_hash(doc)
        page_hashes = _page_text_hashes(doc)
        _save(doc, out, optimize=True)

    with pymupdf.open(str(out)) as readback:
        semantic_ok = len(readback) == input_pages and _page_text_hashes(readback) == page_hashes
    output_size = out.stat().st_size

    return _receipt(
        operation="OPTIMIZE_COMPRESS",
        sources=(source,),
        output=out,
        input_page_count=input_pages,
        source_text_sha256=(source_text,),
        semantic_ok=semantic_ok,
        details={
            "source_size_bytes": source_size,
            "output_size_bytes": output_size,
            "size_delta_bytes": output_size - source_size,
            "smaller": output_size < source_size,
            "content_preserved": semantic_ok,
        },
    )


def redact_pdf(
    input_path: str | Path,
    output_path: str | Path,
    *,
    text_targets: Sequence[str] = (),
    rectangles: Sequence[tuple[int, Sequence[float]]] = (),
) -> PdfOperationReceipt:
    """Permanently redact literal text matches and/or page rectangles, then verify text removal."""
    import pymupdf

    source = _require_pdf(input_path)
    out = _require_distinct_output((source,), output_path)
    targets = tuple(str(t) for t in text_targets if str(t))
    if not targets and not rectangles:
        raise ValueError("at least one redaction target is required")

    hits = 0
    with pymupdf.open(str(source)) as doc:
        if doc.needs_pass:
            raise ValueError("encrypted input requires prior authorization/decryption")
        input_pages = len(doc)
        source_text = _text_hash(doc)
        for page in doc:
            for target in targets:
                for rect in page.search_for(target):
                    page.add_redact_annot(rect, fill=(1, 1, 1))
                    hits += 1
        for page_number, coords in rectangles:
            page_number = int(page_number)
            if page_number < 1 or page_number > input_pages:
                raise ValueError("redaction page out of range")
            if len(tuple(coords)) != 4:
                raise ValueError("redaction rectangle must have four coordinates")
            rect = pymupdf.Rect(*[float(x) for x in coords])
            doc[page_number - 1].add_redact_annot(rect, fill=(1, 1, 1))
            hits += 1
        if targets and hits == 0 and not rectangles:
            raise ValueError("no redaction targets were found")
        for page in doc:
            if page.first_annot:
                page.apply_redactions()
        _save(doc, out)

    with pymupdf.open(str(out)) as readback:
        extracted = _document_text(readback)
        removed = all(target not in extracted for target in targets)
        semantic_ok = len(readback) == input_pages and removed

    return _receipt(
        operation="REDACT",
        sources=(source,),
        output=out,
        input_page_count=input_pages,
        source_text_sha256=(source_text,),
        semantic_ok=semantic_ok,
        details={"redaction_regions": hits, "target_count": len(targets), "targets_absent_from_text": removed},
    )


def annotate_pdf(
    input_path: str | Path,
    output_path: str | Path,
    *,
    highlights: Sequence[tuple[int, str]] = (),
    notes: Sequence[tuple[int, float, float, str]] = (),
) -> PdfOperationReceipt:
    """Add text highlights and/or text-note annotations with readback verification."""
    import pymupdf

    source = _require_pdf(input_path)
    out = _require_distinct_output((source,), output_path)
    if not highlights and not notes:
        raise ValueError("at least one annotation is required")

    expected_highlights = 0
    expected_notes = len(notes)
    with pymupdf.open(str(source)) as doc:
        if doc.needs_pass:
            raise ValueError("encrypted input requires prior authorization/decryption")
        input_pages = len(doc)
        source_text = _text_hash(doc)
        source_page_hashes = _page_text_hashes(doc)
        for page_number, target in highlights:
            page_number = int(page_number)
            if page_number < 1 or page_number > input_pages:
                raise ValueError("highlight page out of range")
            page = doc[page_number - 1]
            rects = page.search_for(str(target))
            if not rects:
                raise ValueError(f"highlight target not found: {target}")
            for rect in rects:
                annot = page.add_highlight_annot(rect)
                annot.update()
                expected_highlights += 1
        for page_number, x, y, text in notes:
            page_number = int(page_number)
            if page_number < 1 or page_number > input_pages:
                raise ValueError("note page out of range")
            page = doc[page_number - 1]
            annot = page.add_text_annot((float(x), float(y)), str(text))
            annot.set_info(content=str(text), title="Federation Adobe Omega")
            annot.update()
        _save(doc, out)

    actual_highlights = 0
    actual_notes = 0
    note_contents: list[str] = []
    with pymupdf.open(str(out)) as readback:
        for page in readback:
            annot = page.first_annot
            while annot:
                annot_type = int(annot.type[0])
                if annot_type == pymupdf.PDF_ANNOT_HIGHLIGHT:
                    actual_highlights += 1
                if annot_type == pymupdf.PDF_ANNOT_TEXT:
                    actual_notes += 1
                    note_contents.append(str((annot.info or {}).get("content") or ""))
                annot = annot.next
        text_preserved = _page_text_hashes(readback) == source_page_hashes
        semantic_ok = (
            len(readback) == input_pages
            and text_preserved
            and actual_highlights == expected_highlights
            and actual_notes == expected_notes
            and all(str(note[3]) in note_contents for note in notes)
        )

    return _receipt(
        operation="ANNOTATE",
        sources=(source,),
        output=out,
        input_page_count=input_pages,
        source_text_sha256=(source_text,),
        semantic_ok=semantic_ok,
        details={
            "highlight_count": actual_highlights,
            "note_count": actual_notes,
            "text_preserved": text_preserved,
        },
    )


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def ocr_pdf(
    input_path: str | Path,
    output_path: str | Path,
    *,
    pages: Sequence[int] | None = None,
    dpi: int = 200,
    language: str = "eng",
) -> PdfOperationReceipt:
    """Create searchable OCR pages with local Tesseract, preserving unselected pages."""
    import pymupdf

    if not ocr_available():
        raise RuntimeError("LOCAL_TESSERACT_UNAVAILABLE")
    if dpi < 72 or dpi > 600:
        raise ValueError("dpi must be between 72 and 600")

    source = _require_pdf(input_path)
    out = _require_distinct_output((source,), output_path)
    with pymupdf.open(str(source)) as doc:
        if doc.needs_pass:
            raise ValueError("encrypted input requires prior authorization/decryption")
        input_pages = len(doc)
        source_text = _text_hash(doc)
        selected = tuple(range(1, input_pages + 1)) if pages is None else tuple(sorted({int(n) for n in pages}))
        if not selected:
            raise ValueError("at least one OCR page is required")
        if any(n < 1 or n > input_pages for n in selected):
            raise ValueError("OCR page out of range")

        output_doc = pymupdf.open()
        try:
            for page_number in range(1, input_pages + 1):
                page = doc[page_number - 1]
                if page_number not in selected:
                    output_doc.insert_pdf(doc, from_page=page_number - 1, to_page=page_number - 1)
                    continue
                pix = page.get_pixmap(dpi=int(dpi), alpha=False)
                one_bytes = pix.pdfocr_tobytes(language=language)
                one = pymupdf.open(stream=one_bytes, filetype="pdf")
                try:
                    output_doc.insert_pdf(one)
                finally:
                    one.close()
            _save(output_doc, out)
        finally:
            output_doc.close()

    with pymupdf.open(str(out)) as readback:
        extracted = tuple(readback[n - 1].get_text("text").strip() for n in selected)
        selected_have_text = all(bool(text) for text in extracted)
        semantic_ok = len(readback) == input_pages and selected_have_text

    return _receipt(
        operation="OCR",
        sources=(source,),
        output=out,
        input_page_count=input_pages,
        source_text_sha256=(source_text,),
        semantic_ok=semantic_ok,
        details={
            "ocr_pages": ",".join(str(n) for n in selected),
            "dpi": dpi,
            "language": language,
            "tesseract_available": True,
            "searchable_text_present": selected_have_text,
        },
    )
