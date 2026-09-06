from __future__ import annotations

import inspect
from pathlib import Path
import tempfile
import unittest


class TestFederationAutopilotSuitesProofOSBridge(unittest.TestCase):
    """Execute the exact embedded 93-case Autopilot corpus with stdlib only.

    The historical test module uses pytest only as a collection/parameterization
    shell plus tmp_path injection. The case bodies themselves are plain Python.
    ProofOS can therefore execute the same embedded corpus without introducing a
    repository-wide pytest runtime dependency or weakening the admission policy.
    """

    def test_embedded_autopilot_court_executes_all_93_cases(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        source_path = repo_root / "tests" / "test_federation_autopilot_suites_v1.py"
        source = source_path.read_text(encoding="utf-8")
        prefix, marker, _ = source.partition("CASES = []")
        self.assertTrue(marker, "Autopilot embedded-case marker missing")
        prefix = prefix.replace("import pytest\n", "", 1)

        namespace = {"__name__": "_autopilot_proofos_embedded_court"}
        exec(compile(prefix, str(source_path), "exec"), namespace)
        test_sources = namespace.get("TEST_SOURCES")
        self.assertIsInstance(test_sources, dict)

        cases: list[tuple[str, object]] = []
        for module_name, case_source in sorted(test_sources.items()):
            case_namespace = {"__name__": f"_autopilot_case_{module_name}"}
            exec(compile(case_source, f"<{module_name}>", "exec"), case_namespace)
            for name, fn in sorted(case_namespace.items()):
                if name.startswith("test_") and callable(fn):
                    cases.append((f"{module_name}::{name}", fn))

        self.assertEqual(len(cases), 93, f"expected 93 local-qualified cases, found {len(cases)}")

        failures: list[str] = []
        for case_id, case in cases:
            try:
                if "tmp_path" in inspect.signature(case).parameters:
                    with tempfile.TemporaryDirectory(prefix="autopilot-suite-court-") as d:
                        case(Path(d))
                else:
                    case()
            except Exception as exc:  # pragma: no cover - surfaced as proof detail
                failures.append(f"{case_id}: {type(exc).__name__}: {exc}")

        self.assertFalse(failures, "Autopilot embedded court failures:\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
