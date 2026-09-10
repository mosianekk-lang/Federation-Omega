from __future__ import annotations
from ..schemas import CertificationResult
_RESULTS: list[CertificationResult] = []

def record(result: CertificationResult) -> None:
    _RESULTS.append(result)

def all_results() -> list[CertificationResult]:
    return list(_RESULTS)
