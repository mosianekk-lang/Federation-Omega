from __future__ import annotations
import asyncio, hashlib, time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Awaitable, Callable, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple

class Route(str, Enum):
    NATIVE_FAST='native_fast'; HYBRID_LAYOUT='hybrid_layout'; VISION_OCR='vision_ocr'; TABLE_SPECIALIST='table_specialist'

@dataclass(frozen=True)
class PageProfile:
    page_number:int; text_chars:int=0; image_area_ratio:float=0.0; table_score:float=0.0; formula_score:float=0.0; has_native_text:bool=True

@dataclass(frozen=True)
class PageInput:
    page_number:int; payload:bytes; profile:PageProfile

@dataclass
class ParseResult:
    page_number:int; route:Route; text:str; confidence:float; structure_score:float; parser_name:str; parser_version:str
    elapsed_ms:float=0.0; cache_hit:bool=False; warnings:List[str]=field(default_factory=list); provenance:Dict[str,str]=field(default_factory=dict)

class ParserAdapter(Protocol):
    name:str; version:str
    async def parse(self, page:PageInput, route:Route)->ParseResult: ...

@dataclass(frozen=True)
class QualityPolicy:
    min_confidence:float=0.82; min_structure_score:float=0.75; retry_on_quality_failure:bool=True

@dataclass(frozen=True)
class FabricConfig:
    max_concurrency:int=8; native_text_threshold:int=220; table_specialist_threshold:float=0.72; scanned_image_ratio_threshold:float=0.65; quality:QualityPolicy=QualityPolicy()

class PageRouter:
    def __init__(self, config:FabricConfig): self.config=config
    def choose(self,p:PageProfile)->Route:
        if p.table_score>=self.config.table_specialist_threshold: return Route.TABLE_SPECIALIST
        if (not p.has_native_text) or (p.text_chars<self.config.native_text_threshold and p.image_area_ratio>=self.config.scanned_image_ratio_threshold): return Route.VISION_OCR
        if p.image_area_ratio>0.25 or p.formula_score>0.35 or p.table_score>0.25: return Route.HYBRID_LAYOUT
        return Route.NATIVE_FAST

class MemoryCache:
    def __init__(self): self._data:Dict[str,ParseResult]={}
    def get(self,key:str)->Optional[ParseResult]:
        item=self._data.get(key)
        if item is None: return None
        clone=ParseResult(**asdict(item)); clone.route=Route(clone.route); clone.cache_hit=True; return clone
    def put(self,key:str,value:ParseResult)->None: self._data[key]=ParseResult(**asdict(value))

class DocumentFabric:
    def __init__(self, adapters:Mapping[Route,ParserAdapter], config:FabricConfig=FabricConfig(), cache:Optional[MemoryCache]=None):
        self.adapters=dict(adapters); self.config=config; self.router=PageRouter(config); self.cache=cache or MemoryCache()
    @staticmethod
    def _page_hash(page:PageInput)->str: return hashlib.sha256(page.payload).hexdigest()
    def _cache_key(self,page:PageInput,route:Route,adapter:ParserAdapter)->str:
        raw=f'{self._page_hash(page)}:{page.page_number}:{route.value}:{adapter.name}:{adapter.version}'
        return hashlib.sha256(raw.encode()).hexdigest()
    def _quality_pass(self,r:ParseResult)->bool:
        q=self.config.quality; return r.confidence>=q.min_confidence and r.structure_score>=q.min_structure_score
    async def _parse_once(self,page:PageInput,route:Route)->ParseResult:
        if route not in self.adapters: raise KeyError(f'No parser adapter bound for route={route.value}')
        adapter=self.adapters[route]; key=self._cache_key(page,route,adapter); cached=self.cache.get(key)
        if cached is not None: return cached
        started=time.perf_counter(); result=await adapter.parse(page,route); result.elapsed_ms=(time.perf_counter()-started)*1000.0
        result.provenance.setdefault('page_sha256',self._page_hash(page)); result.provenance.setdefault('route',route.value); self.cache.put(key,result); return result
    async def _process_page(self,page:PageInput,sem:asyncio.Semaphore)->ParseResult:
        async with sem:
            primary=self.router.choose(page.profile); result=await self._parse_once(page,primary)
            if self._quality_pass(result) or not self.config.quality.retry_on_quality_failure: return result
            order={Route.NATIVE_FAST:[Route.HYBRID_LAYOUT,Route.VISION_OCR],Route.HYBRID_LAYOUT:[Route.VISION_OCR],Route.TABLE_SPECIALIST:[Route.HYBRID_LAYOUT,Route.VISION_OCR],Route.VISION_OCR:[]}[primary]
            for route in order:
                if route not in self.adapters: continue
                candidate=await self._parse_once(page,route); candidate.warnings.append(f'Escalated from {primary.value}: confidence={result.confidence:.3f}, structure={result.structure_score:.3f}')
                if self._quality_pass(candidate): return candidate
                result=candidate
            result.warnings.append('Quality gate unresolved after available escalation routes'); return result
    async def process(self,pages:Sequence[PageInput])->Dict[str,object]:
        sem=asyncio.Semaphore(max(1,self.config.max_concurrency)); started=time.perf_counter(); tasks=[asyncio.create_task(self._process_page(p,sem)) for p in pages]
        results=[]; failures=[]
        for page,task in zip(pages,tasks):
            try: results.append(await task)
            except Exception as exc: failures.append({'page_number':page.page_number,'error_type':type(exc).__name__,'error':str(exc)})
        results.sort(key=lambda r:r.page_number); route_counts={}; cache_hits=0
        for r in results: route_counts[r.route.value]=route_counts.get(r.route.value,0)+1; cache_hits+=int(r.cache_hit)
        elapsed_ms=(time.perf_counter()-started)*1000.0
        return {'pages':[asdict(r) for r in results],'failures':failures,'metrics':{'page_count':len(pages),'success_count':len(results),'failure_count':len(failures),'cache_hits':cache_hits,'route_counts':route_counts,'elapsed_ms':elapsed_ms,'pages_per_second':(len(pages)/(elapsed_ms/1000.0)) if elapsed_ms else None}}

class FunctionAdapter:
    def __init__(self,name:str,version:str,fn:Callable[[PageInput,Route],Awaitable[Tuple[str,float,float]]]): self.name=name; self.version=version; self.fn=fn
    async def parse(self,page:PageInput,route:Route)->ParseResult:
        text,confidence,structure=await self.fn(page,route)
        return ParseResult(page.page_number,route,text,confidence,structure,self.name,self.version)
