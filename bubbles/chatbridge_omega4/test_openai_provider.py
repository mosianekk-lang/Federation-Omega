from __future__ import annotations

import json
import os
import tempfile
import unittest

from .models import ApprovalState, ContinuationMode, GovernanceCapsule, ProviderContinuationRef
from .openai_provider import OpenAIConversationProvider, OpenAIProviderBindingError
from .provider_state import ProviderRunStateConflict, ProviderStateStore
from .runtime import ChatBridgeOmega4
from .store import ChatBridgeStore


class _FakeAgent:
    def __init__(self, name, instructions, model, tools=None):
        self.name = name
        self.instructions = instructions
        self.model = model
        self.tools = list(tools or [])


class _FakeInterruption:
    def __init__(self, name="governed_action", arguments='{"value":7}', agent=None):
        self.name = name
        self.arguments = arguments
        self.agent = agent


class _FakeState:
    def __init__(self, interruptions=None, approved=None):
        self._interruptions = list(interruptions or [])
        self.approved = list(approved or [])

    def to_string(self):
        return json.dumps(
            {
                "interruptions": [
                    {"name": item.name, "arguments": item.arguments}
                    for item in self._interruptions
                ],
                "approved": self.approved,
            },
            sort_keys=True,
        )

    @classmethod
    async def from_string(cls, agent, raw):
        data = json.loads(raw)
        items = [
            _FakeInterruption(item["name"], item["arguments"], agent)
            for item in data.get("interruptions", [])
        ]
        return cls(items, data.get("approved", []))

    def get_interruptions(self):
        return list(self._interruptions)

    def approve(self, interruption, always_approve=False):
        self.approved.append(True)

    def reject(self, interruption):
        self.approved.append(False)


class _FakeResult:
    def __init__(self, *, final_output="", interruptions=None, response_id="resp_fake"):
        self.final_output = final_output
        self.interruptions = list(interruptions or [])
        self.last_response_id = response_id

    def to_state(self):
        return _FakeState(self.interruptions)


class _FakeSession:
    conversations = {}
    next_id = 1

    def __init__(self, conversation_id=None):
        self._session_id = conversation_id
        if conversation_id and conversation_id not in self.conversations:
            self.conversations[conversation_id] = []

    @property
    def session_id(self):
        if not self._session_id:
            raise ValueError("session is not initialized")
        return self._session_id

    def ensure(self):
        if not self._session_id:
            self._session_id = f"conv_fake_{self.next_id}"
            type(self).next_id += 1
            self.conversations[self._session_id] = []
        return self._session_id

    async def get_items(self, limit=100):
        cid = self.ensure()
        return list(self.conversations[cid][-limit:])


class _FakeRunner:
    response_no = 1

    @classmethod
    async def run(cls, agent, input_value, session):
        cid = session.ensure()
        items = session.conversations[cid]
        response_id = f"resp_fake_{cls.response_no}"
        cls.response_no += 1
        if isinstance(input_value, _FakeState):
            items.append({"role": "tool", "approved": list(input_value.approved)})
            items.append({"role": "assistant", "content": "approval-resume-complete"})
            return _FakeResult(final_output="approval-resume-complete", response_id=response_id)
        items.append({"role": "user", "content": input_value})
        if "NEED_APPROVAL" in input_value:
            interruption = _FakeInterruption(agent=agent)
            items.append({"role": "assistant", "content": "waiting-approval"})
            return _FakeResult(interruptions=[interruption], response_id=response_id)
        if "REMEMBER=" in input_value:
            token = input_value.split("REMEMBER=", 1)[1]
            items.append({"role": "assistant", "content": f"remembered:{token}"})
            return _FakeResult(final_output=f"remembered:{token}", response_id=response_id)
        remembered = ""
        for item in items:
            content = item.get("content", "")
            if isinstance(content, str) and content.startswith("REMEMBER="):
                remembered = content.split("REMEMBER=", 1)[1]
        answer = f"memory:{remembered}"
        items.append({"role": "assistant", "content": answer})
        return _FakeResult(final_output=answer, response_id=response_id)


class _FakeProvider(OpenAIConversationProvider):
    def _sdk(self):
        return {
            "Agent": _FakeAgent,
            "OpenAIConversationsSession": _FakeSession,
            "RunState": _FakeState,
            "Runner": _FakeRunner,
        }


