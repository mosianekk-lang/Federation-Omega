# EvidenceOps FastDoc Fabric

FastDoc is the Federation/EvidenceOps document-intelligence ingestion component. It is **not** a new control plane. The v1 API is preserved for compatibility; **FastDoc v2 is the preferred staged path for large mixed PDFs**.

## Architectural rule

A large document must not block useful analysis on whole-document OCR, rendering, rich layout reconstruction, or a full-text prompt dump.

The v2 blocking path is:

`FILE HASH -> NATIVE PAGE EXTRACTION -> PAGE INDEX -> BOUNDED CONTEXT PACK`

Selective OCR/vision and richer structure are later enrichment lanes:

`SPARSE PAGE -> LOCAL OCR CACHE -> OPTIONAL LAYOUT/TABLE/VLM SPECIALIST`

This is the direct consequence of the private 391-page matched workload: 381/391 pages were already natively extractable and only 10 pages required OCR/visual escalation.

## FastDoc v2 improvements

- **Completion-order streaming** with a bounded number of in-flight page batches.
- **Two latency profiles**: `INTERACTIVE` defaults to 16-page batches; `THROUGHPUT` to 32-page batches.
- **Process-isolated PDF extraction** for libraries/backends that are not safely thread-scaled.
- **Partial resume**: only missing pages are re-extracted after an interrupted/incomplete ingest.
- **Persistent extraction-payload CAS** separate from document/page mapping, enabling duplicate payload reuse across documents without putting page number in the reusable identity.
- **No warm index rebuild** for an unchanged fully ingested document.
- **Selective OCR overlay**: OCR is stored separately from immutable native extraction payloads and updates retrieval without mutating the native payload identity.
- **Local Tesseract fast path**: only escalation pages are rendered in grayscale and OCRed locally; no network/provider effect occurs.
- **Bounded context packs**: retrieval returns only top-hit pages + small neighbor windows under a strict character budget instead of injecting the whole PDF into downstream reasoning.
- **Provider-neutral extension point**: GPU/VLM/table/layout adapters can replace selective enrichment without changing the core evidence contract.

## v2 API

```python
from evidenceops.fastdoc_fabric import (
    ContextPackBuilder,
    FastDocV2,
    FastDocV2Config,
    LatencyProfile,
    SQLiteContentStoreV2,
)

store = SQLiteContentStoreV2("fastdoc-v2.sqlite")
engine = FastDocV2(
    store,
    FastDocV2Config(profile=LatencyProfile.INTERACTIVE, workers=4),
)

receipt = engine.ingest("large.pdf")

# Only sparse/ambiguous pages are OCR candidates.
ocr = engine.enrich_local_ocr(
    "large.pdf",
    document_sha256=receipt.document_sha256,
    page_numbers=receipt.escalation_pages,
)

context = ContextPackBuilder(store).build(
    document_sha256=receipt.document_sha256,
    extractor_version=__import__("pymupdf").__version__,
    query="post meeting instruction",
    escalation_pages=receipt.escalation_pages,
)
```

## H9 matched-workload result - 391-page private regression corpus

The private corpus remained local. No document text, path, or private corpus hash is committed in source.

Seven repeated matched native runs on the same runtime showed these medians:

| Metric | FastDoc v1 | FastDoc v2 | Delta |
| --- | ---: | ---: | ---: |
| Cold native ingest + index | 0.2700 s | 0.2454 s | 9.1% faster |
| Index portion | 0.1124 s | 0.0858 s | 23.7% faster |
| Warm unchanged re-ingest wall | 0.0566 s | 0.0165 s | 70.9% lower / 3.44x faster |
| Raw FTS query median | 0.547 ms | 0.535 ms | approximately parity, slightly faster |
| Native time-to-first-result | not streamed | 30.5 ms | new capability |
| Selective escalation pages | 10/391 | 10/391 | quality floor preserved |

A same-runtime selective-OCR challenge over those 10 pages measured approximately **17.85 s** for the v1 PyMuPDF OCR wrapper versus **8.98 s** for the v2 grayscale-render + local Tesseract CLI route. All **391/391 pages had non-empty effective text after selective OCR**.

The v2 context pack is capped at 24,000 characters by default. The same PDF contains roughly 769,000 characters of native extracted text, so the bounded downstream context path avoids up to **96.9%** of full-document text injection per query before any model-side compaction.

These are local matched-workload measurements, not ChatGPT backend claims.

## Clean-room market mechanism harvest

FastDoc v2 composes public engineering mechanisms rather than copying third-party implementation:

- Docling: stage-specific batching, bounded queues/backpressure, independent OCR/layout/table stages.
- Marker/Surya: light CPU workers with shared specialist inference, explicit worker/batch controls.
- MinerU: cross-page table continuity and specialist structured parsing.
- PaddleOCR: high-performance inference/back-end specialization such as TensorRT paths.
- Unstructured: adaptive fast/high-resolution/OCR/VLM routing.
- AWS Textract: asynchronous feature-gated multipage jobs and idempotent submission patterns.
- Google Document AI / Mistral / Adobe: hierarchical/block/reading-order/confidence structured outputs.
- Ray Data: bounded actor/batch execution, fault recovery, checkpoint/resume patterns.

Provider-specific services remain optional adapters. Their existence never proves provider authority or owner value.

## Truth boundary

- `main` source and CI proof are not proof that the ChatGPT product backend uses FastDoc.
- H9 proves matched local technical advantage for this receiver workload; it does not prove universal market superiority.
- H10 owner-value requires receiver-local operational use/observation after runtime binding.
- Local OCR avoids external transfer but still remains subject to the existing EvidenceOps document-security/privacy gate.
- External OCR/VLM, GPU deployment, spending, IAM, and provider calls require their own authority and provider-native readback.
