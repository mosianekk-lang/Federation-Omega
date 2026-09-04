# CFBE-Ω Document Fabric v1 — Market Benchmark and Harvest

## Problem
Current Federation source explicitly states that PDF bytes are integrity-hashed but production OCR/document conversion is not yet bound. Large mixed PDFs therefore risk slow, serial, all-or-nothing processing.

## Market capabilities harvested

| Source class | Capability harvested | Federation adaptation |
|---|---|---|
| Marker | Very high batch throughput, GPU/CPU/MPS execution, optional LLM repair, table-focused quality | Bounded page fan-out; route only complex pages to expensive parsers; quality escalation per page |
| MinerU | Native multi-format parsing, VLM+OCR dual engine, human reading order, header/footer suppression, cross-page table merging | Dual-route architecture; native-first, OCR/VLM fallback; structure-preserving result contract |
| Docling | Unified document representation, hierarchical/hybrid chunking | Preserve page/document hierarchy and support downstream chunking without reparsing |
| Mistral OCR | Structural blocks, table formats, header/footer controls, confidence at page/block/word level | Confidence-gated parser results and structural quality scores |
| Google Document AI Layout Parser | OCR + layout + Gemini structure recovery for headings, lists, tables and figures | Hybrid-layout route for complex pages, separate from simple native-text fast path |
| Adobe PDF Extract | Natural reading order, semantic element types, complex tables, JSON/Markdown outputs | Structured intermediate representation and explicit reading-order preservation |
| Amazon Textract | Async multipage analysis; forms, tables, queries, signatures, layout; confidence | Async adapter contract and feature-specific specialist route |
| LandingAI ADE | Concurrent page classification and downstream route selection | Pre-parse page classification and route-aware dispatch |
| Reducto benchmark methodology | Separate OCR, table parsing and structured extraction benchmarks | CFBE must not collapse incompatible document tasks into one score |
| 2026 academic benchmarks | Hierarchy-aware chunking and metadata enrichment can matter more than parser choice; clean-only benchmarks mislead | Benchmark downstream QA, degraded scans, layout continuity and document-level semantics, not parser speed alone |

## Federation design laws
1. **Native first, vision second.** Never OCR a page that already has clean native text unless a quality gate fails.
2. **Page-level routing.** Route each page independently: `native_fast`, `hybrid_layout`, `vision_ocr`, `table_specialist`.
3. **Bounded parallelism.** Process independent pages concurrently; preserve exact document order on fan-in.
4. **Page cache.** Key cache by page hash + route + parser name/version so unchanged pages are never reprocessed.
5. **Quality escalation.** Retry only the failed page through a stronger route; never restart the whole document because one page is weak.
6. **Failure isolation.** One page failure becomes an explicit page receipt, not a document-wide silent failure.
7. **Proof-preserving output.** Every page carries parser identity, parser version, route, page SHA-256, confidence, structure score and warnings.
8. **Task-specific benchmarks.** Measure text fidelity, tables, forms, formulas, reading order, multi-page continuity, latency, cost and downstream QA separately.
9. **Degraded-document court.** Include scanned, rotated, noisy, low-resolution and mixed native/scanned PDFs in regression tests.
10. **No provider maturity inheritance.** A locally passing adapter is not provider-live proof.

## CFBE performance court
Minimum benchmark dimensions:
- pages/second and p50/p95/p99 page latency
- cold vs warm cache throughput
- native-text extraction accuracy
- reading-order fidelity
- table tree similarity / merged-cell fidelity
- formula fidelity
- form/key-value fidelity
- cross-page table and paragraph continuity
- downstream question-answer accuracy
- failure rate and retry rate
- cost per 1,000 pages
- peak memory and CPU/GPU utilization
- provider-specific rate-limit behavior

## Acceptance targets for v1
- deterministic routing and ordered fan-in
- bounded concurrency
- page-level cache
- quality escalation
- explicit provenance
- tests proving routing, cache reuse and parallel speedup

## Not yet claimed
- no Marker, MinerU, Mistral, Google, Adobe, AWS or LandingAI provider adapter is live in this PR
- no production deployment is claimed
- no provider benchmark has yet been run against a Federation corpus
- no 24x7 runtime maturity is claimed
