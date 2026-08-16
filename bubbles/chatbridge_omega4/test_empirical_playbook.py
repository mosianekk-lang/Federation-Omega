from __future__ import annotations

import os
import tempfile
import unittest

from .empirical_playbook import (
    ChatLearningEvent,
    EmpiricalPlaybookEngine,
    EmpiricalPlaybookStore,
    EvidenceTier,
    LearningSeverity,
    LearningShareScope,
    LearningState,
)


class EmpiricalPlaybookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = EmpiricalPlaybookStore(
            os.path.join(self.tmp.name, "chatbridge.sqlite3")
        )
        self.engine = EmpiricalPlaybookEngine(self.store)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def event(self, event_id: str, conversation_key: str, **overrides) -> ChatLearningEvent:
        data = {
            "event_id": event_id,
            "observed_at": "2026-08-16T20:00:00+02:00",
            "conversation_key": conversation_key,
            "namespace_key": "chatgpt-experience",
            "category": "CONTINUITY",
            "problem_signature": "CHAT_MAX_LENGTH_TERMINAL_AFTER_ACTIVE_WORK",
            "observation": "The active chat reached the product maximum-length warning.",
            "outcome": "The same chat could no longer create a reliable handoff.",
            "evidence_tier": EvidenceTier.PROVIDER_READBACK,
            "evidence_refs": (f"evidence:{event_id}",),
            "verified": True,
            "reproduced": False,
            "independent_observation": True,
            "severity": LearningSeverity.CRITICAL,
            "repair": "Checkpoint material deltas before terminal exhaustion.",
            "reusable": True,
            "share_scope": LearningShareScope.FEDERATION_OPERATIONAL,
            "matter_key": "",
            "supports_candidate_rule": True,
        }
        data.update(overrides)
        return ChatLearningEvent(**data)

    def test_privacy_sensitive_event_is_redacted_and_not_promoted(self) -> None:
        receipt = self.engine.record(
            self.event(
                "evt-private",
                "chat-private",
                observation="raw medical detail",
                outcome="raw medical outcome",
                contains_raw_sensitive_content=True,
                matter_key="medical-accommodation",
                share_scope=LearningShareScope.NAMESPACE_ONLY,
            )
        )
        self.assertEqual(receipt["learning_state"], LearningState.REJECTED_PRIVACY.value)
        self.assertEqual(
            receipt["stored_payload"]["observation"],
            "[REDACTED_BY_PLAYBOOK_PRIVACY_POLICY]",
        )
        self.assertEqual(
            receipt["stored_payload"]["outcome"],
            "[REDACTED_BY_PLAYBOOK_PRIVACY_POLICY]",
        )

    def test_secret_event_removes_evidence_references(self) -> None:
        receipt = self.engine.record(
            self.event(
                "evt-secret",
                "chat-secret",
                contains_secret=True,
            )
        )
        self.assertEqual(receipt["learning_state"], LearningState.REJECTED_PRIVACY.value)
        self.assertEqual(receipt["stored_payload"]["evidence_refs"], [])

    def test_verified_provider_event_becomes_bounded_not_global(self) -> None:
        receipt = self.engine.record(self.event("evt-one", "chat-one"))
        self.assertEqual(receipt["learning_state"], LearningState.VERIFIED_BOUNDED.value)
        promoted = self.engine.promote_rule(
            problem_signature="CHAT_MAX_LENGTH_TERMINAL_AFTER_ACTIVE_WORK",
            rule_id="CBP-001",
            title="Checkpoint before terminal exhaustion",
            instruction="Checkpoint material deltas and migrate before terminal exhaustion.",
        )
        self.assertEqual(
            promoted["rule"]["learning_state"],
            LearningState.VERIFIED_BOUNDED.value,
        )
        self.assertEqual(promoted["rule"]["qualified_support_count"], 1)

    def test_documentation_only_observation_cannot_promote_rule(self) -> None:
        documentation_event = ChatLearningEvent(
            event_id="evt-docs",
            observed_at="2026-08-16T20:01:00+02:00",
            conversation_key="chat-docs",
            namespace_key="chatgpt-experience",
            category="REFERENCE",
            problem_signature="DOCS_ONLY_THEORY",
            observation="An official help page recommends starting a new chat.",
            outcome="No independent product behaviour was observed in this event.",
            evidence_tier=EvidenceTier.OFFICIAL_DOCUMENTATION,
            evidence_refs=("official-doc:chat-help",),
            verified=True,
            reusable=True,
            share_scope=LearningShareScope.FEDERATION_OPERATIONAL,
        )
        recorded = self.engine.record(documentation_event)
        self.assertEqual(
            recorded["learning_state"],
            LearningState.OBSERVED_NOT_PROMOTED.value,
        )
        rule = self.engine.promote_rule(
            problem_signature="DOCS_ONLY_THEORY",
            rule_id="CBP-DOCS-HOLD",
            title="Documentation-only theory",
            instruction="Do not promote without empirical support.",
        )["rule"]
        self.assertEqual(
            rule["learning_state"],
            LearningState.HOLD_INSUFFICIENT_EMPIRICAL_PROOF.value,
        )
        self.assertTrue(rule["documentation_only"])

    def test_two_independent_empirical_events_promote_global_rule(self) -> None:
        self.engine.record(self.event("evt-two-a", "chat-a"))
        self.engine.record(
            self.event(
                "evt-two-b",
                "chat-b",
                evidence_tier=EvidenceTier.REPRODUCED_CANARY,
                reproduced=True,
            )
        )
        result = self.engine.promote_rule(
            problem_signature="CHAT_MAX_LENGTH_TERMINAL_AFTER_ACTIVE_WORK",
            rule_id="CBP-001",
            title="Never wait for terminal quota",
            instruction=(
                "Checkpoint each material delta and before heavy work; migrate at red risk; "
                "at terminal restore only from the last verified checkpoint."
            ),
        )
        rule = result["rule"]
        self.assertEqual(rule["learning_state"], LearningState.PROMOTED.value)
        self.assertEqual(rule["scope"], "ALL_CHATBRIDGE_ACTIVE_CHATS")
        self.assertEqual(rule["distinct_conversation_count"], 2)
        self.assertTrue(rule["provider_or_canary_support"])
        self.assertGreaterEqual(rule["confidence"], 0.7)

    def test_matter_bound_events_cannot_become_global_rule(self) -> None:
        self.engine.record(
            self.event(
                "evt-matter-a",
                "chat-matter-a",
                matter_key="medical-accommodation",
                share_scope=LearningShareScope.NAMESPACE_ONLY,
            )
        )
        self.engine.record(
            self.event(
                "evt-matter-b",
                "chat-matter-b",
                matter_key="medical-accommodation",
                share_scope=LearningShareScope.NAMESPACE_ONLY,
                evidence_tier=EvidenceTier.REPRODUCED_CANARY,
                reproduced=True,
            )
        )
        rule = self.engine.promote_rule(
            problem_signature="CHAT_MAX_LENGTH_TERMINAL_AFTER_ACTIVE_WORK",
            rule_id="CBP-MATTER",
            title="Matter-bound rule",
            instruction="Keep this rule within its governed namespace.",
        )["rule"]
        self.assertTrue(rule["scope"].startswith("NAMESPACE:"))
        self.assertNotEqual(rule["scope"], "ALL_CHATBRIDGE_ACTIVE_CHATS")

    def test_verified_contradiction_holds_rule(self) -> None:
        self.engine.record(self.event("evt-support", "chat-support"))
        self.engine.record(
            self.event(
                "evt-contradiction",
                "chat-contradiction",
                supports_candidate_rule=False,
                contradicts_candidate_rule=True,
                observation="A later provider readback contradicted the proposed global rule.",
                outcome="The rule requires revalidation.",
                evidence_tier=EvidenceTier.REPRODUCED_CANARY,
                reproduced=True,
            )
        )
        rule = self.engine.promote_rule(
            problem_signature="CHAT_MAX_LENGTH_TERMINAL_AFTER_ACTIVE_WORK",
            rule_id="CBP-CONTRADICTION",
            title="Contradicted rule",
            instruction="Hold until the contradiction is resolved.",
        )["rule"]
        self.assertEqual(
            rule["learning_state"],
            LearningState.HOLD_CONTRADICTION.value,
        )
        self.assertEqual(rule["qualified_contradiction_count"], 1)
        self.assertLessEqual(rule["confidence"], 0.35)

    def test_learning_event_is_idempotent_but_conflicting_reuse_fails(self) -> None:
        event = self.event("evt-idempotent", "chat-idempotent")
        first = self.engine.record(event)
        second = self.engine.record(event)
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        with self.assertRaises(ValueError):
            self.engine.record(
                self.event(
                    "evt-idempotent",
                    "chat-idempotent",
                    outcome="different content under the same event ID",
                )
            )


if __name__ == "__main__":
    unittest.main()
