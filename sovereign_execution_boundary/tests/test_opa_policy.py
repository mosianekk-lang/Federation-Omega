import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from seb.adapters import OpaHttpAdapter
from seb.models import Budget, MissionIR
from seb.policy import OpaPolicyEngine


def mission(authority="A0"):
    return MissionIR("opa-1", "test OPA", (), (), authority,
                     allowed_tools=("local",), budget=Budget(max_tokens=10))


class Stub(BaseHTTPRequestHandler):
    response = {"result": {"allow": True, "reasons": []}}
    observed = None

    def do_POST(self):
        Stub.observed = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        body = json.dumps(Stub.response).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class OpaPolicyTests(unittest.TestCase):
    def setUp(self):
        Stub.response = {"result": {"allow": True, "reasons": []}}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        url = f"http://127.0.0.1:{self.server.server_port}/v1/data/seb/decision"
        self.policy = OpaPolicyEngine(OpaHttpAdapter(url, timeout=0.2))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_real_http_decision_and_input_binding(self):
        result = self.policy.evaluate(mission(), tool="local")
        self.assertTrue(result.allowed)
        self.assertEqual(Stub.observed["input"]["mission"]["fingerprint"], mission().fingerprint)
        self.assertEqual(len(result.decision_id), 64)

    def test_explicit_opa_denial_is_preserved(self):
        Stub.response = {"result": {"allow": False, "reasons": ["authority_exceeds_runtime"]}}
        result = self.policy.evaluate(mission("A3"))
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "authority_exceeds_runtime")

    def test_string_false_cannot_become_allow(self):
        Stub.response = {"result": {"allow": "false", "reasons": []}}
        result = self.policy.evaluate(mission())
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "opa_unavailable_or_invalid")

    def test_missing_result_fails_closed(self):
        Stub.response = {}
        self.assertFalse(self.policy.evaluate(mission()).allowed)

    def test_unreachable_endpoint_fails_closed(self):
        policy = OpaPolicyEngine(OpaHttpAdapter("http://127.0.0.1:1/v1/data/seb/decision", 0.01))
        self.assertFalse(policy.evaluate(mission()).allowed)

    def test_allow_with_reasons_is_rejected_as_contradictory(self):
        Stub.response = {"result": {"allow": True, "reasons": ["unexpected"]}}
        self.assertFalse(self.policy.evaluate(mission()).allowed)


if __name__ == "__main__":
    unittest.main()
