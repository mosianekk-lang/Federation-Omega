import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ManifestCourt(unittest.TestCase):
    def test_manifest(self):
        d=json.loads((ROOT/'governance/fuse_forge_convergence_v1.json').read_text())
        self.assertEqual(d['runtime_hard_dependencies'],['PYTHON','GIT'])
        self.assertFalse(d['virtual_executor']['physical_device_claim'])
        self.assertFalse(d['physical_windows']['required_for_forge_inner_loop'])
        self.assertEqual(set(d['mutation_roots']),{'HUMAN_OWNER','SOVARA_SOL62','FDOF'})
        self.assertIn('GITHUB',d['optional_witness_surfaces'])

if __name__ == '__main__': unittest.main()
