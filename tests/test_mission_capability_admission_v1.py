from __future__ import annotations

import unittest

from federation.capability_truth_v1 import (
    CapabilityTruthRecord,
    ClaimKind,
    EvidenceRef,
    Maturity,
)
from federation.mission_capability_admission_v1 import (
    Equivalence,
    MissionCapabilityCompiler,
    MissionCapabilityRequirement,
    SubstituteCapability,
)
from federation.mission_ir import MissionIR


def mission() -> MissionIR:
    return MissionIR(
        mission_id="MISSION-TEST-1",
        objective="complete verified mission",
        domain="test",
        outcome_contract="all mandatory capability gates pass",
        source_frontier="current",
        privacy_class="P1_INTERNAL",
        rights_state="OWNER_CONTROLLED",
        proof_requirements=("proof",),
    )


def evidence(cap: str, kind: ClaimKind, maturity: Maturity, *, fresh=True, independent=False, eid="e1"):
    return EvidenceRef(eid, cap, kind, f"ref:{eid}", maturity, fresh=fresh, independently_verified=independent)


class MissionCapabilityAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.compiler = MissionCapabilityCompiler()

    def test_bible_requirement_cannot_admit_runtime_requirement(self):
        rec = CapabilityTruthRecord("AGENT_RUNTIME").add(evidence("AGENT_RUNTIME", ClaimKind.REQUIREMENT, Maturity.PROVIDER_RUNNING))
        receipt = self.compiler.admit(mission(), [MissionCapabilityRequirement("AGENT_RUNTIME", Maturity.PROVIDER_RUNNING)], {"AGENT_RUNTIME": rec})
        self.assertFalse(receipt.admitted)
        self.assertEqual(receipt.blocking_capabilities, ("AGENT_RUNTIME",))

    def test_agent_role_registration_cannot_admit_runtime_requirement(self):
        rec = CapabilityTruthRecord("AGENT_RUNTIME").add(evidence("AGENT_RUNTIME", ClaimKind.ROLE_REGISTRATION, Maturity.PROVIDER_RUNNING))
        receipt = self.compiler.admit(mission(), [MissionCapabilityRequirement("AGENT_RUNTIME", Maturity.PROVIDER_RUNNING)], {"AGENT_RUNTIME": rec})
        self.assertFalse(receipt.admitted)

    def test_runtime_receipt_can_admit_runtime_requirement(self):
        rec = CapabilityTruthRecord("AGENT_RUNTIME").add(evidence("AGENT_RUNTIME", ClaimKind.RUNTIME_RECEIPT, Maturity.PROVIDER_RUNNING))
        receipt = self.compiler.admit(mission(), [MissionCapabilityRequirement("AGENT_RUNTIME", Maturity.PROVIDER_RUNNING)], {"AGENT_RUNTIME": rec})
        self.assertTrue(receipt.admitted)
        self.assertEqual(receipt.decisions[0].state, "SATISFIED_DIRECT")

    def test_stale_runtime_receipt_fails_when_fresh_required(self):
        rec = CapabilityTruthRecord("AGENT_RUNTIME").add(evidence("AGENT_RUNTIME", ClaimKind.RUNTIME_RECEIPT, Maturity.PROVIDER_RUNNING, fresh=False))
        receipt = self.compiler.admit(mission(), [MissionCapabilityRequirement("AGENT_RUNTIME", Maturity.PROVIDER_RUNNING)], {"AGENT_RUNTIME": rec})
        self.assertFalse(receipt.admitted)

    def test_independent_requirement_fails_without_independent_evidence(self):
        rec = CapabilityTruthRecord("PROOF").add(evidence("PROOF", ClaimKind.BEHAVIOURAL_EVIDENCE, Maturity.BEHAVIOUR_VERIFIED))
        req = MissionCapabilityRequirement("PROOF", Maturity.BEHAVIOUR_VERIFIED, require_independent_verification=True)
        self.assertFalse(self.compiler.admit(mission(), [req], {"PROOF": rec}).admitted)

    def test_independent_requirement_passes_with_independent_evidence(self):
        rec = CapabilityTruthRecord("PROOF").add(evidence("PROOF", ClaimKind.BEHAVIOURAL_EVIDENCE, Maturity.BEHAVIOUR_VERIFIED, independent=True))
        req = MissionCapabilityRequirement("PROOF", Maturity.BEHAVIOUR_VERIFIED, require_independent_verification=True)
        self.assertTrue(self.compiler.admit(mission(), [req], {"PROOF": rec}).admitted)

    def test_missing_record_holds_mission(self):
        receipt = self.compiler.admit(mission(), [MissionCapabilityRequirement("MISSING", Maturity.BUILT)], {})
        self.assertFalse(receipt.admitted)

    def test_optional_missing_capability_does_not_block(self):
        req = MissionCapabilityRequirement("OPTIONAL", Maturity.BUILT, mandatory=False)
        receipt = self.compiler.admit(mission(), [req], {})
        self.assertTrue(receipt.admitted)
        self.assertEqual(receipt.decisions[0].state, "OPTIONAL_UNSATISFIED")

    def test_full_equivalent_substitute_can_satisfy(self):
        sub = CapabilityTruthRecord("SAFE_LANES").add(evidence("SAFE_LANES", ClaimKind.BEHAVIOURAL_EVIDENCE, Maturity.BEHAVIOUR_VERIFIED))
        req = MissionCapabilityRequirement(
            "TRUE_SWARM",
            Maturity.BEHAVIOUR_VERIFIED,
            substitutes=(SubstituteCapability("SAFE_LANES", Equivalence.FULL, proof_ref="proof:eq"),),
        )
        receipt = self.compiler.admit(mission(), [req], {"SAFE_LANES": sub})
        self.assertTrue(receipt.admitted)
        self.assertEqual(receipt.decisions[0].state, "SATISFIED_EQUIVALENT")

    def test_partial_equivalence_never_satisfies_mandatory_requirement(self):
        sub = CapabilityTruthRecord("SAFE_LANES").add(evidence("SAFE_LANES", ClaimKind.BEHAVIOURAL_EVIDENCE, Maturity.BEHAVIOUR_VERIFIED))
        req = MissionCapabilityRequirement(
            "TRUE_SWARM",
            Maturity.BEHAVIOUR_VERIFIED,
            substitutes=(SubstituteCapability("SAFE_LANES", Equivalence.PARTIAL, proof_ref="proof:partial"),),
        )
        self.assertFalse(self.compiler.admit(mission(), [req], {"SAFE_LANES": sub}).admitted)

    def test_full_equivalence_requires_proof_ref(self):
        with self.assertRaises(ValueError):
            SubstituteCapability("ALT", Equivalence.FULL).validate()

    def test_substitute_cannot_equal_primary(self):
        req = MissionCapabilityRequirement("X", Maturity.BUILT, substitutes=(SubstituteCapability("X", Equivalence.PARTIAL),))
        with self.assertRaises(ValueError): req.validate()

    def test_duplicate_mission_capability_requirement_rejected(self):
        req = MissionCapabilityRequirement("X", Maturity.BUILT)
        with self.assertRaises(ValueError): self.compiler.admit(mission(), [req, req], {})

    def test_revoked_capability_holds_mission(self):
        rec = CapabilityTruthRecord("X").add(evidence("X", ClaimKind.IMPLEMENTATION, Maturity.BUILT)).revoke("unsafe")
        self.assertFalse(self.compiler.admit(mission(), [MissionCapabilityRequirement("X", Maturity.BUILT)], {"X": rec}).admitted)

    def test_source_admitted_does_not_satisfy_hosted_requirement(self):
        rec = CapabilityTruthRecord("X").add(evidence("X", ClaimKind.SOURCE_ADMISSION, Maturity.SOURCE_ADMITTED))
        self.assertFalse(self.compiler.admit(mission(), [MissionCapabilityRequirement("X", Maturity.HOSTED)], {"X": rec}).admitted)

    def test_receipt_is_deterministic(self):
        rec = CapabilityTruthRecord("X").add(evidence("X", ClaimKind.IMPLEMENTATION, Maturity.BUILT))
        req = [MissionCapabilityRequirement("X", Maturity.BUILT)]
        a = self.compiler.admit(mission(), req, {"X": rec})
        b = self.compiler.admit(mission(), req, {"X": rec})
        self.assertEqual(a.receipt_digest, b.receipt_digest)

    def test_multiple_mandatory_requirements_all_must_pass(self):
        x = CapabilityTruthRecord("X").add(evidence("X", ClaimKind.IMPLEMENTATION, Maturity.BUILT, eid="x"))
        reqs = [MissionCapabilityRequirement("X", Maturity.BUILT), MissionCapabilityRequirement("Y", Maturity.BUILT)]
        r = self.compiler.admit(mission(), reqs, {"X": x})
        self.assertFalse(r.admitted)
        self.assertEqual(r.blocking_capabilities, ("Y",))

    def test_substitute_specific_maturity_can_be_stricter(self):
        sub = CapabilityTruthRecord("ALT").add(evidence("ALT", ClaimKind.SOURCE_ADMISSION, Maturity.SOURCE_ADMITTED))
        req = MissionCapabilityRequirement("X", Maturity.BUILT, substitutes=(SubstituteCapability("ALT", Equivalence.FULL, Maturity.HOSTED, "proof:eq"),))
        self.assertFalse(self.compiler.admit(mission(), [req], {"ALT": sub}).admitted)

    def test_no_requirements_admits_structurally_valid_mission(self):
        self.assertTrue(self.compiler.admit(mission(), [], {}).admitted)


if __name__ == "__main__":
    unittest.main()
