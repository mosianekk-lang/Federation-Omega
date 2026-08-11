from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from evidenceops.caseforge.openai_provider_adapter import (
    OpenAIProviderAdapterError,
    OpenAIProviderBlindExperiment,
    OpenAIResponsesTestedAgent,
    ProviderReadbackEvidence,
)


BLIND = {
    "case_id": "CF-TEST-OPENAI-001",
    "research_question": "What can be concluded from the supplied record?",
    "observations": [
        {"id": "O1", "state": "USER_SUPPLIED", "text": "A shared service is interrupted."}
    ],
}


class FakeResponses:
    def __init__(self, *, output_text: str | None = None, error: Exception | None = None):
        self.output_text = output_text or json.dumps({"hypotheses": ["H1", "H2"]})
        self.error = error
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(dict(kwargs))
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            id="resp_caseforge_001",
            model="gpt-provider-returned-model",
            status="completed",
            created_at=1786490000,
            output_text=self.output_text,
            _request_id="req_caseforge_001",
        )


class FakeClient:
    def __init__(self, responses: FakeResponses | None = None):
        self.responses = responses or FakeResponses()


class MatchingReadback:
    def verify(self, execution):
        return ProviderReadbackEvidence(
            provider="openai",
            provider_readback_ref="provider-readback:resp_caseforge_001",
            response_id=execution.response_id,
            response_model=execution.response_model,
            status=execution.status,
            model_version="gpt-provider-version-2026-08-12",
            model_version_verified=True,
        )


class MismatchedReadback:
    def verify(self, execution):
        return ProviderReadbackEvidence(
            provider="openai",
            provider_readback_ref="provider-readback:wrong",
            response_id="resp_wrong",
            response_model=execution.response_model,
            status=execution.status,
            model_version="gpt-provider-version-2026-08-12",
            model_version_verified=True,
        )


class UnversionedReadback:
    def verify(self, execution):
        return ProviderReadbackEvidence(
            provider="openai",
            provider_readback_ref="provider-readback:unversioned",
            response_id=execution.response_id,
            response_model=execution.response_model,
            status=execution.status,
            model_version="",
            model_version_verified=False,
        )


class CaseForgeOpenAIProviderAdapterTests(unittest.TestCase):
    def test_adapter_prohibits_tools_and_hidden_context_routes(self) -> None:
        with self.assertRaisesRegex(OpenAIProviderAdapterError, "weaken blind isolation"):
            OpenAIResponsesTestedAgent(
                client=FakeClient(),
                model="gpt-test",
                request_options={"tools": [{"type": "web_search"}]},
            )
        with self.assertRaisesRegex(OpenAIProviderAdapterError, "weaken blind isolation"):
            OpenAIResponsesTestedAgent(
                client=FakeClient(),
                model="gpt-test",
                request_options={"previous_response_id": "resp_hidden"},
            )

    def test_adapter_rejects_unadmitted_provider_options(self) -> None:
        with self.assertRaisesRegex(OpenAIProviderAdapterError, "not admitted"):
            OpenAIResponsesTestedAgent(
                client=FakeClient(),
                model="gpt-test",
                request_options={"unknown_future_option": True},
            )

    def test_provider_execution_receipt_does_not_self_certify_readback(self) -> None:
        client = FakeClient()
        receipt = OpenAIProviderBlindExperiment().run(
            run_id="RUN-OPENAI-001",
            blind_payload=BLIND,
            client=client,
            model="gpt-test",
            request_options={"max_output_tokens": 200},
        )
        self.assertEqual("PROVIDER_EXECUTED_UNREADBACK", receipt.provider_state)
        self.assertEqual("", receipt.provider_readback_ref)
        self.assertEqual("", receipt.verified_model_version)
        self.assertEqual("DETERMINISTIC_TEST_ONLY", receipt.blind_run.execution_state)
        self.assertEqual(
            "REQUESTED_MODEL_ID_UNVERIFIED_VERSION",
            receipt.blind_run.version,
        )
        self.assertEqual("resp_caseforge_001", receipt.provider_execution.response_id)
        self.assertEqual("gpt-provider-returned-model", receipt.provider_execution.response_model)
        self.assertFalse(receipt.provider_execution.store)

        call = client.responses.calls[0]
        self.assertEqual("gpt-test", call["model"])
        self.assertFalse(call["store"])
        self.assertNotIn("tools", call)
        supplied = json.loads(call["input"][0]["content"])
        self.assertEqual(BLIND, supplied)
        serialized = json.dumps(call, sort_keys=True)
        self.assertNotIn("answer_key", serialized)
        self.assertNotIn("control_pack", serialized)

    def test_matching_independent_readback_promotes_only_execution_proof(self) -> None:
        receipt = OpenAIProviderBlindExperiment().run(
            run_id="RUN-OPENAI-002",
            blind_payload=BLIND,
            client=FakeClient(),
            model="gpt-test",
            readback_verifier=MatchingReadback(),
        )
        self.assertEqual("PROVIDER_VERIFIED", receipt.provider_state)
        self.assertEqual(
            "provider-readback:resp_caseforge_001",
            receipt.provider_readback_ref,
        )
        self.assertEqual(
            "gpt-provider-version-2026-08-12",
            receipt.verified_model_version,
        )
        self.assertEqual("PROVIDER_VERIFIED", receipt.blind_run.execution_state)
        self.assertEqual("gpt-test", receipt.blind_run.model)
        self.assertEqual(
            "gpt-provider-version-2026-08-12",
            receipt.blind_run.version,
        )

    def test_mismatched_provider_readback_fails_closed(self) -> None:
        with self.assertRaisesRegex(OpenAIProviderAdapterError, "response id mismatch"):
            OpenAIProviderBlindExperiment().run(
                run_id="RUN-OPENAI-003",
                blind_payload=BLIND,
                client=FakeClient(),
                model="gpt-test",
                readback_verifier=MismatchedReadback(),
            )

    def test_unverified_model_version_cannot_promote_provider_state(self) -> None:
        with self.assertRaisesRegex(OpenAIProviderAdapterError, "model version"):
            OpenAIProviderBlindExperiment().run(
                run_id="RUN-OPENAI-003B",
                blind_payload=BLIND,
                client=FakeClient(),
                model="gpt-test",
                readback_verifier=UnversionedReadback(),
            )

    def test_provider_exception_does_not_echo_sensitive_error_text(self) -> None:
        sensitive_marker = "PRIVATE-CREDENTIAL-VALUE-MUST-NOT-ESCAPE"
        client = FakeClient(FakeResponses(error=RuntimeError(sensitive_marker)))
        with self.assertRaises(OpenAIProviderAdapterError) as caught:
            OpenAIProviderBlindExperiment().run(
                run_id="RUN-OPENAI-004",
                blind_payload=BLIND,
                client=client,
                model="gpt-test",
            )
        self.assertNotIn(sensitive_marker, str(caught.exception))
        self.assertIn("RuntimeError", str(caught.exception))

    def test_non_json_model_output_is_preserved_as_unparsed_analysis(self) -> None:
        client = FakeClient(FakeResponses(output_text="Plain model analysis"))
        receipt = OpenAIProviderBlindExperiment().run(
            run_id="RUN-OPENAI-005",
            blind_payload=BLIND,
            client=client,
            model="gpt-test",
        )
        self.assertEqual(
            {
                "response_format": "NON_JSON_OUTPUT",
                "analysis_text": "Plain model analysis",
            },
            receipt.blind_run.tested_output,
        )


if __name__ == "__main__":
    unittest.main()
