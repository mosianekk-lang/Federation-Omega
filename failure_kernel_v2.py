from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class FailureDecision:
    next_step: str
    reasons: tuple[str, ...]
    failed_kernel_quarantined: bool
    fallback_used: bool
    external_effect: bool = False


class FallbackParent:
    """Minimal parent containment contract for active-kernel failure.

    This primitive never creates provider effects or authority. It isolates a
    failed active kernel and allows continuity only through an already healthy
    fallback; otherwise it holds the failed lane closed.
    """

    def on_failure(self, failure: Mapping[str, Any]) -> FailureDecision:
        active_failed = bool(failure.get("active_kernel_failed", False))
        healthy_fallback = bool(failure.get("healthy_fallback_available", False))
        failure_class = str(failure.get("failure_class", "UNKNOWN") or "UNKNOWN")

        if not active_failed:
            return FailureDecision(
                next_step="KEEP_ACTIVE_KERNEL",
                reasons=("ACTIVE_KERNEL_FAILURE_NOT_ESTABLISHED", f"FAILURE_CLASS:{failure_class}"),
                failed_kernel_quarantined=False,
                fallback_used=False,
            )
        if healthy_fallback:
            return FailureDecision(
                next_step="CONTINUE_WITH_HEALTHY_FALLBACK",
                reasons=("ACTIVE_KERNEL_FAILED", "HEALTHY_FALLBACK_AVAILABLE"),
                failed_kernel_quarantined=True,
                fallback_used=True,
            )
        return FailureDecision(
            next_step="BLOCK_AND_HOLD_FAILED_KERNEL",
            reasons=("ACTIVE_KERNEL_FAILED", "NO_HEALTHY_FALLBACK_PROVEN"),
            failed_kernel_quarantined=True,
            fallback_used=False,
        )


__all__ = ["FailureDecision", "FallbackParent"]
