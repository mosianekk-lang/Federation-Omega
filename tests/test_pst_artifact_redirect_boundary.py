from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import unittest
import urllib.error
from email.message import Message
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pst_artifact_redirect_boundary",
    ROOT / "ops" / "run_evidenceops_pst_v2_composite_verify.py",
)
assert SPEC and SPEC.loader
ADAPTER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ADAPTER
SPEC.loader.exec_module(ADAPTER)


class RedirectOpener:
    def __init__(self, location: str):
        self.location = location
        self.requests = []

    def open(self, request, timeout=0):
        self.requests.append(request)
        headers = Message()
        headers["Location"] = self.location
        raise urllib.error.HTTPError(
            request.full_url,
            302,
            "Found",
            headers,
            None,
        )


class PstArtifactRedirectBoundaryTests(unittest.TestCase):
    def test_storage_headers_never_contain_repository_authorization(self):
        headers = {
            key.lower(): value
            for key, value in ADAPTER.signed_storage_headers().items()
        }
        self.assertNotIn("authorization", headers)

    def test_api_headers_do_contain_repository_authorization(self):
        headers = {
            key.lower(): value
            for key, value in ADAPTER.github_api_headers("test-token").items()
        }
        self.assertEqual("Bearer test-token", headers["authorization"])

    def test_redirect_download_strips_auth_on_storage_request(self):
        signed_url = "https://blob.example.invalid/object?signature=temporary"
        opener = RedirectOpener(signed_url)
        storage_requests = []
        original_build_opener = ADAPTER.urllib.request.build_opener
        original_urlopen = ADAPTER.urllib.request.urlopen
        original_sleep = ADAPTER.time.sleep
        previous_token = os.environ.get("GITHUB_TOKEN")

        def fake_urlopen(request, timeout=0):
            storage_requests.append(request)
            return io.BytesIO(b"verified-zip-bytes")

        ADAPTER.urllib.request.build_opener = lambda *handlers: opener
        ADAPTER.urllib.request.urlopen = fake_urlopen
        ADAPTER.time.sleep = lambda *_: None
        os.environ["GITHUB_TOKEN"] = "repository-token"
        try:
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "artifact.zip"
                ADAPTER.download_artifact(
                    "mosianekk-lang/Federation-Omega",
                    123,
                    output,
                )
                self.assertEqual(b"verified-zip-bytes", output.read_bytes())
        finally:
            ADAPTER.urllib.request.build_opener = original_build_opener
            ADAPTER.urllib.request.urlopen = original_urlopen
            ADAPTER.time.sleep = original_sleep
            if previous_token is None:
                os.environ.pop("GITHUB_TOKEN", None)
            else:
                os.environ["GITHUB_TOKEN"] = previous_token

        self.assertEqual(1, len(opener.requests))
        api_headers = {
            key.lower(): value
            for key, value in opener.requests[0].header_items()
        }
        self.assertEqual(
            "Bearer repository-token",
            api_headers["authorization"],
        )

        self.assertEqual(1, len(storage_requests))
        storage_headers = {
            key.lower(): value
            for key, value in storage_requests[0].header_items()
        }
        self.assertNotIn("authorization", storage_headers)
        self.assertEqual(signed_url, storage_requests[0].full_url)

    def test_non_redirect_http_error_is_not_misclassified(self):
        headers = Message()
        error = urllib.error.HTTPError(
            "https://api.github.com/example",
            401,
            "Unauthorized",
            headers,
            None,
        )
        self.assertIsNone(ADAPTER._location_from_redirect(error))


if __name__ == "__main__":
    unittest.main()
