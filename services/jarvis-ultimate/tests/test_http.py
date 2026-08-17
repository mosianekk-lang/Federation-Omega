import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from jarvis import main
from jarvis.orchestrator import Jarvis


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app_patch = patch.object(main, "APP", Jarvis(self.tmp.name))
        self.app_patch.start()
        self.token_patch = patch.dict(os.environ, {"JARVIS_API_TOKEN": "secret"})
        self.token_patch.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), main.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.token_patch.stop()
        self.app_patch.stop()
        self.tmp.cleanup()

    def request(self, path, payload=None, token="secret"):
        data = None if payload is None else json.dumps(payload).encode()
        headers = {"content-type": "application/json"}
        if token is not None:
            headers["authorization"] = f"Bearer {token}"
        request = Request(self.base + path, data=data, headers=headers, method="POST" if payload is not None else "GET")
        with urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read())

    def test_health_is_public_but_execution_policy_is_protected(self):
        status, health = self.request("/health", token=None)
        self.assertEqual(status, 200)
        self.assertEqual(health["directiveEnvelopeSeconds"], 1200)
        with self.assertRaises(HTTPError) as denied:
            self.request("/v1/execution-policy", token=None)
        self.assertEqual(denied.exception.code, 403)
        status, policy = self.request("/v1/execution-policy")
        self.assertEqual(status, 200)
        self.assertEqual(policy["id"], "T20-AO-OMEGA-SCIENTIST-1.0")

    def test_root_page_is_packaged(self):
        request = Request(self.base + "/", headers={"authorization": "Bearer secret"}, method="GET")
        with urlopen(request, timeout=2) as response:
            body = response.read().decode()
        self.assertIn("JARVIS Ultimate Federation", body)

    def test_plan_and_cycle_review(self):
        status, plan = self.request("/v1/plan", {"objective": "Finish safely"})
        self.assertEqual(status, 200)
        self.assertEqual(plan["deadlineAt"] - plan["startedAt"], 1200)
        gates = {gate: True for gate in main.APP.execution.policy.quality_gates}
        status, review = self.request("/v1/cycle-review", {"elapsedSeconds": 500, "qualityGates": gates})
        self.assertEqual(status, 200)
        self.assertTrue(review["cyclePass"])
        self.assertTrue(review["learningHash"])


if __name__ == "__main__":
    unittest.main()
