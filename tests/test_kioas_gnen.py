import json, pathlib, re, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=ROOT/'systems'/'kioas_gnen'
class TestGNEN(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files=list(SRC.glob('*.gs'))
        cls.text='\n'.join(p.read_text() for p in cls.files)
        cls.manifest=json.loads((SRC/'appsscript.json').read_text())
    def test_version_and_thin_node(self):
        self.assertIn('VERSION: "1.0.0"',self.text)
        self.assertIn('THIN_GOOGLE_NATIVE_EXECUTION_NODE',self.text)
        self.assertIn('PRODUCTION_EFFECT: false',self.text)
    def test_no_dangerous_capabilities(self):
        for forbidden in ['GmailApp.sendEmail','MailApp.sendEmail','DriveApp.getFileById(id).setSharing','grantIam','deleteProject','roles/owner']:
            self.assertNotIn(forbidden,self.text)
    def test_no_arbitrary_external_http(self):
        self.assertIn('GNEN_GOOGLE_HOST_NOT_ALLOWLISTED',self.text)
        self.assertNotIn('eval(',self.text)
        self.assertNotIn('new Function',self.text)
    def test_secret_rejection(self):
        self.assertIn('GNEN_SENSITIVE_PAYLOAD_REJECTED',self.text)
        self.assertIn('SENSITIVE_KEY_PATTERN',self.text)
        self.assertIn('networkCallPerformed:false',self.text)
    def test_authority_hold(self):
        self.assertIn('HELD_AUTHORITY',self.text)
        self.assertRegex(self.text,r'\["A2","A3"\]')
    def test_trigger_singletons(self):
        self.assertIn('COMMAND_TRIGGER_SINGLETON',self.text)
        self.assertIn('HEARTBEAT_TRIGGER_SINGLETON',self.text)
        self.assertIn('GNEN_installTriggers',self.text)
    def test_semantic_readback(self):
        self.assertIn('COMMAND_SEMANTIC_READBACK',self.text)
        self.assertIn('GNEN_APPEND_READBACK_MISMATCH',self.text)
    def test_minimal_scopes(self):
        scopes=set(self.manifest['oauthScopes'])
        self.assertNotIn('https://mail.google.com/',scopes)
        self.assertNotIn('https://www.googleapis.com/auth/cloud-platform',scopes)
        self.assertNotIn('https://www.googleapis.com/auth/script.projects',scopes)
        self.assertIn('https://www.googleapis.com/auth/drive.metadata.readonly',scopes)
        self.assertIn('https://www.googleapis.com/auth/documents.readonly',scopes)
    def test_legacy_compatibility(self):
        self.assertIn('function FED_status()',self.text)
        self.assertIn('function FED_genesisCheck()',self.text)
if __name__=='__main__': unittest.main()
