from __future__ import annotations

import importlib.util
import io
import py_compile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_test_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load test module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReconciliationFabricV2PhoenixAdmissionTests(unittest.TestCase):
    def test_full_v2_adversarial_and_frontier_courts_are_independently_runnable(self):
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        modules = (
            (
                ROOT / "tests" / "test_formation_omega_reconciliation_fabric_v2.py",
                "_rfv2_adversarial_court",
            ),
            (
                ROOT / "tests" / "test_formation_omega_reconciliation_v2_frontier_contracts.py",
                "_rfv2_frontier_contract_court",
            ),
        )
        for path, module_name in modules:
            self.assertTrue(path.is_file(), path)
            suite.addTests(loader.loadTestsFromModule(_load_test_module(path, module_name)))

        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        output = stream.getvalue()
        self.assertGreaterEqual(result.testsRun, 18, output)
        self.assertTrue(result.wasSuccessful(), output)
        self.assertIn("test_durable_replay_survives_restart_and_rejects_conflict", output)
        self.assertIn("test_cfbe_keeps_unverified_frontier_adapters_evidence_discounted", output)
        self.assertIn("OK", output)

    def test_core_compiles_without_optional_frontier_runtimes(self):
        source = ROOT / "formation_omega" / "reconciliation_fabric_v2.py"
        self.assertTrue(source.is_file(), source)
        py_compile.compile(str(source), doraise=True)

    def test_external_frontier_tools_remain_optional_not_import_dependencies(self):
        source = (ROOT / "formation_omega" / "reconciliation_fabric_v2.py").read_text(encoding="utf-8")
        for forbidden_import in (
            "import temporalio",
            "import langgraph",
            "import opentelemetry",
            "import sigstore",
            "import opa",
            "import tla",
            "from temporalio",
            "from langgraph",
            "from opentelemetry",
            "from sigstore",
        ):
            self.assertNotIn(forbidden_import, source.lower())


if __name__ == "__main__":
    unittest.main()