class ChatBridgeOmega4OpenAIProviderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "chatbridge.sqlite3")
        self.bridge = ChatBridgeOmega4(ChatBridgeStore(self.db))
        self.provider_state = ProviderStateStore(self.db)
        self.capsule = GovernanceCapsule(
            owner="Kim Kagiso Mosiane",
            project="ChatBridge Ω4",
            workstream="provider-canary",
            adapter="chatbridge-openai-conversations",
            objective="Prove durable provider continuation without weakening governance.",
            exact_next_action="Complete provider canary readback.",
            approval_gates=(ApprovalState.SCREEN_FIRST,),
            external_effects_allowed=False,
        )
        self.bridge.backup(
            "omega4-canary",
            self.capsule,
            hot_state={"phase": "SOURCE_VERIFIED"},
        )
        self.provider = _FakeProvider(self.bridge, self.provider_state, model="fake-model")

    def tearDown(self):
        self.tmp.cleanup()

    async def test_first_turn_binds_real_provider_identity_shape_as_new_generation(self):
        first = await self.provider.run_turn(
            "omega4-canary",
            "REMEMBER=blue-orchid",
            destination_session_key="process-a",
        )
        self.assertTrue(first["conversation_id"].startswith("conv_fake_"))
        self.assertEqual(first["state"], "TURN_COMPLETE_READBACK_VERIFIED")
        status = self.bridge.status("omega4-canary")
        self.assertEqual(status["active_generation_number"], 2)
        restored = self.bridge.store.restore(
            "omega4-canary", destination_session_key="inspect"
        )
        self.assertEqual(restored.provider_ref.mode, ContinuationMode.OPENAI_CONVERSATION)
        self.assertEqual(restored.provider_ref.conversation_id, first["conversation_id"])

    async def test_new_provider_instance_continues_same_conversation_without_manual_replay(self):
        first = await self.provider.run_turn(
            "omega4-canary",
            "REMEMBER=blue-orchid",
            destination_session_key="process-a",
        )
        new_process_provider = _FakeProvider(
            ChatBridgeOmega4(ChatBridgeStore(self.db)),
            ProviderStateStore(self.db),
            model="fake-model",
        )
        second = await new_process_provider.run_turn(
            "omega4-canary",
            "WHAT_DID_I_ASK_YOU_TO_REMEMBER",
            destination_session_key="process-b",
        )
        self.assertEqual(second["conversation_id"], first["conversation_id"])
        self.assertEqual(second["final_output"], "memory:blue-orchid")

    async def test_hitl_runstate_is_persisted_fenced_and_resumed_once(self):
        await self.provider.run_turn(
            "omega4-canary",
            "REMEMBER=blue-orchid",
            destination_session_key="process-a",
        )
        paused = await self.provider.run_turn(
            "omega4-canary",
            "NEED_APPROVAL",
            destination_session_key="process-b",
        )
        self.assertEqual(paused["state"], "INTERRUPTED_WAITING_APPROVAL")
        self.assertTrue(paused["run_state_id"])

        resumed = await self.provider.resume_approval(
            "omega4-canary",
            paused["run_state_id"],
            [True],
            destination_session_key="process-c",
        )
        self.assertEqual(
            resumed["state"], "APPROVAL_RESUME_COMPLETE_READBACK_VERIFIED"
        )
        state_row = self.provider_state.get_run_state(paused["run_state_id"])
        self.assertEqual(state_row["status"], "RESUMED")

        with self.assertRaises(ProviderRunStateConflict):
            await self.provider.resume_approval(
                "omega4-canary",
                paused["run_state_id"],
                [True],
                destination_session_key="process-d",
            )

    async def test_provider_strategy_mismatch_fails_closed(self):
        other = ProviderContinuationRef(
            mode=ContinuationMode.OPENAI_PREVIOUS_RESPONSE,
            provider="openai",
            previous_response_id="resp_other",
        )
        self.bridge.refresh(
            "omega4-canary",
            self.capsule,
            hot_state={"phase": "OTHER_STRATEGY"},
            provider_ref=other,
        )
        with self.assertRaises(OpenAIProviderBindingError):
            await self.provider.run_turn(
                "omega4-canary",
                "hello",
                destination_session_key="process-x",
            )


if __name__ == "__main__":
    unittest.main()
