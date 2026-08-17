from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "services" / "jarvis-ultimate"
SERVICE_TESTS = SERVICE / "tests"


def _load_module(path: Path) -> ModuleType:
    name = f"_jarvis_t20_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class JarvisT20AirlockContractTests(unittest.TestCase):
    def test_build_contract_preserves_truth_boundary(self) -> None:
        contract = json.loads(
            (SERVICE / "BUILD_CONTRACT.json").read_text(encoding="utf-8")
        )
        boundary = contract["executionBoundary"]
        proof = contract["proofBoundary"]

        self.assertEqual(boundary["maxDirectiveSeconds"], 1200)
        self.assertLess(
            boundary["splitTriggerSeconds"],
            boundary["expansionCutoffSeconds"],
        )
        self.assertLess(
            boundary["expansionCutoffSeconds"],
            boundary["forceReleaseSeconds"],
        )
        self.assertLess(
            boundary["forceReleaseSeconds"],
            boundary["maxDirectiveSeconds"],
        )
        self.assertTrue(proof["t20GovernorSourceBuilt"])
        self.assertTrue(proof["t20GovernorTestedLocal"])
        self.assertFalse(proof["t20CiVerified"])
        self.assertFalse(proof["googleWorkspaceBound"])
        self.assertFalse(proof["geminiLive"])
        self.assertFalse(proof["cloudDeployed"])

    def test_package_discovery_is_explicit_and_static_ui_is_declared(self) -> None:
        config = tomllib.loads(
            (SERVICE / "pyproject.toml").read_text(encoding="utf-8")
        )
        discovery = config["tool"]["setuptools"]["packages"]["find"]
        package_data = config["tool"]["setuptools"]["package-data"]

        self.assertEqual(discovery["include"], ["jarvis*"])
        self.assertIn("web*", discovery["exclude"])
        self.assertIn("tests*", discovery["exclude"])
        self.assertIn("static/*.html", package_data["jarvis"])
        self.assertTrue(
            (SERVICE / "jarvis" / "static" / "index.html").is_file()
        )


def load_tests(
    loader: unittest.TestLoader,
    tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    """Bind canonical JARVIS T20 regressions into the allowlisted Airlock.

    Federation Omega Airlock executes test_phoenix_provider_cutover_v3*.py.
    The bridge discovers the service-owned tests without copying or weakening
    their assertions and adds truth-boundary/package regressions at admission.
    """
    del tests, pattern
    service_path = str(SERVICE)
    if service_path not in sys.path:
        sys.path.insert(0, service_path)

    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(JarvisT20AirlockContractTests))
    for path in sorted(SERVICE_TESTS.glob("test_*.py")):
        suite.addTests(loader.loadTestsFromModule(_load_module(path)))
    return suite


if __name__ == "__main__":
    unittest.main()
