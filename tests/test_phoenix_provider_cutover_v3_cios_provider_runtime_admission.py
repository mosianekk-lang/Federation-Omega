from __future__ import annotations

import io
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CIOSProviderRuntimeAdmissionTests(unittest.TestCase):
    def test_forge_provider_runtime_suite_executes(self) -> None:
        suite = unittest.defaultTestLoader.discover(
            str(ROOT / "tests"), pattern="test_cios_provider_runtime.py"
        )
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        evidence = stream.getvalue()
        self.assertTrue(result.wasSuccessful(), evidence)
        self.assertEqual(9, result.testsRun, evidence)
        self.assertIn("test_real_http_canary_serves_authenticated_semantic_health", evidence)
        self.assertIn("test_event_and_audit_persist_across_runtime_reopen", evidence)
        self.assertIn("test_parallel_provider_requests_are_serialized_without_loss", evidence)
        self.assertIn("test_bearer_holder_cannot_choose_another_tenant_or_user", evidence)

    def test_provider_runtime_contract_is_present(self) -> None:
        self.assertTrue((ROOT / "evidenceops" / "capital_intelligence_os" / "provider_runtime.py").is_file())
        self.assertTrue((ROOT / "evidenceops" / "capital_intelligence_os" / "Dockerfile.runtime").is_file())
        self.assertTrue((ROOT / "evidenceops" / "capital_intelligence_os" / "PROVIDER_RUNTIME_CONTRACT.json").is_file())


if __name__ == "__main__":
    unittest.main()
