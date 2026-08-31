from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from evidenceops.caseforge.openai_provider_adapter import (
    OpenAIProviderAdapterError,
    ProviderReadbackEvidence,
)
from federation.idea_to_system_compiler import compile_idea_to_system
from federation.openai_build_generator import OpenAIResponsesBuildGenerator


class FakeResponses:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(dict(kwargs))
        return SimpleNamespace(
            id="resp_build_001",
            model="gpt-provider-returned-model",
            status="completed",
            created_at=1788196000,
            output_text=self.output_text,
            _request_id="req_build_001",
        )


class FakeClient:
    def __init__(self, output_text: str) -> None:
        self.responses = FakeResponses(output_text)


class MatchingReadback:
    def verify(self, execution):
        return ProviderReadbackEvidence(
            provider="openai",
            provider_readback_ref="provider-readback:resp_build_001",
            response_id=execution.response_id,
            response_model=execution.response_model,
            status=execution.status,
            model_version="provider-model-version-2026-08-31",
            model_version_verified=True,
            configuration_sha256=execution.configuration_sha256,
            configuration_verified=True,
        )


def plan():
    return compile_idea_to_system(
        "Build a tiny Python API and test it.",
        source_frontier="main@test",
    )


def candidate_json() -> str:
    return json.dumps(
        {
            "candidate_id": "candidate-1",
            "files": {
                "app.py": "print('ok')\n",
                "result.txt": "candidate\n",
            },
            "validation_command": ["python", "app.py"],
            "export_paths": ["result.txt"],
            "rationale": "smallest testable candidate",
        }
    )


def authorized_generator(client, **kwargs):
    return OpenAIResponsesBuildGenerator(
        client=client,
        model="gpt-build",
        provider_execution_authorized=True,
        provider_payload_authorized=True,
        **kwargs,
    )


class OpenAIResponsesBuildGeneratorTests(unittest.TestCase):
    def test_provider_call_is_blocked_without_explicit_execution_authorization(self) -> None:
        client = FakeClient(candidate_json())
        generator = OpenAIResponsesBuildGenerator(client=client, model="gpt-build")
        with self.assertRaisesRegex(PermissionError, "explicit provider execution authorization"):
            generator.propose(plan(), {}, None)
        self.assertEqual([], client.responses.calls)
        self.assertIsNone(generator.provider_receipt())

    def test_provider_call_is_blocked_without_separate_payload_authorization(self) -> None:
        client = FakeClient(candidate_json())
        generator = OpenAIResponsesBuildGenerator(
            client=client,
            model="gpt-build",
            provider_execution_authorized=True,
            provider_payload_authorized=False,
        )
        with self.assertRaisesRegex(PermissionError, "explicit provider payload authorization"):
            generator.propose(plan(), {"private.py": "PRIVATE-WORKSPACE"}, None)
        self.assertEqual([], client.responses.calls)
        self.assertIsNone(generator.provider_receipt())

    def test_authorized_provider_execution_returns_bounded_candidate_without_self_readback(self) -> None:
        client = FakeClient(candidate_json())
        generator = authorized_generator(client, request_options={"max_output_tokens": 500})
        candidate = generator.propose(plan(), {}, None)
        self.assertEqual("candidate-1", candidate.candidate_id)
        self.assertEqual(("python", "app.py"), candidate.validation_command)
        self.assertEqual({"app.py", "result.txt"}, set(candidate.normalized_files()))
        receipt = dict(generator.provider_receipt() or {})
        self.assertEqual("PROVIDER_EXECUTED_UNREADBACK", receipt["provider_state"])
        self.assertFalse(receipt["provider_storage"])
        self.assertFalse(receipt["external_mutation"])
        self.assertEqual("", receipt["provider_readback_ref"])
        self.assertTrue(receipt["provider_execution_authorized"])
        self.assertTrue(receipt["provider_payload_authorized"])
        self.assertFalse(receipt["truth_boundary"]["provider_call_authority_is_payload_share_authority"])
        call = client.responses.calls[0]
        self.assertFalse(call["store"])
        self.assertNotIn("tools", call)

    def test_independent_readback_promotes_only_provider_generation_proof(self) -> None:
        client = FakeClient(candidate_json())
        generator = authorized_generator(
            client,
            readback_verifier=MatchingReadback(),
            require_provider_readback=True,
        )
        generator.propose(plan(), {}, None)
        receipt = dict(generator.provider_receipt() or {})
        self.assertEqual("PROVIDER_VERIFIED", receipt["provider_state"])
        self.assertEqual("provider-readback:resp_build_001", receipt["provider_readback_ref"])
        self.assertEqual("provider-model-version-2026-08-31", receipt["verified_model_version"])
        self.assertFalse(receipt["truth_boundary"]["generated_candidate_is_deployed"])
        self.assertFalse(receipt["truth_boundary"]["provider_execution_grants_mutation_authority"])

    def test_required_readback_without_verifier_fails_before_provider_call(self) -> None:
        client = FakeClient(candidate_json())
        with self.assertRaisesRegex(ValueError, "independent readback verifier"):
            OpenAIResponsesBuildGenerator(
                client=client,
                model="gpt-build",
                provider_execution_authorized=True,
                provider_payload_authorized=True,
                require_provider_readback=True,
            )
        self.assertEqual([], client.responses.calls)

    def test_failure_feedback_is_minimized_before_provider_prompt(self) -> None:
        client = FakeClient(candidate_json())
        generator = authorized_generator(client)
        generator.propose(
            plan(),
            {},
            {
                "status": "NONZERO_EXIT",
                "returncode": 1,
                "result_hash": "RESULT-HASH",
                "stdout": "PRIVATE-RAW-OUTPUT-MUST-NOT-LEAVE",
                "stderr": "PRIVATE-RAW-ERROR-MUST-NOT-LEAVE",
            },
        )
        serialized = json.dumps(client.responses.calls[0], sort_keys=True)
        self.assertIn("RESULT-HASH", serialized)
        self.assertNotIn("PRIVATE-RAW-OUTPUT-MUST-NOT-LEAVE", serialized)
        self.assertNotIn("PRIVATE-RAW-ERROR-MUST-NOT-LEAVE", serialized)

    def test_model_output_must_be_strict_candidate_json(self) -> None:
        client = FakeClient("not json")
        generator = authorized_generator(client)
        with self.assertRaisesRegex(ValueError, "non-JSON"):
            generator.propose(plan(), {}, None)
        self.assertIsNone(generator.provider_receipt())

    def test_tools_and_hidden_context_options_remain_forbidden(self) -> None:
        client = FakeClient(candidate_json())
        with self.assertRaises(OpenAIProviderAdapterError):
            authorized_generator(
                client,
                request_options={"tools": [{"type": "web_search"}]},
            )


if __name__ == "__main__":
    unittest.main()
