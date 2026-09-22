from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOCTRINE = ROOT / "governance/KIM_DATAVERSE_AUTONOMIC_OPERATING_DOCTRINE_V1_20260901.md"


class KimDataverseAutonomicOperatingDoctrineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = DOCTRINE.read_text(encoding="utf-8")

    def test_owner_interruption_is_exception_not_default(self) -> None:
        self.assertIn("reversible, self-resolvable", self.text)
        self.assertIn("AutoPilot responsibility rather than an owner task", self.text)

    def test_four_loops_are_event_classes_not_four_sovereign_autopilots(self) -> None:
        self.assertIn("MISSION, MAINTENANCE, RECOVERY and EVOLUTION", self.text)
        self.assertIn("not four sovereign autopilots", self.text)

    def test_chat_is_cockpit_not_persistent_carrier(self) -> None:
        self.assertIn("Chat is an owner cockpit", self.text)
        self.assertIn("not the required persistent carrier", self.text)

    def test_maintenance_authority_cannot_expand_wif_or_provider_authority(self) -> None:
        self.assertIn("does not include IAM/WIF mutation", self.text)
        self.assertIn("provider authority expansion", self.text)

    def test_repeated_owner_continuation_is_autonomy_debt(self) -> None:
        self.assertIn("record autonomy debt", self.text)
        self.assertIn("Repeated owner intervention is evidence of incomplete autonomy architecture", self.text)


if __name__ == "__main__":
    unittest.main()
