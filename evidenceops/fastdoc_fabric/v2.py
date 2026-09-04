from __future__ import annotations
'FastDoc v2 - staged, cache-first, completion-order document intelligence.\n\nDesign contract\n---------------\nThe first useful answer must not wait for whole-document OCR or rich layout parsing.\nThe blocking path is deliberately narrow:\n\n    file hash -> native page extraction -> page index -> bounded context pack\n\nSparse/ambiguous pages are flagged for selective OCR/vision after the native path.\nRich hierarchy/table/visual enrichment is lazy and receiver-specific.  No external\nprovider call is performed by this module.\n\nThis module is a clean-room Federation implementation of public engineering\npatterns: process-isolated PDF extraction, bounded in-flight work, batch tuning,\ncontent-addressed reuse, staged enrichment, completion-order streaming, and\nretrieval-sized context construction.  It does not copy third-party source code.\n'
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import string
import subprocess
import tempfile
import time
from typing import Any, Iterable, Iterator, Mapping, Sequence
EXTRACTOR = 'pymupdf-fastdoc-v2'
SCHEMA = 'FEDERATION_FASTDOC_V2_1'

def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)

def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()

def sha256_file(path: str | Path, chunk_size: int=1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()

class LatencyProfile(str, Enum):
    INTERACTIVE = 'INTERACTIVE'
    THROUGHPUT = 'THROUGHPUT'

@dataclass(frozen=True, slots=True)
class FastDocV2Config:
    profile: LatencyProfile = LatencyProfile.INTERACTIVE
    workers: int = 0
    batch_pages: int = 0
    max_inflight_batches: int = 4
    min_native_chars: int = 80
    min_native_quality: float = 0.8
    context_max_chars: int = 24000
    context_hit_limit: int = 8
    context_neighbor_pages: int = 1
    def resolved(self, page_count: int) -> 'FastDocV2Config':
        cpu = max(1, os.cpu_count() or 1)
        workers = self.workers or min(4, cpu, max(1, page_count))
        if self.batch_pages:
            batch_pages = self.batch_pages
        elif self.profile is LatencyProfile.INTERACTIVE:
            batch_pages = 16
        else:
            batch_pages = 32
        return FastDocV2Config(profile=self.profile, workers=max(1, min(int(workers), max(1, page_count))), batch_pages=max(1, int(batch_pages)), max_inflight_batches=max(1, int(self.max_inflight_batches)), min_native_chars=max(1, int(self.min_native_chars)), min_native_quality=min(1.0, max(0.0, float(self.min_native_quality))), context_max_chars=max(1000, int(self.context_max_chars)), context_hit_limit=max(1, int(self.context_hit_limit)), context_neighbor_pages=max(0, int(self.context_neighbor_pages)))

@dataclass(frozen=True, slots=True)
class PageV2:
    page_number: int
    text: str
    block_count: int
    image_count: int
    width: float
    height: float
    quality: float
    route: str
    payload_sha256: str
    extraction_ms: float
    metadata: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class PageBatchV2:
    page_numbers: tuple[int, ...]
    pages: tuple[PageV2, ...]
    elapsed_seconds: float

@dataclass(frozen=True, slots=True)
class SearchHitV2:
    page_number: int
    score: float
    snippet: str

@dataclass(frozen=True, slots=True)
class ContextPage:
    page_number: int
    text: str
    payload_sha256: str
    reason: str

@dataclass(frozen=True, slots=True)
class ContextPack:
    document_sha256: str
    query: str
    pages: tuple[ContextPage, ...]
    total_chars: int
    page_count: int
    truncated: bool
    build_ms: float

@dataclass(frozen=True, slots=True)
class FastDocV2Receipt:
    schema: str
    document_sha256: str
    page_count: int
    processed_pages: int
    page_map_hits: int
    payload_reuse_hits: int
    escalation_pages: tuple[int, ...]
    ttfr_seconds: float
    extraction_seconds: float
    index_seconds: float
    total_native_stage_seconds: float
    pages_per_second: float
    workers: int
    batch_pages: int
    max_inflight_batches: int
    profile: str
    warm_unchanged: bool
    provider_effect: bool = False

@dataclass(frozen=True, slots=True)
class OCRV2Receipt:
    requested_pages: tuple[int, ...]
    processed_pages: tuple[int, ...]
    cache_hits: int
    elapsed_seconds: float
    dpi: int
    language: str
    provider_effect: bool = False

def _text_quality(text: str) -> float:
    text = text.strip()
    if not text:
        return 0.0
    replacement = text.count('�') + text.count('<?>')
    printable = sum((ch in string.printable or ch.isprintable() for ch in text))
    printable_ratio = printable / max(1, len(text))
    garbled_ratio = replacement / max(1, len(text))
    return min(1.0, max(0.0, printable_ratio - 4.0 * garbled_ratio))

def _payload_hash(*, text: str, block_count: int, image_count: int, width: float, height: float, extractor_version: str) -> str:
    return _sha256_text(_canonical_json({'text': text, 'block_count': int(block_count), 'image_count': int(image_count), 'width': round(float(width), 3), 'height': round(float(height), 3), 'extractor': EXTRACTOR, 'extractor_version': extractor_version}))

def _pymupdf_version() -> str:
    import pymupdf
    return getattr(pymupdf, '__version__', 'unknown')

def _extract_batch(payload: tuple[str, tuple[int, ...], int, float]) -> tuple[PageV2, ...]:
    path, page_numbers, min_native_chars, min_native_quality = payload
    import pymupdf
    flags = pymupdf.TEXT_PRESERVE_LIGATURES | pymupdf.TEXT_PRESERVE_WHITESPACE
    version = getattr(pymupdf, '__version__', 'unknown')
    pages: list[PageV2] = []
    with pymupdf.open(path) as doc:
        for page_number in page_numbers:
            start = time.perf_counter()
            page = doc[page_number - 1]
            blocks = page.get_text('blocks', flags=flags)
            text = '\n'.join((str(block[4]).strip() for block in blocks if len(block) > 4 and str(block[4]).strip()))
            image_count = len(page.get_images(full=True))
            quality = _text_quality(text)
            if len(text.strip()) >= min_native_chars and quality >= min_native_quality:
                route = 'NATIVE_FAST'
            elif image_count:
                route = 'SELECTIVE_OCR'
            else:
                route = 'LAYOUT_REVIEW'
            pages.append(PageV2(page_number=page_number, text=text, block_count=len(blocks), image_count=image_count, width=float(page.rect.width), height=float(page.rect.height), quality=quality, route=route, payload_sha256=_payload_hash(text=text, block_count=len(blocks), image_count=image_count, width=page.rect.width, height=page.rect.height, extractor_version=version), extraction_ms=(time.perf_counter() - start) * 1000.0, metadata={'extractor': EXTRACTOR, 'extractor_version': version}))
    return tuple(pages)

def _ordered_pages(page_count: int, priority_pages: Iterable[int]=()) -> tuple[int, ...]:
    seen: set[int] = set()
    result: list[int] = []
    for page in priority_pages:
        page = int(page)
        if 1 <= page <= page_count and page not in seen:
            result.append(page)
            seen.add(page)
    for page in range(1, page_count + 1):
        if page not in seen:
            result.append(page)
    return tuple(result)

def _chunk_pages(page_numbers: Sequence[int], batch_pages: int) -> list[tuple[int, ...]]:
    return [tuple(page_numbers[i:i + batch_pages]) for i in range(0, len(page_numbers), batch_pages)]

class SQLiteContentStoreV2:
    def __init__(self, path: str | Path=':memory:') -> None:
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('PRAGMA synchronous=NORMAL')
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents(
              document_sha TEXT NOT NULL, extractor TEXT NOT NULL, extractor_version TEXT NOT NULL,
              options_sha TEXT NOT NULL, page_count INTEGER NOT NULL, complete INTEGER NOT NULL DEFAULT 0,
              escalation_json TEXT NOT NULL DEFAULT '[]', PRIMARY KEY(document_sha, extractor, extractor_version, options_sha));
            CREATE TABLE IF NOT EXISTS payloads(
              payload_sha TEXT PRIMARY KEY, text TEXT NOT NULL, block_count INTEGER NOT NULL, image_count INTEGER NOT NULL,
              width REAL NOT NULL, height REAL NOT NULL, quality REAL NOT NULL, route TEXT NOT NULL, metadata_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS page_map(
              document_sha TEXT NOT NULL, page_number INTEGER NOT NULL, extractor TEXT NOT NULL, extractor_version TEXT NOT NULL,
              options_sha TEXT NOT NULL, payload_sha TEXT NOT NULL,
              PRIMARY KEY(document_sha, page_number, extractor, extractor_version, options_sha));
            CREATE TABLE IF NOT EXISTS enrichments(
              document_sha TEXT NOT NULL, page_number INTEGER NOT NULL, extractor_version TEXT NOT NULL, options_sha TEXT NOT NULL,
              kind TEXT NOT NULL, text TEXT NOT NULL, metadata_json TEXT NOT NULL,
              PRIMARY KEY(document_sha, page_number, extractor_version, options_sha, kind));
            """)
        self.fts_enabled = True
        try:
            self.conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS page_fts USING fts5(document_sha UNINDEXED,page_number UNINDEXED,payload_sha UNINDEXED,text,tokenize='unicode61')")
        except sqlite3.OperationalError:
            self.fts_enabled = False
            self.conn.execute('CREATE TABLE IF NOT EXISTS page_fts_fallback(document_sha TEXT,page_number INTEGER,payload_sha TEXT,text TEXT,PRIMARY KEY(document_sha,page_number))')
        self.conn.commit()
    @staticmethod
    def options_sha(options: Mapping[str, Any] | None=None) -> str:
        return _sha256_text(_canonical_json(options or {}))
    def _key(self, document_sha: str, extractor_version: str, options: Mapping[str, Any] | None) -> tuple[str, str, str, str]:
        return (document_sha, EXTRACTOR, extractor_version, self.options_sha(options))
    def document_status(self, document_sha: str, extractor_version: str, options: Mapping[str, Any] | None=None) -> tuple[int, bool, tuple[int, ...]] | None:
        row = self.conn.execute('SELECT page_count,complete,escalation_json FROM documents WHERE document_sha=? AND extractor=? AND extractor_version=? AND options_sha=?', self._key(document_sha, extractor_version, options)).fetchone()
        if not row:
            return None
        return (int(row[0]), bool(row[1]), tuple((int(x) for x in json.loads(row[2]))))
    def cached_page_numbers(self, document_sha: str, extractor_version: str, options: Mapping[str, Any] | None=None) -> set[int]:
        rows = self.conn.execute('SELECT page_number FROM page_map WHERE document_sha=? AND extractor=? AND extractor_version=? AND options_sha=?', self._key(document_sha, extractor_version, options))
        return {int(row[0]) for row in rows}
    def put_pages(self, document_sha: str, pages: Sequence[PageV2], extractor_version: str, options: Mapping[str, Any] | None=None) -> int:
        options_sha = self.options_sha(options)
        reuse_hits = 0
        with self.conn:
            for page in pages:
                existed = self.conn.execute('SELECT 1 FROM payloads WHERE payload_sha=?', (page.payload_sha256,)).fetchone() is not None
                reuse_hits += int(existed)
                self.conn.execute('INSERT OR IGNORE INTO payloads(payload_sha,text,block_count,image_count,width,height,quality,route,metadata_json) VALUES (?,?,?,?,?,?,?,?,?)', (page.payload_sha256, page.text, page.block_count, page.image_count, page.width, page.height, page.quality, page.route, _canonical_json(dict(page.metadata))))
                self.conn.execute('INSERT OR REPLACE INTO page_map(document_sha,page_number,extractor,extractor_version,options_sha,payload_sha) VALUES (?,?,?,?,?,?)', (document_sha, page.page_number, EXTRACTOR, extractor_version, options_sha, page.payload_sha256))
                if self.fts_enabled:
                    self.conn.execute('DELETE FROM page_fts WHERE document_sha=? AND page_number=?', (document_sha, page.page_number))
                    self.conn.execute('INSERT INTO page_fts(document_sha,page_number,payload_sha,text) VALUES (?,?,?,?)', (document_sha, page.page_number, page.payload_sha256, page.text))
                else:
                    self.conn.execute('INSERT OR REPLACE INTO page_fts_fallback(document_sha,page_number,payload_sha,text) VALUES (?,?,?,?)', (document_sha, page.page_number, page.payload_sha256, page.text))
        return reuse_hits
    def finalize_document(self, document_sha: str, page_count: int, escalation_pages: Sequence[int], extractor_version: str, options: Mapping[str, Any] | None=None) -> None:
        with self.conn:
            self.conn.execute('INSERT OR REPLACE INTO documents(document_sha,extractor,extractor_version,options_sha,page_count,complete,escalation_json) VALUES (?,?,?,?,?,?,?)', (document_sha, EXTRACTOR, extractor_version, self.options_sha(options), int(page_count), 1, json.dumps(sorted({int(x) for x in escalation_pages}))))
    def get_page(self, document_sha: str, page_number: int, extractor_version: str, options: Mapping[str, Any] | None=None) -> PageV2 | None:
        row = self.conn.execute('SELECT p.text,p.block_count,p.image_count,p.width,p.height,p.quality,p.route,p.payload_sha,p.metadata_json FROM page_map m JOIN payloads p ON p.payload_sha=m.payload_sha WHERE m.document_sha=? AND m.page_number=? AND m.extractor=? AND m.extractor_version=? AND m.options_sha=?', (document_sha, int(page_number), EXTRACTOR, extractor_version, self.options_sha(options))).fetchone()
        if not row:
            return None
        return PageV2(page_number=int(page_number), text=row[0], block_count=int(row[1]), image_count=int(row[2]), width=float(row[3]), height=float(row[4]), quality=float(row[5]), route=row[6], payload_sha256=row[7], extraction_ms=0.0, metadata=json.loads(row[8]))
    def has_enrichment(self, document_sha: str, page_number: int, extractor_version: str, kind: str, options: Mapping[str, Any] | None=None) -> bool:
        return self.conn.execute('SELECT 1 FROM enrichments WHERE document_sha=? AND page_number=? AND extractor_version=? AND options_sha=? AND kind=?', (document_sha, int(page_number), extractor_version, self.options_sha(options), kind)).fetchone() is not None
    def put_enrichment(self, document_sha: str, page_number: int, extractor_version: str, kind: str, text: str, *, options: Mapping[str, Any] | None=None, metadata: Mapping[str, Any] | None=None) -> None:
        page = self.get_page(document_sha, page_number, extractor_version, options)
        if page is None:
            raise KeyError(f'PAGE_NOT_MAPPED:{page_number}')
        with self.conn:
            self.conn.execute('INSERT OR REPLACE INTO enrichments(document_sha,page_number,extractor_version,options_sha,kind,text,metadata_json) VALUES (?,?,?,?,?,?,?)', (document_sha, int(page_number), extractor_version, self.options_sha(options), kind, text, _canonical_json(metadata or {})))
            effective = text if len(text.strip()) > len(page.text.strip()) + 40 else page.text
            if self.fts_enabled:
                self.conn.execute('DELETE FROM page_fts WHERE document_sha=? AND page_number=?', (document_sha, int(page_number)))
                self.conn.execute('INSERT INTO page_fts(document_sha,page_number,payload_sha,text) VALUES (?,?,?,?)', (document_sha, int(page_number), page.payload_sha256, effective))
            else:
                self.conn.execute('INSERT OR REPLACE INTO page_fts_fallback(document_sha,page_number,payload_sha,text) VALUES (?,?,?,?)', (document_sha, int(page_number), page.payload_sha256, effective))
    def best_text(self, document_sha: str, page_number: int, extractor_version: str, options: Mapping[str, Any] | None=None) -> tuple[str, str]:
        page = self.get_page(document_sha, page_number, extractor_version, options)
        if page is None:
            return ('', 'MISSING')
        row = self.conn.execute('SELECT kind,text FROM enrichments WHERE document_sha=? AND page_number=? AND extractor_version=? AND options_sha=? ORDER BY length(text) DESC LIMIT 1', (document_sha, int(page_number), extractor_version, self.options_sha(options))).fetchone()
        if row and len(str(row[1]).strip()) > len(page.text.strip()) + 40:
            return (str(row[1]), str(row[0]))
        return (page.text, 'NATIVE')
    def search(self, document_sha: str, query: str, limit: int=8) -> list[SearchHitV2]:
        terms = [term for term in re.findall('[\\w.-]+', query) if len(term) > 1]
        if not terms:
            return []
        limit = max(1, int(limit))
        if self.fts_enabled:
            fts_query = ' OR '.join((f'"{term.replace(chr(34), "")}"' for term in terms))
            rows = self.conn.execute("SELECT page_number,bm25(page_fts),snippet(page_fts,3,'[',']','...',22) FROM page_fts WHERE page_fts MATCH ? AND document_sha=? ORDER BY bm25(page_fts) LIMIT ?", (fts_query, document_sha, limit)).fetchall()
            return [SearchHitV2(int(page), float(score), snippet) for page, score, snippet in rows]
        pattern = '%' + '%'.join(terms) + '%'
        rows = self.conn.execute('SELECT page_number,text FROM page_fts_fallback WHERE document_sha=? AND text LIKE ? LIMIT ?', (document_sha, pattern, limit)).fetchall()
        return [SearchHitV2(int(page), 0.0, text[:350]) for page, text in rows]
    def close(self) -> None:
        self.conn.close()

class FastDocV2:
    def __init__(self, store: SQLiteContentStoreV2, config: FastDocV2Config | None=None) -> None:
        self.store = store
        self.config = config or FastDocV2Config()
    @staticmethod
    def page_count(path: str | Path) -> int:
        import pymupdf
        with pymupdf.open(str(path)) as doc:
            return len(doc)
    def iter_native_batches(self, path: str | Path, page_numbers: Sequence[int], *, resolved: FastDocV2Config) -> Iterator[PageBatchV2]:
        batches = _chunk_pages(page_numbers, resolved.batch_pages)
        if not batches:
            return
        if resolved.workers == 1:
            for batch in batches:
                start = time.perf_counter()
                pages = _extract_batch((str(path), batch, resolved.min_native_chars, resolved.min_native_quality))
                yield PageBatchV2(batch, pages, time.perf_counter() - start)
            return
        with ProcessPoolExecutor(max_workers=resolved.workers) as pool:
            iterator = iter(batches)
            pending: dict[Any, tuple[int, ...]] = {}
            for _ in range(min(resolved.max_inflight_batches, len(batches))):
                try:
                    batch = next(iterator)
                except StopIteration:
                    break
                pending[pool.submit(_extract_batch, (str(path), batch, resolved.min_native_chars, resolved.min_native_quality))] = batch
            while pending:
                done, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
                for future in done:
                    batch = pending.pop(future)
                    start = time.perf_counter()
                    pages = future.result()
                    yield PageBatchV2(batch, pages, max(0.0, time.perf_counter() - start))
                    try:
                        next_batch = next(iterator)
                    except StopIteration:
                        continue
                    pending[pool.submit(_extract_batch, (str(path), next_batch, resolved.min_native_chars, resolved.min_native_quality))] = next_batch
    def ingest(self, path: str | Path, *, options: Mapping[str, Any] | None=None, priority_pages: Iterable[int]=()) -> FastDocV2Receipt:
        path = Path(path)
        document_sha = sha256_file(path)
        page_count = self.page_count(path)
        extractor_version = _pymupdf_version()
        resolved = self.config.resolved(page_count)
        status = self.store.document_status(document_sha, extractor_version, options)
        if status and status[0] == page_count and status[1]:
            return FastDocV2Receipt(schema=SCHEMA, document_sha256=document_sha, page_count=page_count, processed_pages=0, page_map_hits=page_count, payload_reuse_hits=0, escalation_pages=status[2], ttfr_seconds=0.0, extraction_seconds=0.0, index_seconds=0.0, total_native_stage_seconds=0.0, pages_per_second=0.0, workers=resolved.workers, batch_pages=resolved.batch_pages, max_inflight_batches=resolved.max_inflight_batches, profile=resolved.profile.value, warm_unchanged=True)
        start = time.perf_counter()
        cached = self.store.cached_page_numbers(document_sha, extractor_version, options)
        ordered = _ordered_pages(page_count, priority_pages)
        missing = tuple((page for page in ordered if page not in cached))
        ttfr = 0.0
        extraction_started = time.perf_counter()
        payload_reuse = 0
        escalation: set[int] = set()
        index_seconds = 0.0
        first = True
        for batch in self.iter_native_batches(path, missing, resolved=resolved):
            if first:
                ttfr = time.perf_counter() - extraction_started
                first = False
            index_start = time.perf_counter()
            payload_reuse += self.store.put_pages(document_sha, batch.pages, extractor_version, options)
            index_seconds += time.perf_counter() - index_start
            for page in batch.pages:
                if page.route != 'NATIVE_FAST':
                    escalation.add(page.page_number)
        extraction_seconds = time.perf_counter() - extraction_started
        for page_number in cached:
            page = self.store.get_page(document_sha, page_number, extractor_version, options)
            if page and page.route != 'NATIVE_FAST':
                escalation.add(page_number)
        self.store.finalize_document(document_sha, page_count, tuple(escalation), extractor_version, options)
        total = time.perf_counter() - start
        pps = len(missing) / extraction_seconds if missing and extraction_seconds else 0.0
        return FastDocV2Receipt(schema=SCHEMA, document_sha256=document_sha, page_count=page_count, processed_pages=len(missing), page_map_hits=len(cached), payload_reuse_hits=payload_reuse, escalation_pages=tuple(sorted(escalation)), ttfr_seconds=ttfr, extraction_seconds=extraction_seconds, index_seconds=index_seconds, total_native_stage_seconds=total, pages_per_second=pps, workers=resolved.workers, batch_pages=resolved.batch_pages, max_inflight_batches=resolved.max_inflight_batches, profile=resolved.profile.value, warm_unchanged=False)
    def enrich_local_ocr(self, path: str | Path, *, document_sha256: str, page_numbers: Iterable[int], options: Mapping[str, Any] | None=None, dpi: int=120, language: str='eng') -> OCRV2Receipt:
        if shutil.which('tesseract') is None:
            raise RuntimeError('LOCAL_TESSERACT_UNAVAILABLE')
        import pymupdf
        version = _pymupdf_version()
        requested = tuple(sorted({int(x) for x in page_numbers}))
        missing = [page for page in requested if not self.store.has_enrichment(document_sha256, page, version, 'LOCAL_OCR', options)]
        start = time.perf_counter()
        processed: list[int] = []
        with pymupdf.open(str(path)) as doc:
            for page_number in missing:
                if page_number < 1 or page_number > len(doc):
                    raise ValueError(f'PAGE_OUT_OF_RANGE:{page_number}')
                page = doc[page_number - 1]
                pix = page.get_pixmap(dpi=int(dpi), alpha=False, colorspace=pymupdf.csGRAY)
                fd, tmp = tempfile.mkstemp(suffix='.png')
                os.close(fd)
                try:
                    pix.save(tmp)
                    proc = subprocess.run(['tesseract', tmp, 'stdout', '-l', language, '--psm', '6'], check=True, capture_output=True, text=True, timeout=120)
                    text = proc.stdout
                finally:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
                self.store.put_enrichment(document_sha256, page_number, version, 'LOCAL_OCR', text, options=options, metadata={'dpi': int(dpi), 'language': language, 'provider_effect': False, 'backend': 'tesseract-cli'})
                processed.append(page_number)
        return OCRV2Receipt(requested_pages=requested, processed_pages=tuple(processed), cache_hits=len(requested) - len(missing), elapsed_seconds=time.perf_counter() - start, dpi=int(dpi), language=language)

class ContextPackBuilder:
    def __init__(self, store: SQLiteContentStoreV2, config: FastDocV2Config | None=None) -> None:
        self.store = store
        self.config = config or FastDocV2Config()
    def build(self, *, document_sha256: str, extractor_version: str, query: str, options: Mapping[str, Any] | None=None, escalation_pages: Iterable[int]=(), max_chars: int | None=None) -> ContextPack:
        start = time.perf_counter()
        limit_chars = max_chars or self.config.context_max_chars
        hits = self.store.search(document_sha256, query, self.config.context_hit_limit)
        reasons: dict[int, str] = {}
        ordered: list[int] = []
        def add(page_number: int, reason: str) -> None:
            if page_number < 1 or page_number in reasons:
                return
            reasons[page_number] = reason
            ordered.append(page_number)
        for hit in hits:
            add(hit.page_number, 'SEARCH_HIT')
            for delta in range(1, self.config.context_neighbor_pages + 1):
                add(hit.page_number - delta, 'SEARCH_NEIGHBOR')
                add(hit.page_number + delta, 'SEARCH_NEIGHBOR')
        for page in escalation_pages:
            add(int(page), 'ESCALATION')
        pages: list[ContextPage] = []
        total_chars = 0
        truncated = False
        for page_number in ordered:
            page = self.store.get_page(document_sha256, page_number, extractor_version, options)
            if page is None:
                continue
            text, source_kind = self.store.best_text(document_sha256, page_number, extractor_version, options)
            if not text.strip():
                continue
            remaining = limit_chars - total_chars
            if remaining <= 0:
                truncated = True
                break
            if len(text) > remaining:
                text = text[:remaining]
                truncated = True
            reason = reasons[page_number] if source_kind == 'NATIVE' else f'{reasons[page_number]}+{source_kind}'
            pages.append(ContextPage(page_number, text, page.payload_sha256, reason))
            total_chars += len(text)
            if total_chars >= limit_chars:
                break
        return ContextPack(document_sha256=document_sha256, query=query, pages=tuple(pages), total_chars=total_chars, page_count=len(pages), truncated=truncated, build_ms=(time.perf_counter() - start) * 1000.0)
