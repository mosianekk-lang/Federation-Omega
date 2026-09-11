import unittest

from fuse_astra_protocol_awareness.pragmatics import (
    CommitmentLedger,
    CommitmentState,
    ParticipantRole,
    PragmaticFirewall,
    PragmaticPolicy,
    SemanticMessage,
    SpeechAct,
)


class PragmaticCommunicationTests(unittest.TestCase):
    def setUp(self):
        self.firewall = PragmaticFirewall()
        self.policy = PragmaticPolicy(owner_ids=("kim",), delegated_commanders=("ops-controller",))

    def msg(self, sender_id, role, act):
        return SemanticMessage(
            message_id=f"m-{sender_id}-{act.value}",
            mission_id="mission-1",
            sender_id=sender_id,
            sender_role=role,
            speech_act=act,
            topic="test",
        )

    def test_owner_command_is_preserved(self):
        decision = self.firewall.evaluate(self.msg("kim", ParticipantRole.OWNER, SpeechAct.COMMAND), self.policy)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.normalized_act, SpeechAct.COMMAND)

    def test_delegated_commander_can_command(self):
        decision = self.firewall.evaluate(
            self.msg("ops-controller", ParticipantRole.AGENT, SpeechAct.COMMAND), self.policy
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.normalized_act, SpeechAct.COMMAND)

    def test_remote_agent_cannot_self_elevate_to_command(self):
        decision = self.firewall.evaluate(self.msg("agent-x", ParticipantRole.AGENT, SpeechAct.COMMAND), self.policy)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.normalized_act, SpeechAct.REQUEST)

    def test_tool_imperative_is_normalized_to_information(self):
        decision = self.firewall.evaluate(self.msg("tool-1", ParticipantRole.TOOL, SpeechAct.COMMAND), self.policy)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.normalized_act, SpeechAct.INFORM)

    def test_agent_self_approval_is_not_valid(self):
        decision = self.firewall.evaluate(self.msg("agent-x", ParticipantRole.AGENT, SpeechAct.APPROVE), self.policy)
        self.assertFalse(decision.allowed)
        self.assertNotEqual(decision.normalized_act, SpeechAct.APPROVE)

    def test_evidence_message_does_not_imply_execution_authority(self):
        decision = self.firewall.evaluate(self.msg("researcher", ParticipantRole.AGENT, SpeechAct.EVIDENCE), self.policy)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.normalized_act, SpeechAct.EVIDENCE)

    def test_commitment_state_machine_requires_approval_before_completion(self):
        ledger = CommitmentLedger()
        ledger.create("c1")
        ledger.transition("c1", CommitmentState.ACCEPTED)
        with self.assertRaises(ValueError):
            ledger.transition("c1", CommitmentState.COMPLETED)
        ledger.transition("c1", CommitmentState.APPROVED)
        ledger.transition("c1", CommitmentState.COMPLETED)
        self.assertEqual(ledger.state("c1"), CommitmentState.COMPLETED)

    def test_rejected_commitment_is_terminal(self):
        ledger = CommitmentLedger()
        ledger.create("c2")
        ledger.transition("c2", CommitmentState.REJECTED)
        with self.assertRaises(ValueError):
            ledger.transition("c2", CommitmentState.ACCEPTED)


if __name__ == "__main__":
    unittest.main()
