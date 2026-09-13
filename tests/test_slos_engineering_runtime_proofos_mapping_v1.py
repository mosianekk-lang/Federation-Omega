import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'governance' / 'proofos_omega_policy_extension_slos_engineering_runtime_v2.json'

class MappingTests(unittest.TestCase):
    def test_extension_schema_and_required_lists(self):
        p=json.loads(POLICY.read_text())
        self.assertEqual(p['schema'],'FEDERATION-PROOFOS-OMEGA-ADDITIVE-EXTENSION-V1')
        for key in ('risk_rules','subsystem_rules','historical_associations','tests'):
            self.assertIn(key,p)
            self.assertIsInstance(p[key],list)

    def test_all_runtime_production_paths_are_mapped(self):
        p=json.loads(POLICY.read_text())
        patterns=set(p['subsystem_rules'][0]['patterns'])
        required={
            'superior_logic/engineering_runtime.py',
            'superior_logic/runtime_bridge.py',
            'superior_logic/finalization_kernel.py',
            'governance/proofos_omega_policy_extension_slos_engineering_runtime_v2.json',
        }
        self.assertTrue(required <= patterns)

    def test_mapping_has_global_selector_escape_court(self):
        p=json.loads(POLICY.read_text())
        courts={x['id']:x for x in p['tests']}
        c=courts['slos_engineering_runtime_proofos_mapping_v1']
        self.assertEqual(c['failure_class'],'SELECTOR_ESCAPE')
        self.assertEqual(c['block_scope'],'GLOBAL')

    def test_no_unbounded_repository_wildcard(self):
        p=json.loads(POLICY.read_text())
        all_patterns=[]
        for section in ('risk_rules','subsystem_rules'):
            for row in p[section]: all_patterns += row.get('patterns',[])
        self.assertNotIn('**',all_patterns)
        self.assertNotIn('*',all_patterns)

if __name__=='__main__': unittest.main()
