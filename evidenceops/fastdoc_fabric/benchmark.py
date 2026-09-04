from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import tempfile
import time

from .cache import SQLitePageStore
from .engine import FastDocumentEngine
from .pymupdf_adapter import PyMuPDFAdapter


def run_benchmark(
    path: str | Path,
    *,
    workers: int | None = None,
    queries: list[str] | None = None,
) -> dict:
    path = Path(path)
    queries = queries or []
    with tempfile.TemporaryDirectory(prefix="fastdoc-bench-") as td:
        store = SQLitePageStore(Path(td) / "fastdoc.sqlite")
        engine = FastDocumentEngine(PyMuPDFAdapter(), store)
        cold = engine.ingest(path, workers=workers)
        query_ms: list[float] = []
        query_pages: dict[str, list[int]] = {}
        for query in queries:
            t0 = time.perf_counter()
            hits = store.search(cold.document_sha256, query, limit=8)
            query_ms.append((time.perf_counter() - t0) * 1000.0)
            query_pages[query] = [hit.page_number for hit in hits]
        warm = engine.ingest(path, workers=workers)
        store.close()

    return {
        "document_sha256": cold.document_sha256,
        "page_count": cold.page_count,
        "extractor": f"{cold.extractor}@{cold.extractor_version}",
        "cold_elapsed_seconds": cold.elapsed_seconds,
        "cold_pages_per_second": cold.pages_per_second,
        "cold_index_seconds": cold.index_seconds,
        "selective_escalation_pages": list(cold.escalation_pages),
        "selective_escalation_ratio": (
            len(cold.escalation_pages) / cold.page_count if cold.page_count else 0.0
        ),
        "warm_elapsed_seconds": warm.elapsed_seconds,
        "warm_cache_hits": warm.cache_hits,
        "query_latency_ms_p50": statistics.median(query_ms) if query_ms else None,
        "query_latency_ms_max": max(query_ms) if query_ms else None,
        "query_top_pages": query_pages,
        "truth_boundary": (
            "Local native extraction/cache/search only; no OCR/VLM/provider effect executed."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark EvidenceOps FastDoc on a local document without external provider effects."
        )
    )
    parser.add_argument("document")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--query", action="append", default=[])
    args = parser.parse_args()
    print(
        json.dumps(
            run_benchmark(args.document, workers=args.workers, queries=args.query),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
