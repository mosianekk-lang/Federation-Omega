import unittest

from evidenceops.lex_omega.test_lex_omega_adversarial_boundary import (
    test_future_effective_authority_fails_closed,
    test_missing_source_pinpoint_is_rejected_at_construction,
    test_multi_authority_partial_support_fails_closed,
    test_proposition_text_mutation_fails_closed,
    test_proposed_amendment_source_must_not_be_current_law_without_in_force_proof,
    test_stale_authority_fails_closed,
    test_support_key_substitution_fails_closed,
    test_superseded_authority_fails_closed,
    test_unrelated_nonblank_pinpoint_must_not_satisfy_support_binding,
)


class LexOmegaAdversarialBoundaryAirlockTests(unittest.TestCase):
    def test_01_support_key_substitution_fails_closed(self):
        test_support_key_substitution_fails_closed()

    def test_02_proposition_text_mutation_fails_closed(self):
        test_proposition_text_mutation_fails_closed()

    def test_03_missing_source_pinpoint_fails_closed(self):
        test_missing_source_pinpoint_is_rejected_at_construction()

    def test_04_unrelated_nonblank_pinpoint_fails_closed(self):
        test_unrelated_nonblank_pinpoint_must_not_satisfy_support_binding()

    def test_05_stale_authority_fails_closed(self):
        test_stale_authority_fails_closed()

    def test_06_superseded_authority_fails_closed(self):
        test_superseded_authority_fails_closed()

    def test_07_future_effective_authority_fails_closed(self):
        test_future_effective_authority_fails_closed()

    def test_08_proposed_amendment_without_in_force_proof_fails_closed(self):
        test_proposed_amendment_source_must_not_be_current_law_without_in_force_proof()

    def test_09_multi_authority_partial_support_fails_closed(self):
        test_multi_authority_partial_support_fails_closed()


if __name__ == "__main__":
    unittest.main()
