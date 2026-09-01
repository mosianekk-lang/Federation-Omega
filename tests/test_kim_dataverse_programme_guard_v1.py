from __future__ import annotations

from pathlib import Path
import unittest

from benchmarking.cfbe_omega.kim_dataverse_programme_guard_v1 import scan_files, scan_text_for_authority_expansion


ROOT = Path(__file__).resolve().parents[1]


class KimDataverseProgrammeGuardTests(unittest.TestCase):
    def test_authority_true_literal_is_detected(self) -> None:
        findings = scan_text_for_authority_expansion('{"provider_effect_authorized": true}')
        self.assertIn('provider_effect_authorized\": true', findings)

    def test_false_authority_literals_are_allowed(self) -> None:
        self.assertEqual((), scan_text_for_authority_expansion('{"provider_effect_authorized": false}'))

    def test_current_manifest_has_no_authority_expansion(self) -> None:
        paths = (
            ROOT / "benchmarking/cfbe_omega/KIM_DATAVERSE_LEVEL7_PLUS_IMPLEMENTATION_MANIFEST_V1_20260901.json",
            ROOT / "governance/proofos_omega_policy_extension_kim_dataverse_level7_plus_v1.json",
        )
        self.assertEqual((), scan_files(paths))


if __name__ == "__main__":
    unittest.main()
