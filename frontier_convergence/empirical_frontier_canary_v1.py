from __future__ import annotations

"""Thin Bubbles–CFBE Ω hosted canary binding.

The path intentionally lives under ``frontier_convergence`` so the already
admitted Frontier Runtime Qualification workflow re-runs on closure changes.
It creates no runtime of its own and performs no provider effect.
"""

from benchmarking.cfbe_omega.empirical_frontier_closure_v1 import (
    current_snapshot,
    next_executable_lanes,
)


def hosted_canary_projection() -> dict[str, object]:
    closure = current_snapshot()
    return {
        "schema": "BUBBLES_CFBE_OMEGA_EMPIRICAL_HOSTED_CANARY_V1",
        "source_main_sha": closure.source_main_sha,
        "closure_sha256": closure.closure_sha256,
        "lane_count": len(closure.lanes),
        "safe_no_effect_lanes": list(next_executable_lanes(closure)),
        "provider_effect_authorized": False,
        "stable_promotion_authorized": False,
    }
