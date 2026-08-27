from __future__ import annotations

from dataclasses import dataclass, asdict

from .models import MarketSnapshot, ShadowFill, ShadowOrderRequest, stable_sha256


@dataclass(frozen=True)
class ReconciliationReceipt:
    status: str
    request_fingerprint: str
    snapshot_fingerprint: str
    fill_fingerprint: str
    reason_codes: tuple[str, ...]
    receipt_digest: str
    provider_effect_verified: bool = False
    financial_effect: bool = False


class ShadowReconciler:
    """Independent deterministic reconciliation for shadow execution evidence."""

    def reconcile(
        self,
        *,
        request: ShadowOrderRequest,
        snapshot: MarketSnapshot,
        fill: ShadowFill,
    ) -> ReconciliationReceipt:
        request_fp = request.fingerprint()
        snapshot_fp = snapshot.fingerprint()
        fill_fp = fill.fingerprint()
        reasons: list[str] = []

        if fill.request_fingerprint != request_fp:
            reasons.append("REQUEST_BINDING_MISMATCH")
        if fill.snapshot_fingerprint != snapshot_fp:
            reasons.append("SNAPSHOT_BINDING_MISMATCH")
        if fill.filled_base_volume + fill.unfilled_base_volume != request.base_volume:
            reasons.append("VOLUME_CONSERVATION_FAILURE")
        if fill.status == "FILLED" and fill.unfilled_base_volume != 0:
            reasons.append("FILLED_STATE_HAS_REMAINDER")
        if fill.status == "REJECTED" and not fill.reason_codes:
            reasons.append("REJECTION_WITHOUT_CAUSE")
        if fill.external_effect or fill.financial_effect:
            reasons.append("SHADOW_EFFECT_BOUNDARY_VIOLATION")

        status = "MATCH" if not reasons else "MISMATCH"
        payload = {
            "status": status,
            "request_fingerprint": request_fp,
            "snapshot_fingerprint": snapshot_fp,
            "fill_fingerprint": fill_fp,
            "reason_codes": tuple(reasons),
            "provider_effect_verified": False,
            "financial_effect": False,
        }
        return ReconciliationReceipt(
            status=status,
            request_fingerprint=request_fp,
            snapshot_fingerprint=snapshot_fp,
            fill_fingerprint=fill_fp,
            reason_codes=tuple(reasons),
            receipt_digest=stable_sha256(payload),
        )
