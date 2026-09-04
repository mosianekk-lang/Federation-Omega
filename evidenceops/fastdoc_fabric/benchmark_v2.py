from __future__ import annotations

"""Private-corpus benchmark CLI for FastDoc v2.

Outputs aggregate timings/hashes only. It never emits extracted source text and does
not call external OCR/VLM providers.
"""

from dataclasses import asdict
import argparse
import json
from pathlib import Path
import tempfile
import time

from .v2 import ContextPackBuilder, FastDocV2, FastDocV2Config, LatencyProfile, SQLiteContentStoreV2, _pymupdf_version


def run(pdf: str, *, profile: LatencyProfile, workers: int = 0, batch_pages: int = 0, queries: list[str] | None = None, local_ocr: bool = False) -> dict:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "fastdoc-v2.sqlite"
        store = SQLiteContentStoreV2(db)
        config = FastDocV2Config(profile=profile, workers=workers, batch_pages=batch_pages)
        engine = FastDocV2(store, config)
        cold = engine.ingest(pdf)
        warm_start = time.perf_counter()
        warm = engine.ingest(pdf)
        warm_wall = time.perf_counter() - warm_start
        ocr = None
        if local_ocr and cold.escalation_pages:
            ocr = asdict(engine.enrich_local_ocr(
                pdf, document_sha256=cold.document_sha256, page_numbers=cold.escalation_pages
            ))
        builder = ContextPackBuilder(store, config)
        context = []
        for query in queries or []:
            pack = builder.build(
                document_sha256=cold.document_sha256,
                extractor_version=_pymupdf_version(),
                query=query,
                escalation_pages=cold.escalation_pages,
            )
            context.append({
                "query_sha256": __import__("hashlib").sha256(query.encode()).hexdigest(),
                "page_count": pack.page_count,
                "chars": pack.total_chars,
                "build_ms": pack.build_ms,
                "truncated": pack.truncated,
            })
        result = {
            "schema": "FEDERATION_FASTDOC_V2_PRIVATE_BENCHMARK_1",
            "corpus": {"document_sha256": cold.document_sha256, "page_count": cold.page_count},
            "cold": asdict(cold),
            "warm": asdict(warm),
            "warm_wall_seconds": warm_wall,
            "context_packs": context,
            "local_ocr": ocr,
            "provider_effect": False,
            "source_text_emitted": False,
        }
        store.close()
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("--profile", choices=[x.value for x in LatencyProfile], default=LatencyProfile.INTERACTIVE.value)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--batch-pages", type=int, default=0)
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--local-ocr", action="store_true", help="OCR only selective escalation pages with the local Tesseract CLI")
    parser.add_argument("--public", action="store_true", help="redact private corpus hash from stdout")
    args = parser.parse_args()
    result = run(args.pdf, profile=LatencyProfile(args.profile), workers=args.workers, batch_pages=args.batch_pages, queries=args.query, local_ocr=args.local_ocr)
    if args.public:
        result["corpus"]["document_sha256"] = "PRIVATE_REDACTED"
        result["cold"]["document_sha256"] = "PRIVATE_REDACTED"
        result["warm"]["document_sha256"] = "PRIVATE_REDACTED"
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
