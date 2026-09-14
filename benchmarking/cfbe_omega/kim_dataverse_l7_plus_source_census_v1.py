from __future__ import annotations

from pathlib import Path


def census(root: Path) -> dict[str, int]:
    benchmark_files = tuple((root / "benchmarking/cfbe_omega").glob("kim_dataverse_*")) + tuple((root / "benchmarking/cfbe_omega").glob("KIM_DATAVERSE_LEVEL7_PLUS_*"))
    test_files = tuple((root / "tests").glob("test_kim_dataverse_*"))
    governance_files = tuple((root / "governance").glob("*KIM_DATAVERSE*")) + tuple((root / "governance").glob("proofos_omega_policy_extension_kim_dataverse_*"))
    return {
        "benchmark_files": len({path.name for path in benchmark_files}),
        "test_files": len({path.name for path in test_files}),
        "governance_files": len({path.name for path in governance_files}),
    }
