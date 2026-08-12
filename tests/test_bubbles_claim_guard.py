from __future__ import annotations

import unittest

from bubbles.claim_guard import ClaimGuard


class ClaimGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.guard = ClaimGuard.load()

    def test_six_flagships_are_registered(self) -> None:
        self.assertEqual({"CIOS", "ECERTIFY", "CASEFORGE", "IPEP", "ARCHITRON", "K10"}, set(self.guard.projects))

    def test_cios_can_claim_canary_ready_but_not_deployed(self) -> None:
        self.assertTrue(self.guard.decide("CIOS", "PROVIDER_CANARY_READY").allowed)
        decision = self.guard.decide("CIOS", "DEPLOYED")
        self.assertFalse(decision.allowed)
        self.assertEqual("REQUEST_EXCEEDS_VERIFIED_SCOPE", decision.reason)

    def test_ecertify_cannot_claim_public_live(self) -> None:
        allowed, hits = self.guard.validate_text("ECERTIFY", "eCertify is publicly live")
        self.assertFalse(allowed)
        self.assertIn("eCertify is publicly live", hits)

    def test_caseforge_provider_quality_cannot_inherit_from_deterministic_benchmark(self) -> None:
        project = self.guard.public_record("CASEFORGE")
        self.assertEqual("DETERMINISTIC_TESTED", project["evidence_state"])
        self.assertFalse(project["provider_verified"])
        self.assertFalse(self.guard.decide("CASEFORGE", "PROVIDER_VERIFIED").allowed)

    def test_ipep_local_runtime_claim_is_allowed_cloud_deployment_is_not(self) -> None:
        self.assertTrue(self.guard.decide("IPEP", "LOCAL_RUNTIME_VERIFIED").allowed)
        self.assertFalse(self.guard.decide("IPEP", "DEPLOYED").allowed)

    def test_architron_and_k10_remain_implemented_until_next_proof(self) -> None:
        self.assertEqual("IMPLEMENTED", self.guard.project("ARCHITRON")["evidence_state"])
        self.assertEqual("IMPLEMENTED", self.guard.project("K10")["evidence_state"])
        self.assertFalse(self.guard.decide("K10", "LOCAL_RUNTIME_VERIFIED").allowed)

    def test_unknown_maturity_fails_closed(self) -> None:
        decision = self.guard.decide("CIOS", "MAGIC_PRODUCTION")
        self.assertFalse(decision.allowed)
        self.assertEqual("UNKNOWN_REQUESTED_MATURITY_STATE", decision.reason)


if __name__ == "__main__":
    unittest.main()
