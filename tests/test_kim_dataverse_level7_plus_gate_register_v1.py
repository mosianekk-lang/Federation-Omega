from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "benchmarking/cfbe_omega/KIM_DATAVERSE_LEVEL7_PLUS_GATE_REGISTER_V1_20260901.json"


class KimDataverseLevel7PlusGateRegisterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(REGISTER.read_text(encoding="utf-8"))
        cls.by_id = {item["gate_id"]: item for item in cls.data["gates"]}

    def test_gate_ids_are_unique(self) -> None:
        self.assertEqual(len(self.data["gates"]), len(self.by_id))

    def test_wif_hardening_remains_explicit_owner_gate(self) -> None:
        gate = self.by_id["GOOGLE-WIF-HARDENING-AUTHORITY"]
        self.assertEqual("OWNER", gate["class"])
        self.assertEqual("HELD", gate["status"])
        self.assertTrue(gate["owner_authority_required"])

    def test_routine_level7_empirical_gates_are_not_misclassified_as_owner_tasks(self) -> None:
        for gate_id in (
            "L7-PERSISTENT-NO-CHAT-RESUME",
            "L7-MAINTENANCE-SELF-RESOLUTION",
            "L7-RECOVERY-SELF-RESOLUTION",
            "L7-OWNER-INTERRUPTION-REDUCTION",
            "L7-PROSPECTIVE-OWNER-VALUE",
        ):
            self.assertFalse(self.by_id[gate_id]["owner_authority_required"])

    def test_source_candidate_does_not_claim_native_evidence(self) -> None:
        self.assertEqual("CANDIDATE_IMPLEMENTED", self.by_id["L5-SOURCE-CONTROLS"]["status"])
        self.assertEqual("OPEN", self.by_id["L5-INTEGRATED-OBSERVED-EPISODES"]["status"])


if __name__ == "__main__":
    unittest.main()
