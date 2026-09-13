import unittest

from superior_logic.skill_forge import SkillForge, SkillReplay, TrajectoryLesson


class SkillForgeV2Tests(unittest.TestCase):
    def candidate(self):
        lessons = (
            TrajectoryLesson("m1", ("inspect", "repair", "verify"), ("proof:m1",), True, True),
            TrajectoryLesson("m2", ("inspect", "repair", "verify"), ("proof:m2",), True, True),
            TrajectoryLesson("m3", ("inspect", "repair", "verify"), ("proof:m3",), True, True),
        )
        return SkillForge().propose(name="bounded repair", description="repair a bounded defect", lessons=lessons)

    def test_hardened_skill_requires_preconditions_negatives_and_verification(self):
        skill = self.candidate()
        contract = SkillForge().harden(
            skill,
            preconditions=("exact source revision known", "rollback path available"),
            negative_examples=("do not infer provider success from source-only proof",),
            verification_requirements=("independent replay", "semantic readback"),
            expires_at="2026-10-01T00:00:00+00:00",
        )
        self.assertFalse(contract.effect_authority_inherited)
        self.assertEqual(contract.authority_ceiling, "A1_INTERNAL")
        self.assertTrue(contract.valid_at("2026-09-20T00:00:00+00:00"))
        self.assertFalse(contract.valid_at("2026-10-02T00:00:00+00:00"))
        rendered = SkillForge().render_hardened_skill_md(skill, contract)
        self.assertIn("Negative examples", rendered)
        self.assertIn("Effect authority inherited: `false`", rendered)

    def test_hardening_cannot_grant_provider_effect_authority(self):
        skill = self.candidate()
        with self.assertRaises(ValueError):
            SkillForge().harden(
                skill,
                preconditions=("known",),
                negative_examples=("bad path",),
                verification_requirements=("verify",),
                expires_at="2026-10-01T00:00:00+00:00",
                authority_ceiling="A2_PROVIDER_EFFECT",
            )

    def test_legacy_replay_rule_remains_backward_compatible(self):
        skill = self.candidate()
        result = SkillForge().evaluate(
            skill,
            (
                SkillReplay("r1", True, True, True, "proof:r1"),
                SkillReplay("r2", True, True, True, "proof:r2"),
            ),
        )
        self.assertEqual(result, "ADOPT_CANDIDATE")

    def test_hardened_replay_requires_actor_and_trust_provenance(self):
        skill = self.candidate()
        result = SkillForge().evaluate_hardened(
            skill,
            (
                SkillReplay("r1", True, True, True, "proof:r1"),
                SkillReplay("r2", True, True, True, "proof:r2"),
            ),
            implementation_actor_id="impl",
            implementation_trust_domain="lane-impl",
        )
        self.assertEqual(result, "HOLD_INDEPENDENT_REPLAY_INCOMPLETE")

    def test_hardened_replay_rejects_same_trust_domain_aliases(self):
        skill = self.candidate()
        result = SkillForge().evaluate_hardened(
            skill,
            (
                SkillReplay("r1", True, True, True, "proof:r1", "judge-a", "lane-impl"),
                SkillReplay("r2", True, True, True, "proof:r2", "judge-b", "lane-impl"),
            ),
            implementation_actor_id="impl",
            implementation_trust_domain="lane-impl",
        )
        self.assertEqual(result, "HOLD_INDEPENDENT_REPLAY_INCOMPLETE")

    def test_hardened_replay_accepts_distinct_external_trust_domains(self):
        skill = self.candidate()
        result = SkillForge().evaluate_hardened(
            skill,
            (
                SkillReplay("r1", True, True, True, "proof:r1", "judge-a", "lane-a"),
                SkillReplay("r2", True, True, True, "proof:r2", "judge-b", "lane-b"),
            ),
            implementation_actor_id="impl",
            implementation_trust_domain="lane-impl",
        )
        self.assertEqual(result, "ADOPT_CANDIDATE")

    def test_hardened_replay_preserves_regression_veto(self):
        skill = self.candidate()
        result = SkillForge().evaluate_hardened(
            skill,
            (
                SkillReplay("r1", True, True, False, "proof:r1", "judge-a", "lane-a"),
            ),
            implementation_actor_id="impl",
            implementation_trust_domain="lane-impl",
        )
        self.assertEqual(result, "REJECT_REGRESSION")


if __name__ == "__main__":
    unittest.main()
