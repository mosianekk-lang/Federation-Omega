from __future__ import annotations

import json
from pathlib import Path
import unittest


class MissionIRShadowContractFixtureTests(unittest.TestCase):
    def test_contract_preserves_no_effect_and_no_promotion_boundaries(self):
        path = Path('benchmarking/cfbe_omega/mission_ir_golden_path_shadow_contract_v1.json')
        contract = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual('SC-MIR-20260831-001', contract['binding_id'])
        self.assertEqual(['cell-canva'], contract['required_selected_cell_ids'])
        self.assertFalse(contract['provider_effect_authorized'])
        self.assertFalse(contract['financial_effect_authorized'])
        self.assertFalse(contract['publication_authorized'])
        self.assertEqual(0, contract['external_effects'])
        self.assertTrue(contract['observed_runtime_comparison_required_for_performance_claim'])
        self.assertFalse(contract['stable_promotion_allowed'])


if __name__ == '__main__':
    unittest.main()
