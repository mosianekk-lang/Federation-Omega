import unittest

from evidenceops.lex_omega.test_lex_omega_adversarial_boundary import (
    test_proposed_amendment_source_must_not_be_current_law_without_in_force_proof,
    test_unrelated_nonblank_pinpoint_must_not_satisfy_support_binding,
)


class LexOmegaAdversarialBoundaryAirlockTests(unittest.TestCase):
    def test_unrelated_nonblank_pinpoint_fails_closed(self):
        test_unrelated_nonblank_pinpoint_must_not_satisfy_support_binding()

    def test_proposed_amendment_without_in_force_proof_fails_closed(self):
        test_proposed_amendment_source_must_not_be_current_law_without_in_force_proof()


if __name__ == "__main__":
    unittest.main()
