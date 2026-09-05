from __future__ import annotations

import unittest

from bubbles.chat_governor_omega3.interop_frontier import (
    AgentTaskEnvelope,
    CapabilityAdvertisement,
    MCPRequestMetadata,
    admit_agent_task,
)


class InteropFrontierTests(unittest.TestCase):
    def setUp(self):
        self.card = CapabilityAdvertisement.build(
            system_id="lex",
            name="LEX",
            version="1",
            skills=("research", "reason", "research"),
            authority_ceiling="A1_INTERNAL",
        )

    def test_advertisement_is_deterministic(self):
        other = CapabilityAdvertisement.build(system_id="lex", name="LEX", version="1", skills=("reason", "research"), authority_ceiling="A1_INTERNAL")
        self.assertEqual(self.card.skills, ("reason", "research"))
        self.assertEqual(self.card.fingerprint, other.fingerprint)

    def test_task_requires_skill_and_authentication(self):
        task = AgentTaskEnvelope("t1", "c1", "m1", "research", "ref:1", "trace:1")
        self.assertEqual(admit_agent_task(task, self.card, authenticated=False, current_authority="A1_INTERNAL").state, "AUTHENTICATION_REQUIRED")
        self.assertTrue(admit_agent_task(task, self.card, authenticated=True, current_authority="A1_INTERNAL").admitted)
        bad = AgentTaskEnvelope("t2", "c1", "m1", "deploy", "ref:2", "trace:2")
        self.assertEqual(admit_agent_task(bad, self.card, authenticated=True, current_authority="A1_INTERNAL").state, "SKILL_NOT_ADVERTISED")

    def test_effectful_task_never_inherits_low_authority(self):
        task = AgentTaskEnvelope("t1", "c1", "m1", "research", "ref:1", "trace:1", effectful=True, authority_ref="HMC:x")
        decision = admit_agent_task(task, self.card, authenticated=True, current_authority="A1_INTERNAL")
        self.assertFalse(decision.admitted)
        self.assertEqual(decision.state, "CURRENT_AUTHORITY_INSUFFICIENT")

    def test_mcp_metadata_has_deterministic_capabilities_and_cache_key(self):
        a = MCPRequestMetadata.build(protocol_version="2026-07-28", capabilities=("tasks", "tools", "tasks"), ttl_ms=30000, cache_scope="mission")
        b = MCPRequestMetadata.build(protocol_version="2026-07-28", capabilities=("tools", "tasks"), ttl_ms=30000, cache_scope="mission", traceparent="different")
        self.assertEqual(a.capabilities, ("tasks", "tools"))
        self.assertEqual(a.cache_key, b.cache_key)


if __name__ == "__main__":
    unittest.main()
