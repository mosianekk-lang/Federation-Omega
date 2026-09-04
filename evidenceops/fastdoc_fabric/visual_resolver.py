from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .models import SearchHit


@dataclass(frozen=True)
class RenderedPage:
    page_number: int
    png_bytes: bytes
    width: int
    height: int
    dpi: int


class QueryDrivenPageResolver:
    """Resolve and render only pages that a query or escalation decision needs."""

    def __init__(self, max_pages: int = 12, dpi: int = 96) -> None:
        if max_pages < 1:
            raise ValueError("max_pages must be >= 1")
        self.max_pages = int(max_pages)
        self.dpi = int(dpi)

    def select(
        self,
        hits: Sequence[SearchHit] | None = None,
        escalation_pages: Iterable[int] = (),
    ) -> tuple[int, ...]:
        ordered: list[int] = []
        seen: set[int] = set()
        for hit in hits or ():
            page = int(hit.page_number)
            if page not in seen:
                ordered.append(page)
                seen.add(page)
        for page in sorted({int(n) for n in escalation_pages}):
            if page not in seen:
                ordered.append(page)
                seen.add(page)
        return tuple(ordered[: self.max_pages])

    def render(
        self,
        path: str | Path,
        page_numbers: Iterable[int],
        *,
        dpi: int | None = None,
    ) -> list[RenderedPage]:
        import pymupdf

        selected = tuple(dict.fromkeys(int(n) for n in page_numbers))[: self.max_pages]
        render_dpi = self.dpi if dpi is None else int(dpi)
        result: list[RenderedPage] = []
        with pymupdf.open(str(path)) as doc:
            for page_number in selected:
                if page_number < 1 or page_number > len(doc):
                    raise ValueError(f"PAGE_OUT_OF_RANGE:{page_number}")
                pix = doc[page_number - 1].get_pixmap(dpi=render_dpi, alpha=False)
                result.append(
                    RenderedPage(
                        page_number=page_number,
                        png_bytes=pix.tobytes("png"),
                        width=pix.width,
                        height=pix.height,
                        dpi=render_dpi,
                    )
                )
        return result
