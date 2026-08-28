import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "ops"
for p in (OPS, ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from sovara_local_model_lane_v1 import LocalModelReviewer, _normalize_endpoint


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_local_model_endpoint_is_loopback_only():
    assert _normalize_endpoint("http://127.0.0.1:11434") == "http://127.0.0.1:11434/v1/chat/completions"
    try:
        _normalize_endpoint("https://example.invalid/v1")
    except ValueError as exc:
        assert str(exc) == "LOCAL_MODEL_ENDPOINT_MUST_BE_LOOPBACK"
    else:
        raise AssertionError("remote endpoint must fail closed")


def test_local_model_review_is_proposal_only_and_does_not_execute_code():
    observed = {}

    def opener(request, timeout):
        observed["payload"] = json.loads(request.data.decode("utf-8"))
        observed["auth"] = request.headers.get("Authorization")
        return FakeResponse(
            {
                "model": "local/coder",
                "choices": [{"message": {"content": '{"summary":"local review"}'}}],
            }
        )

    reviewer = LocalModelReviewer(
        endpoint="http://localhost:9000",
        model="local/coder",
        token="runtime-only-test-token",
        opener=opener,
    )
    receipt = reviewer("raise RuntimeError('must never execute')", "python", "review")
    assert receipt.lane_type == "LOCAL_MODEL"
    assert receipt.provider == "SOVARA_LOOPBACK"
    assert receipt.metadata["code_executed"] is False
    assert receipt.metadata["credential_value_recorded"] is False
    assert "runtime-only-test-token" not in json.dumps(receipt.metadata)
    assert "<UNTRUSTED_CODE>" in observed["payload"]["messages"][1]["content"]
