import asyncio, unittest, sys
sys.path.insert(0,'evidenceops/document_fabric')
from fabric import DocumentFabric,FabricConfig,FunctionAdapter,PageInput,PageProfile,Route

class DocumentFabricTests(unittest.TestCase):
    def _adapters(self):
        async def native(page,route):
            await asyncio.sleep(0.01)
            return ('weak',0.5,0.5) if page.page_number==4 else (f'native-{page.page_number}',0.95,0.95)
        async def hybrid(page,route): await asyncio.sleep(0.01); return (f'hybrid-{page.page_number}',0.93,0.92)
        async def ocr(page,route): await asyncio.sleep(0.01); return (f'ocr-{page.page_number}',0.91,0.90)
        async def table(page,route): await asyncio.sleep(0.01); return (f'table-{page.page_number}',0.94,0.96)
        return {Route.NATIVE_FAST:FunctionAdapter('native','1',native),Route.HYBRID_LAYOUT:FunctionAdapter('hybrid','1',hybrid),Route.VISION_OCR:FunctionAdapter('ocr','1',ocr),Route.TABLE_SPECIALIST:FunctionAdapter('table','1',table)}
    def test_route_selection(self):
        f=DocumentFabric(self._adapters())
        pages=[PageInput(1,b'a',PageProfile(1,text_chars=1000,image_area_ratio=0.05)),PageInput(2,b'b',PageProfile(2,text_chars=50,image_area_ratio=0.9,has_native_text=False)),PageInput(3,b'c',PageProfile(3,text_chars=500,table_score=0.9))]
        out=asyncio.run(f.process(pages)); self.assertEqual([p['route'] for p in out['pages']],[Route.NATIVE_FAST,Route.VISION_OCR,Route.TABLE_SPECIALIST])
    def test_quality_escalation_and_cache(self):
        f=DocumentFabric(self._adapters()); p=PageInput(4,b'd',PageProfile(4,text_chars=1000,image_area_ratio=0.05))
        first=asyncio.run(f.process([p])); self.assertEqual(first['pages'][0]['route'],Route.HYBRID_LAYOUT); self.assertTrue(first['pages'][0]['warnings'])
        second=asyncio.run(f.process([p])); self.assertEqual(second['metrics']['cache_hits'],1)
    def test_parallelism(self):
        async def slow(page,route): await asyncio.sleep(0.05); return ('ok',0.99,0.99)
        adapters={r:FunctionAdapter(r.value,'1',slow) for r in Route}; pages=[PageInput(i,str(i).encode(),PageProfile(i,text_chars=1000)) for i in range(1,9)]
        fast=DocumentFabric(adapters,FabricConfig(max_concurrency=8)); serial=DocumentFabric(adapters,FabricConfig(max_concurrency=1))
        a=asyncio.run(fast.process(pages)); b=asyncio.run(serial.process(pages)); self.assertLess(a['metrics']['elapsed_ms'],b['metrics']['elapsed_ms']*0.45)
if __name__=='__main__': unittest.main()
