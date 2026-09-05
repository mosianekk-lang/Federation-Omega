from __future__ import annotations

import unittest

from bubbles.chat_governor_omega3.performance_kernel import HookContext, HookEvent, LifecycleHookBus
from federation.chatgov_progress_binding_v1 import ChatGovProgressBinding
from federation.execution_progress_governor_v1 import ExecutionProgressGovernor


STATE = {
    "verified_closure": 0.2,
    "information": 0.2,
    "safety": 0.9,
    "recoverability": 0.5,
    "unlock_leverage": 0.2,
}


class ChatGovProgressBindingV1Tests(unittest.TestCase):
    def test_binding_registers_into_existing_hook_bus_without_authority_claim(self) -> None:
        bus = LifecycleHookBus()
        receipt = ChatGovProgressBinding().register(bus)
        self.assertEqual(receipt.registered_hooks, ("cfbe_progress_preflight_v1", "cfbe_progress_post_tool_v1"))
        self.assertFalse(receipt.native_chatgpt_binding_claimed)
        self.assertFalse(receipt.provider_effect_authorized)

    def test_material_pretool_requires_state_version(self) -> None:
        bus = LifecycleHookBus()
        ChatGovProgressBinding().register(bus)
        out = bus.emit(HookContext(HookEvent.PRE_TOOL, "M", effect_class="READ_ONLY", material=True, tool_name="GitHub.fetch"))
        self.assertEqual(out.decision, "DENY")
        self.assertIn("STATE_VERSION_REQUIRED", out.reason)

    def test_same_state_zero_progress_forces_route_mutation_through_hooks(self) -> None:
        bus = LifecycleHookBus()
        binding = ChatGovProgressBinding(governor=ExecutionProgressGovernor(same_state_retry_budget=2))
        binding.register(bus)
        pre = HookContext(
            HookEvent.PRE_TOOL,
            "M",
            effect_class="READ_ONLY",
            material=True,
            tool_name="files.find",
            tool_args={"q": "same"},
            metadata={"state_version": "s1"},
        )
        self.assertEqual(bus.emit(pre).decision, "ALLOW")
        post = HookContext(
            HookEvent.POST_TOOL,
            "M",
            effect_class="READ_ONLY",
            material=True,
            tool_name="files.find",
            tool_args={"q": "same"},
            metadata={
                "state_version": "s1",
                "before_state": STATE,
                "after_state": STATE,
                "result_summary": "no new evidence",
            },
        )
        self.assertEqual(bus.emit(post).decision, "ALLOW")
        self.assertEqual(bus.emit(pre).decision, "ALLOW")
        second_post = bus.emit(post)
        self.assertEqual(second_post.decision, "BLOCK_CONTINUE")
        third_pre = bus.emit(pre)
        self.assertEqual(third_pre.decision, "DENY")
        self.assertIn("CIRCUIT_OPEN", third_pre.reason)

    def test_changed_state_version_reopens_same_tool_route(self) -> None:
        bus = LifecycleHookBus()
        binding = ChatGovProgressBinding(governor=ExecutionProgressGovernor(same_state_retry_budget=1))
        binding.register(bus)
        common = dict(effect_class="READ_ONLY", material=True, tool_name="fetch", tool_args={"id": 1})
        pre_old = HookContext(HookEvent.PRE_TOOL, "M", metadata={"state_version": "old"}, **common)
        post_old = HookContext(
            HookEvent.POST_TOOL,
            "M",
            metadata={"state_version": "old", "before_state": STATE, "after_state": STATE, "result_summary": "timeout"},
            **common,
        )
        self.assertEqual(bus.emit(pre_old).decision, "ALLOW")
        self.assertEqual(bus.emit(post_old).decision, "BLOCK_CONTINUE")
        self.assertEqual(bus.emit(pre_old).decision, "DENY")
        pre_new = HookContext(HookEvent.PRE_TOOL, "M", metadata={"state_version": "new"}, **common)
        self.assertEqual(bus.emit(pre_new).decision, "ALLOW")

    def test_status_updates_suppress_zero_delta_narration(self) -> None:
        binding = ChatGovProgressBinding()
        self.assertTrue(binding.status_update(state_digest="d1", update_text="started").allow)
        self.assertFalse(binding.status_update(state_digest="d1", update_text="still working").allow)
        self.assertTrue(binding.status_update(state_digest="d2", update_text="new evidence").allow)


if __name__ == "__main__":
    unittest.main()
