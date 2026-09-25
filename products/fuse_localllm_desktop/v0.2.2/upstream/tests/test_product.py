
from pathlib import Path
import json, unittest
ROOT=Path(__file__).resolve().parents[1]

class DesktopProductTests(unittest.TestCase):
    def test_ui_views(self):
        x=(ROOT/"ui/index.html").read_text()
        for s in ["view-chat","view-models","view-library","view-apps","view-settings","modelPicker","history"]:
            self.assertIn(s,x)

    def test_streaming_client(self):
        x=(ROOT/"ui/app.js").read_text()
        self.assertIn("getReader()",x)
        self.assertIn("/v1/chat/completions",x)

    def test_runtime_endpoints(self):
        x=(ROOT/"src/main.cpp").read_text()
        for s in ["/v1/fuse/models/local","/v1/fuse/models/select","/api/chat","/api/tags","/api/version","text/event-stream"]:
            self.assertIn(s,x)

    def test_launcher_no_console_app_mode(self):
        x=(ROOT/"src/desktop_launcher.cpp").read_text()
        self.assertIn("CREATE_NO_WINDOW",x)
        self.assertIn('L"--app="',x)
        self.assertIn("http://127.0.0.1:8999/",x)
        self.assertIn("msedge.exe",x)

    def test_product_parity_ledger(self):
        d=json.loads((ROOT/"docs/PRODUCT_PARITY_COURT.json").read_text())
        self.assertEqual(d["failure_fingerprint"],"DEVELOPER_BUNDLE_PRESENTED_AS_DESKTOP_PRODUCT")
        self.assertEqual(d["v020_predicates"]["CHAT_FIRST_UI"],"PASS_SOURCE")

if __name__=="__main__":
    unittest.main()
