from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import math
import os
import time

from .models import PagePacket


EXTRACTOR = "pymupdf-blocks-no-images"


def _pymupdf_version() -> str:
    import pymupdf
    return getattr(pymupdf, "__version__", "unknown")


def _extract_range(path: str, start: int, end: int) -> list[PagePacket]:
    import pymupdf

    flags = pymupdf.TEXT_PRESERVE_LIGATURES | pymupdf.TEXT_PRESERVE_WHITESPACE
    version = getattr(pymupdf, "__version__", "unknown")
    result: list[PagePacket] = []
    with pymupdf.open(path) as doc:
        for page_index in range(start, end):
            t0 = time.perf_counter()
            page = doc[page_index]
            blocks = page.get_text("blocks", flags=flags)
            text = "\n".join(str(b[4]) for b in blocks if len(b) > 4 and str(b[4]).strip())
            image_count = len(page.get_images(full=True))
            result.append(
                PagePacket(
                    page_number=page_index + 1,
                    text=text,
                    block_count=len(blocks),
                    image_count=image_count,
                    extraction_ms=(time.perf_counter() - t0) * 1000.0,
                    extractor=EXTRACTOR,
                    extractor_version=version,
                )
            )
    return result


class PyMuPDFAdapter:
    """Fast native PDF adapter.

    Page ranges are processed in independent processes. Images are counted but not
    extracted on the fast path. OCR is intentionally not performed here; sparse or
    low-quality pages are returned to the routing layer for selective escalation.
    """

    extractor = EXTRACTOR

    @property
    def extractor_version(self) -> str:
        return _pymupdf_version()

    def page_count(self, path: str | Path) -> int:
        import pymupdf
        with pymupdf.open(str(path)) as doc:
            return len(doc)

    def extract_document(self, path: str | Path, workers: int | None = None) -> list[PagePacket]:
        path = str(path)
        pages = self.page_count(path)
        if pages == 0:
            return []
        max_workers = max(1, min(workers or (os.cpu_count() or 1), pages))
        if max_workers == 1 or pages < 64:
            return _extract_range(path, 0, pages)

        chunk = math.ceil(pages / max_workers)
        ranges = [(start, min(start + chunk, pages)) for start in range(0, pages, chunk)]
        packets: list[PagePacket] = []
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_extract_range, path, start, end) for start, end in ranges]
            for future in as_completed(futures):
                packets.extend(future.result())
        packets.sort(key=lambda p: p.page_number)
        return packets
