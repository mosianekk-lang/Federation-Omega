from __future__ import annotations
import math
from collections.abc import Iterable


def robust_anomaly_score(values: Iterable[float], baseline_mean: float = 0.2, baseline_scale: float = 0.15) -> float:
    """Bounded anomaly proxy for metadata-only defensive features.

    This is intentionally deterministic for the reference build. A production TCN/GNN/encoder can
    replace it after passing the same certification gates.
    """
    xs = [max(0.0, min(1.0, float(v))) for v in values]
    if not xs:
        return 0.0
    x = sum(xs) / len(xs)
    z = max(0.0, (x - baseline_mean) / max(baseline_scale, 1e-6))
    return max(0.0, min(1.0, 1.0 - math.exp(-z)))
