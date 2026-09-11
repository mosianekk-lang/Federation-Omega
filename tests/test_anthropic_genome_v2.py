import unittest

from fuse_anthropic_genome_v2.context import ContextPressureController
from fuse_anthropic_genome_v2.memory import MemoryTrustPlanner, VersionedMemoryStore
from fuse_anthropic_genome_v2.outcomes import AgentDefinitionStore, OutcomeEvaluator, OutcomeState
from fuse_anthropic_genome_v2.runtime import AdvisorPolicy, Effort, EffortGovernor, SandboxPlanner, ToolLocusRouter


class AnthropicGenomeV2Tests(unittest.TestCase):
    def test_advisor_for_high_value_case(self):
        d = AdvisorPolicy.decide(complexity=.95, uncertainty=.9, failure_cost=.9, executor_quality=.7)
        self.assertTrue(d.use_advisor)
        self.assertGreaterEqual(d.max_uses, 1)

    def test_advisor_skips_low_value_case(self):
        d = AdvisorPolicy.decide(complexity=.1, uncertainty=.1, failure_cost=.1, executor_quality=.95)
        self.assertFalse(d.use_advisor)

    def test_effort_governor_max_for_hard_long_horizon(self):
        self.assertEqual(EffortGovernor.choose(difficulty=1, uncertainty=.9, long_horizon=True, failure_cost=.9), Effort.MAX)

    def test_effort_governor_low_for_simple_cost_sensitive(self):
        self.assertEqual(EffortGovernor.choose(difficulty=.05, uncertainty=.05, long_horizon=False, failure_cost=.05, cost_pressure=1), Effort.LOW)

    def test_browser_selected_for_web_only(self):
        self.assertEqual(ToolLocusRouter.select(web_only=True, desktop_required=False, sensitive_data=False), "browser_toolset")

    def test_computer_selected_for_desktop(self):
        self.assertEqual(ToolLocusRouter.select(web_only=False, desktop_required=True, sensitive_data=False), "computer_toolset")

    def test_sensitive_runtime_prefers_self_hosted(self):
        self.assertEqual(SandboxPlanner.plan(sensitive_data=True, internal_network_required=False, write_required=True).mode, "self_hosted")

    def test_untrusted_memory_is_read_only(self):
        self.assertEqual(MemoryTrustPlanner.choose(shared_reference=False, untrusted_input_present=True, write_needed=True).access, "read_only")

    def test_trusted_learning_memory_can_write(self):
        self.assertEqual(MemoryTrustPlanner.choose(shared_reference=False, untrusted_input_present=False, write_needed=True).access, "read_write")

    def test_memory_versions_are_immutable_history(self):
        s = VersionedMemoryStore()
        s.write("project/a", "one", actor="agent")
        s.write("project/a", "two", actor="agent")
        self.assertEqual([v.content for v in s.history("project/a")], ["one", "two"])

    def test_context_pressure_composes_controls(self):
        p = ContextPressureController.plan(tool_count=50, tool_result_tokens=30000, conversation_tokens=120000, stable_toolset=True, repetitive_fanout=True, memory_available=True)
        self.assertIn("TOOL_SEARCH", p.actions)
        self.assertIn("PROGRAMMATIC_TOOL_CALLING", p.actions)
        self.assertIn("PROMPT_CACHE", p.actions)
        self.assertIn("CLEAR_STALE_TOOL_RESULTS", p.actions)
        self.assertIn("MEMORY_OFFLOAD_BEFORE_COMPACTION", p.actions)
        self.assertIn("SERVER_COMPACTION", p.actions)

    def test_context_pressure_does_not_overmanage_small_context(self):
        p = ContextPressureController.plan(tool_count=3, tool_result_tokens=100, conversation_tokens=5000, stable_toolset=False, repetitive_fanout=False, memory_available=False)
        self.assertEqual(p.actions, ())

    def test_outcome_requires_evaluation_not_self_claim(self):
        e = OutcomeEvaluator()
        e.define("o1", "verified patch", max_iterations=2)
        e.start("o1")
        r = e.evaluate("o1", satisfied=False, recoverable=True, explanation="tests failing")
        self.assertEqual(r.state, OutcomeState.NEEDS_REVISION)

    def test_outcome_hits_iteration_ceiling(self):
        e = OutcomeEvaluator()
        e.define("o1", "verified patch", max_iterations=1)
        e.start("o1")
        r = e.evaluate("o1", satisfied=False, recoverable=True)
        self.assertEqual(r.state, OutcomeState.MAX_ITERATIONS_REACHED)

    def test_agent_definition_optimistic_concurrency(self):
        s = AgentDefinitionStore()
        a = s.create("a", model="m1", tools_digest="t1", skills_digest="s1")
        b = s.update("a", expected_version=a.version, model="m2")
        self.assertEqual(b.version, 2)
        with self.assertRaises(RuntimeError):
            s.update("a", expected_version=1, model="m3")


if __name__ == "__main__":
    unittest.main()
