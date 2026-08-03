from __future__ import annotations

import unittest

from policy_kernel import ActionMandate, Constitution, PolicyKernel, PolicyRule


class PolicyKernelTests(unittest.TestCase):
    def setUp(self) -> None:
        constitution = Constitution(
            "SOL-CONSTITUTION", "6.1",
            ("proof-before-claim", "owner-final-authority", "least-effect"),
            ("expose_secret", "delete_last_good_release"),
            ("send_external_message", "financial_commitment", "live_release"),
        )
        rules = [
            PolicyRule("ALLOW-REVERSIBLE", "ALLOW", 10, required_preconditions=("snapshot",)),
            PolicyRule("DENY-SECRET", "DENY", 100, forbidden_effects=("expose_secret",)),
            PolicyRule("OWNER-LIVE", "REQUIRE_OWNER", 90, action_types=("live_release",)),
            PolicyRule("REVIEW-HIGH", "REQUIRE_REVIEW", 80, min_risk="HIGH", required_roles=("security",)),
        ]
        self.kernel = PolicyKernel(constitution, rules)

    def mandate(self, **changes):
        base = dict(
            action_id="a1", action_type="deploy_candidate", risk="MEDIUM",
            proposer_role="planner", executor_role="builder", certifier_role="auditor",
            preconditions=("snapshot",), intended_effects=("create_revision",),
            rollback_available=True, review_roles=(), proof_requirements=("execution", "readback"),
        )
        base.update(changes)
        return ActionMandate(**base)

    def test_eligible_and_proof_carrying(self):
        decision = self.kernel.evaluate(self.mandate(), {"snapshot"})
        self.assertEqual(decision.status, "ELIGIBLE")
        self.assertFalse(self.kernel.verify_proof_bundle(decision, {"execution": {}})["execution_authorised"])
        self.assertTrue(self.kernel.verify_proof_bundle(decision, {"execution": {}, "readback": {}})["execution_authorised"])

    def test_role_separation_and_preconditions(self):
        same_role = self.mandate(executor_role="planner")
        self.assertEqual(self.kernel.evaluate(same_role, {"snapshot"}).status, "DENIED")
        self.assertEqual(self.kernel.evaluate(self.mandate(), set()).status, "DENIED")

    def test_constitution_and_owner_boundaries(self):
        forbidden = self.mandate(intended_effects=("expose_secret",))
        self.assertEqual(self.kernel.evaluate(forbidden, {"snapshot"}).status, "DENIED")
        owner = self.mandate(action_type="live_release")
        self.assertEqual(self.kernel.evaluate(owner, {"snapshot"}).status, "OWNER_AUTHORITY_REQUIRED")

    def test_high_risk_review_and_rollback(self):
        no_rollback = self.mandate(risk="HIGH", rollback_available=False)
        self.assertEqual(self.kernel.evaluate(no_rollback, {"snapshot"}).status, "DENIED")
        reviewed = self.mandate(risk="HIGH", review_roles=("security",))
        self.assertEqual(self.kernel.evaluate(reviewed, {"snapshot"}).status, "ELIGIBLE")

    def test_fail_closed_and_conflict_resolution(self):
        empty = PolicyKernel(self.kernel.constitution, [])
        self.assertEqual(empty.evaluate(self.mandate(), {"snapshot"}).status, "DENIED")
        conflict = PolicyKernel(self.kernel.constitution, [
            PolicyRule("ALLOW", "ALLOW", 1), PolicyRule("DENY", "DENY", 2)
        ])
        self.assertEqual(conflict.evaluate(self.mandate(preconditions=()), set()).status, "DENIED")


if __name__ == "__main__":
    unittest.main()
