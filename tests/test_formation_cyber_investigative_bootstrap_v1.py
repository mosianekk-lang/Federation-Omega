import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FormationCyberInvestigativeBootstrapTests(unittest.TestCase):
    def test_bootstrap_inherits_engine_before_route_compile(self):
        cfg = json.loads((ROOT / "config" / "fuse-bootstrap-inheritance-v3.json").read_text(encoding="utf-8"))
        order = cfg["required_order"]
        self.assertIn("FORMATION_CYBER_INVESTIGATIVE_ENGINE", order)
        self.assertLess(order.index("FORMATION_CYBER_INVESTIGATIVE_ENGINE"), order.index("ROUTE_COMPILE"))
        engine = cfg["formation_cyber_investigative_engine"]
        self.assertFalse(engine["new_state_root"])
        self.assertFalse(engine["authority_expansion"])
        self.assertFalse(engine["external_effect_authorized"])

    def test_formation_power_binds_engine_for_relevant_work(self):
        src = (ROOT / "federation" / "formation_power_inheritance_v2.py").read_text(encoding="utf-8")
        self.assertIn("FormationCyberInvestigativeEngine", src)
        self.assertIn("FORMATION_CYBER_INVESTIGATIVE_ENGINE_V1", src)
        self.assertIn("PERSISTENT_FAILURE_FINGERPRINT_AND_WORKAROUND_COMPILATION", src)

    def test_governance_has_closed_source_and_bypass_boundaries(self):
        cfg = json.loads((ROOT / "config" / "fuse-formation-cyber-investigative-engine-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["rights_boundary"]["closed_source_default"], "CLEAN_ROOM_BEHAVIOURAL_OR_METADATA_ONLY")
        prohibited = set(cfg["rights_boundary"]["prohibited"])
        self.assertIn("AUTHENTICATION_BYPASS", prohibited)
        self.assertIn("PROPRIETARY_SOURCE_EXFILTRATION", prohibited)
        self.assertIn("EXPLOITATION_WITHOUT_SEPARATE_EXACT_AUTHORITY", prohibited)


if __name__ == "__main__":
    unittest.main()
