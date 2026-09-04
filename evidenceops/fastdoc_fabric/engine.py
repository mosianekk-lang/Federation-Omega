from __future__ import annotations

import hashlib
from pathlib import Path
import time
from typing import Mapping, Any

from .cache import SQLitePageStore
from .models import IngestReceipt, PagePacket, ProcessingLane
from .router import RoutingPolicy


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class FastDocumentEngine:
    """Progressive-ready high-speed ingestion core.

    The engine deliberately separates cheap native extraction from expensive OCR/
    vision. It persists page packets so repeated questions do not reprocess an
    unchanged document. External OCR/vision adapters are downstream, authority-
    gated extensions rather than implicit side effects.
    """

    def __init__(self, adapter: Any, store: SQLitePageStore, routing: RoutingPolicy | None = None) -> None:
        self.adapter = adapter
        self.store = store
        self.routing = routing or RoutingPolicy()

    def ingest(
        self,
        path: str | Path,
        *,
        workers: int | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> IngestReceipt:
        path = str(path)
        document_sha = sha256_file(path)
        page_count = self.adapter.page_count(path)
        cached = self.store.cached_page_numbers(
            document_sha,
            self.adapter.extractor,
            self.adapter.extractor_version,
            options,
        )

        start = time.perf_counter()
        processed = 0
        escalation: list[int] = []

        if len(cached) == page_count:
            for page_number in sorted(cached):
                packet = self.store.get(
                    document_sha,
                    page_number,
                    self.adapter.extractor,
                    self.adapter.extractor_version,
                    options,
                )
                if packet and self.routing.route(packet).lane != ProcessingLane.NATIVE_FAST:
                    escalation.append(page_number)
            elapsed = time.perf_counter() - start
            return IngestReceipt(
                document_sha256=document_sha,
                page_count=page_count,
                processed_pages=0,
                cache_hits=page_count,
                escalation_pages=tuple(escalation),
                elapsed_seconds=elapsed,
                pages_per_second=0.0,
                index_seconds=0.0,
                extractor=self.adapter.extractor,
                extractor_version=self.adapter.extractor_version,
            )

        packets = self.adapter.extract_document(path, workers=workers)
        index_start = time.perf_counter()
        to_store: list[PagePacket] = []
        for packet in packets:
            if packet.page_number in cached:
                continue
            processed += 1
            decision = self.routing.route(packet)
            if decision.lane != ProcessingLane.NATIVE_FAST:
                escalation.append(packet.page_number)
            metadata = dict(packet.metadata)
            metadata.update(
                {
                    "routing_lane": decision.lane.value,
                    "quality_score": decision.quality_score,
                    "routing_reasons": list(decision.reasons),
                }
            )
            to_store.append(
                PagePacket(
                    page_number=packet.page_number,
                    text=packet.text,
                    block_count=packet.block_count,
                    image_count=packet.image_count,
                    extraction_ms=packet.extraction_ms,
                    extractor=packet.extractor,
                    extractor_version=packet.extractor_version,
                    metadata=metadata,
                )
            )
        self.store.put_many(document_sha, to_store, options)
        index_elapsed = time.perf_counter() - index_start
        elapsed = time.perf_counter() - start
        pps = processed / elapsed if elapsed and processed else 0.0
        return IngestReceipt(
            document_sha256=document_sha,
            page_count=page_count,
            processed_pages=processed,
            cache_hits=len(cached),
            escalation_pages=tuple(sorted(escalation)),
            elapsed_seconds=elapsed,
            pages_per_second=pps,
            index_seconds=index_elapsed,
            extractor=self.adapter.extractor,
            extractor_version=self.adapter.extractor_version,
        )
