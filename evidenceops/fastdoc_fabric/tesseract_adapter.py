from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import time
from typing import Iterable, Mapping, Any

from .cache import SQLitePageStore
from .models import PagePacket


EXTRACTOR = "pymupdf-tesseract-ocr"


def _tesseract_version() -> str:
    binary = shutil.which("tesseract")
    if not binary:
        return "unavailable"
    try:
        proc = subprocess.run(
            [binary, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        first = (proc.stdout or proc.stderr).splitlines()[0].strip()
        return first or "unknown"
    except Exception:
        return "unknown"


class TesseractOCRAdapter:
    """Local-only OCR adapter used exclusively for selected escalation pages.

    No network/provider request is made. PyMuPDF invokes the locally installed
    Tesseract binary. Callers must still apply their own confidentiality and
    document-security gates before processing.
    """

    extractor = EXTRACTOR

    @property
    def available(self) -> bool:
        return shutil.which("tesseract") is not None

    @property
    def extractor_version(self) -> str:
        import pymupdf

        return f"pymupdf-{getattr(pymupdf, '__version__', 'unknown')}/{_tesseract_version()}"

    def extract_pages(
        self,
        path: str | Path,
        page_numbers: Iterable[int],
        *,
        dpi: int = 120,
        language: str = "eng",
    ) -> list[PagePacket]:
        if not self.available:
            raise RuntimeError("LOCAL_TESSERACT_UNAVAILABLE")
        import pymupdf

        selected = sorted({int(n) for n in page_numbers})
        result: list[PagePacket] = []
        with pymupdf.open(str(path)) as doc:
            for page_number in selected:
                if page_number < 1 or page_number > len(doc):
                    raise ValueError(f"PAGE_OUT_OF_RANGE:{page_number}")
                page = doc[page_number - 1]
                t0 = time.perf_counter()
                textpage = page.get_textpage_ocr(
                    language=language,
                    dpi=int(dpi),
                    full=True,
                )
                text = page.get_text("text", textpage=textpage)
                result.append(
                    PagePacket(
                        page_number=page_number,
                        text=text,
                        block_count=0,
                        image_count=len(page.get_images(full=True)),
                        extraction_ms=(time.perf_counter() - t0) * 1000.0,
                        extractor=self.extractor,
                        extractor_version=self.extractor_version,
                        metadata={
                            "local_ocr": True,
                            "dpi": int(dpi),
                            "language": language,
                            "provider_effect": False,
                        },
                    )
                )
        return result


@dataclass(frozen=True)
class OCRReceipt:
    requested_pages: tuple[int, ...]
    processed_pages: tuple[int, ...]
    cache_hits: int
    elapsed_seconds: float
    extractor: str
    extractor_version: str


class SelectiveLocalOCR:
    """Cache-first OCR runner for only the pages selected by FastDoc routing."""

    def __init__(self, store: SQLitePageStore, adapter: TesseractOCRAdapter | None = None) -> None:
        self.store = store
        self.adapter = adapter or TesseractOCRAdapter()

    def enrich(
        self,
        path: str | Path,
        document_sha: str,
        page_numbers: Iterable[int],
        *,
        dpi: int = 120,
        language: str = "eng",
    ) -> OCRReceipt:
        requested = tuple(sorted({int(n) for n in page_numbers}))
        options: Mapping[str, Any] = {"dpi": int(dpi), "language": language}
        cached: list[int] = []
        missing: list[int] = []
        for page_number in requested:
            packet = self.store.get(
                document_sha,
                page_number,
                self.adapter.extractor,
                self.adapter.extractor_version,
                options,
            )
            (cached if packet is not None else missing).append(page_number)

        t0 = time.perf_counter()
        packets = self.adapter.extract_pages(
            path,
            missing,
            dpi=dpi,
            language=language,
        ) if missing else []
        if packets:
            self.store.put_many(document_sha, packets, options)
        elapsed = time.perf_counter() - t0
        return OCRReceipt(
            requested_pages=requested,
            processed_pages=tuple(p.page_number for p in packets),
            cache_hits=len(cached),
            elapsed_seconds=elapsed,
            extractor=self.adapter.extractor,
            extractor_version=self.adapter.extractor_version,
        )
