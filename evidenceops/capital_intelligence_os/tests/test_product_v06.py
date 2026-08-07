from __future__ import annotations
from pathlib import Path
import tempfile,unittest
from evidenceops.capital_intelligence_os.demo_product import build_demo_dashboard
from evidenceops.capital_intelligence_os.diligence import DiligenceEngine
from evidenceops.capital_intelligence_os.models import InformationClass
from evidenceops.capital_intelligence_os.product_ui import DashboardRenderer,WorkspaceComposer
from evidenceops.capital_intelligence_os.tenancy import TenantContext
from evidenceops.capital_intelligence_os.vault import DocumentVault
class VaultTests(unittest.TestCase):
    def setUp(self):self.v=DocumentVault(':memory:'); self.admin=TenantContext('t','u',('admin',)); self.basic=TenantContext('t','b',('operator',)); self.other=TenantContext('other','u',('admin',))
    def tearDown(self):self.v.close()
    def test_hash_duplicate_is_deduplicated(self):
        a,d1=self.v.ingest(self.admin,logical_key='fs',filename='fs.pdf',document_type='audited financial statements',content_type='application/pdf',content=b'abc',information_class=InformationClass.CONFIDENTIAL,source_id='upload'); b,d2=self.v.ingest(self.admin,logical_key='fs-copy',filename='copy.pdf',document_type='audited financial statements',content_type='application/pdf',content=b'abc',information_class=InformationClass.CONFIDENTIAL,source_id='upload'); self.assertFalse(d1); self.assertTrue(d2); self.assertEqual(a.document_id,b.document_id)
    def test_new_version_links_previous(self):
        a,_=self.v.ingest(self.admin,logical_key='fs',filename='v1.pdf',document_type='audited financial statements',content_type='application/pdf',content=b'1',information_class=InformationClass.CONFIDENTIAL,source_id='upload'); b,_=self.v.ingest(self.admin,logical_key='fs',filename='v2.pdf',document_type='audited financial statements',content_type='application/pdf',content=b'2',information_class=InformationClass.CONFIDENTIAL,source_id='upload'); self.assertEqual(b.version_no,2); self.assertEqual(b.previous_document_id,a.document_id)
    def test_basic_user_cannot_read_confidential(self):
        self.v.ingest(self.admin,logical_key='x',filename='x.txt',document_type='material contracts',content_type='text/plain',content=b'x',information_class=InformationClass.CONFIDENTIAL,source_id='upload')
        with self.assertRaises(PermissionError):self.v.latest(self.basic,'x')
    def test_unknown_classification_denied_on_ingest(self):
        with self.assertRaises(PermissionError):self.v.ingest(self.admin,logical_key='x',filename='x',document_type='x',content_type='text/plain',content=b'x',information_class=InformationClass.UNKNOWN,source_id='u')
    def test_tenant_search_is_isolated(self):
        self.v.ingest(self.admin,logical_key='x',filename='customer.txt',document_type='customer revenue schedule',content_type='text/plain',content=b'x',information_class=InformationClass.CONFIDENTIAL,source_id='u',extracted_text='customer concentration revenue'); self.assertEqual(len(self.v.search(self.admin,'customer concentration')),1); self.assertEqual(self.v.search(self.other,'customer concentration'),[])
    def test_search_respects_classification(self):
        self.v.ingest(self.admin,logical_key='x',filename='secret.txt',document_type='material contracts',content_type='text/plain',content=b'x',information_class=InformationClass.PRIVILEGED,source_id='u',extracted_text='change control clause'); self.assertEqual(self.v.search(self.basic,'change control'),[])
    def test_vault_document_types_feed_diligence(self):
        self.v.ingest(self.admin,logical_key='fs',filename='fs.pdf',document_type='audited financial statements',content_type='application/pdf',content=b'1',information_class=InformationClass.CONFIDENTIAL,source_id='u'); self.assertGreater(DiligenceEngine().completeness(DiligenceEngine().standard_profile(),self.v.document_types(self.admin)),0)
class UITests(unittest.TestCase):
    def test_guided_owner_snapshot(self):self.assertEqual(WorkspaceComposer().compose(company_name='Co',mode='GUIDED_OWNER',readiness_score=.68,valuation_range=(10,20),diligence_score=.5,top_risks=['Risk'],next_actions=['Action']).readiness_pct,68)
    def test_invalid_range_rejected(self):
        with self.assertRaises(ValueError):WorkspaceComposer().compose(company_name='Co',mode='GUIDED_OWNER',readiness_score=.5,valuation_range=(20,10),diligence_score=.5,top_risks=[],next_actions=[])
    def test_html_escapes_user_content(self):
        s=WorkspaceComposer().compose(company_name='<script>x</script>',mode='GUIDED_OWNER',readiness_score=.5,valuation_range=(1,2),diligence_score=.5,top_risks=['<b>risk</b>'],next_actions=[]); h=DashboardRenderer().render(s); self.assertNotIn('<script>',h); self.assertIn('&lt;script&gt;',h); self.assertNotIn('<b>risk</b>',h)
    def test_professional_mode_contains_drilldown(self):self.assertIn('Professional drill-down',DashboardRenderer().render(WorkspaceComposer().compose(company_name='Co',mode='PROFESSIONAL',readiness_score=.5,valuation_range=(1,2),diligence_score=.5,top_risks=[],next_actions=[])))
    def test_demo_dashboard_is_written(self):
        with tempfile.TemporaryDirectory() as td:self.assertTrue(build_demo_dashboard(Path(td)/'demo.html')['contains_company'])
if __name__=='__main__':unittest.main()
