from __future__ import annotations

import os
import tempfile
import unittest

from .empirical_playbook import (
    ChatLearningEvent,
    EmpiricalPlaybookEngine,
    EmpiricalPlaybookStore,
    EvidenceTier,
    LearningShareScope,
    LearningState,
)


class EmpiricalPlaybookScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = EmpiricalPlaybookEngine(
            EmpiricalPlaybookStore(os.path.join(self.tmp.name, "scope.sqlite3"))
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def event(
        event_id: str,
        conversation_key: str,
        *,
        independent: bool = True,
        tier: EvidenceTier = EvidenceTier.PROVIDER_READBACK,
        reproduced: bool = False,
    ) -> ChatLearningEvent:
        return ChatLearningEvent(
            event_id=event_id,
            observed_at="2026-08-16T20:30:00+02:00",
            conversation_key=conversation_key,
            namespace_key="chatgpt-experience",
            category="CONTINUITY",
            problem_signature="SCOPE_PROMOTION_GATE",
            observation="A bounded operational signal was observed.",
            outcome="A candidate rule was proposed.",
            evidence_tier=tier,
            evidence_refs=(f"evidence:{event_id}",),
            verified=True,
            reproduced=reproduced,
            independent_observation=independent,
            reusable=True,
            share_scope=LearningShareScope.FEDERATION_OPERATIONAL,
        )

    def test_bounded_rule_never_receives_global_scope(self) -> None:
        self.engine.record(self.event("scope-one", "scope-chat-one"))
        rule = self.engine.promote_rule(
            problem_signature="SCOPE_PROMOTION_GATE",
            rule_id="CBP-SCOPE-ONE",
            title="Bounded scope test",
            instruction="Remain bounded until promotion evidence exists.",
        )["rule"]
        self.assertEqual(rule["learning_state"], LearningState.VERIFIED_BOUNDED.value)
        self.assertTrue(rule["scope"].startswith("NAMESPACE:"))
        self.assertNotEqual(rule["scope"], "ALL_CHATBRIDGE_ACTIVE_CHATS")

    def test_nonindependent_event_cannot_satisfy_promotion_threshold(self) -> None:
        self.engine.record(self.event("scope-independent", "scope-chat-a"))
        self.engine.record(
            self.event(
                "scope-dependent",
                "scope-chat-b",
                independent=False,
                tier=EvidenceTier.REPRODUCED_CANARY,
                reproduced=True,
            )
        )
        rule = self.engine.promote_rule(
            problem_signature="SCOPE_PROMOTION_GATE",
            rule_id="CBP-SCOPE-INDEPENDENCE",
            title="Independent evidence gate",
            instruction="Require independent observations before global promotion.",
        )["rule"]
        self.assertEqual(rule["qualified_support_count"], 1)
        self.assertEqual(rule["learning_state"], LearningState.VERIFIED_BOUNDED.value)
        self.assertNotEqual(rule["scope"], "ALL_CHATBRIDGE_ACTIVE_CHATS")


if __name__ == "__main__":
    unittest.main()
