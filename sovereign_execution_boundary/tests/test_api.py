import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib import request

from seb.api import Handler
from seb.engine import SovereignEngine
from seb.ledger import JsonlLedger
from seb.policy import PolicyEngine
from seb.providers import MockProvider
from seb.router import ProviderRouter
from http.server import ThreadingHTTPServer


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        Handler.engine = SovereignEngine(JsonlLedger(Path(self.tmp.name) / "events.jsonl"),
                                         PolicyEngine(), ProviderRouter([MockProvider("api-mock")]))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def test_health(self):
        with request.urlopen(self.base + "/health") as response:
            body = json.loads(response.read())
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["ledger_valid"])
        self.assertFalse(body["external_effects"])
        self.assertEqual(body["revision"], "local")

    def test_execute_mission(self):
        body = json.dumps({"mission_id":"api-1","objective":"test","prompt":"hello",
                           "acceptance_tests":["accepted=true"]}).encode()
        req = request.Request(self.base + "/v1/missions/execute", data=body,
                              headers={"Content-Type":"application/json"}, method="POST")
        with request.urlopen(req) as response:
            result = json.loads(response.read())
        self.assertEqual(result["state"], "COMPLETED")
        self.assertEqual(result["provider"], "api-mock")


if __name__ == "__main__":
    unittest.main()
