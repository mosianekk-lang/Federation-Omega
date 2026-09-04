import io
import json
import os
import unittest
from unittest.mock import patch

from seb.models import FailureClass, ProviderRequest
from seb.providers import OpenRouterProvider, ProviderFailure
from seb.engine import SovereignEngine
from seb.ledger import JsonlLedger
from seb.policy import PolicyEngine
from seb.router import ProviderRouter
from seb.models import Budget, MissionIR
import tempfile
from pathlib import Path


class _Response:
    def __init__(self, value):
        self.body = json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class OpenRouterProviderTests(unittest.TestCase):
    def request(self, model="openrouter/free"):
        return ProviderRequest("m1", "r1", "return JSON", {"type": "object"}, model, 32, "public")

    def response(self, **changes):
        value = {
            "id": "gen-123",
            "model": "meta-llama/llama-3.3-8b-instruct:free",
            "provider": "Example Provider",
            "choices": [{"message": {"content": '{"accepted":true}'}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7, "cost": 0},
        }
        value.update(changes)
        return value

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-only"})
    @patch("seb.providers.request.urlopen")
    def test_preserves_requested_and_provider_observed_metadata(self, urlopen):
        urlopen.return_value = _Response(self.response())
        result = OpenRouterProvider(require_zero_cost=True).complete(self.request())
        self.assertEqual(result.requested_model, "openrouter/free")
        self.assertEqual(result.model, "meta-llama/llama-3.3-8b-instruct:free")
        self.assertEqual(result.generation_id, "gen-123")
        self.assertEqual(result.downstream_provider, "Example Provider")
        self.assertEqual(result.usage["total_tokens"], 7)
        self.assertEqual(result.cost_usd, 0.0)
        sent = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(sent["model"], "openrouter/free")

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-only"})
    @patch("seb.providers.request.urlopen")
    def test_zero_cost_lane_rejects_missing_cost(self, urlopen):
        response = self.response()
        response["usage"].pop("cost")
        urlopen.return_value = _Response(response)
        with self.assertRaises(ProviderFailure) as caught:
            OpenRouterProvider(require_zero_cost=True).complete(self.request())
        self.assertEqual(caught.exception.failure_class, FailureClass.MALFORMED_OUTPUT)

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-only"})
    @patch("seb.providers.request.urlopen")
    def test_zero_cost_lane_rejects_charge(self, urlopen):
        urlopen.return_value = _Response(self.response(usage={"total_tokens": 7, "cost": 0.01}))
        with self.assertRaises(ProviderFailure) as caught:
            OpenRouterProvider(require_zero_cost=True).complete(self.request())
        self.assertEqual(caught.exception.failure_class, FailureClass.BUDGET_EXCEEDED)

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-only"})
    @patch("seb.providers.request.urlopen")
    def test_missing_observed_model_is_malformed_not_request_echo(self, urlopen):
        response = self.response()
        response.pop("model")
        urlopen.return_value = _Response(response)
        with self.assertRaises(ProviderFailure) as caught:
            OpenRouterProvider().complete(self.request("some/requested-model"))
        self.assertEqual(caught.exception.failure_class, FailureClass.MALFORMED_OUTPUT)

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-only"})
    @patch("seb.providers.request.urlopen")
    def test_engine_carries_requested_model_and_metadata_end_to_end(self, urlopen):
        urlopen.return_value = _Response(self.response())
        with tempfile.TemporaryDirectory() as directory:
            engine = SovereignEngine(JsonlLedger(Path(directory) / "events.jsonl"),
                                     PolicyEngine(), ProviderRouter([OpenRouterProvider(require_zero_cost=True)]))
            mission = MissionIR("m1", "prove lane", (), (), data_class="public",
                                budget=Budget(max_tokens=32))
            result = engine.execute(mission, "return JSON", {"type": "object"},
                                    lambda value: value.get("accepted") is True,
                                    requested_model="openrouter/free")
        self.assertEqual(result.provider_metadata["requested_model"], "openrouter/free")
        self.assertEqual(result.provider_metadata["resolved_model"],
                         "meta-llama/llama-3.3-8b-instruct:free")
        self.assertEqual(result.provider_metadata["generation_id"], "gen-123")
        self.assertEqual(result.provider_metadata["cost_usd"], 0.0)


if __name__ == "__main__":
    unittest.main()
