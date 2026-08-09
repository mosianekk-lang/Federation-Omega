from __future__ import annotations

from dataclasses import dataclass


MATURITY_ORDER = (
    "DESIGN_ONLY",
    "DETERMINISTIC_TESTED",
    "SHADOW_VALIDATED",
    "CANARY_VALIDATED",
    "WORKFLOW_VERIFIED",
    "OPERATIONAL_VERIFIED",
)


@dataclass(frozen=True)
class PromotionReceipt:
    capability_id: str
    from_state: str
    to_state: str
    deterministic_tests: bool
    rollback_proven: bool
    target_readback: bool
    health_check: bool
    persistence_check: bool
    provider_receipt: bool = False


class PromotionGovernor:
    def validate(self, receipt: PromotionReceipt) -> tuple[bool, tuple[str, ...]]:
        failures: list[str] = []
        if receipt.from_state not in MATURITY_ORDER or receipt.to_state not in MATURITY_ORDER:
            failures.append("UNKNOWN_MATURITY_STATE")
            return False, tuple(failures)
        if MATURITY_ORDER.index(receipt.to_state) != MATURITY_ORDER.index(receipt.from_state) + 1:
            failures.append("STATE_JUMP_NOT_ALLOWED")
        if not receipt.deterministic_tests:
            failures.append("DETERMINISTIC_TESTS_MISSING")
        if receipt.to_state in {"CANARY_VALIDATED", "WORKFLOW_VERIFIED", "OPERATIONAL_VERIFIED"}:
            if not receipt.rollback_proven:
                failures.append("ROLLBACK_PROOF_MISSING")
            if not receipt.target_readback:
                failures.append("TARGET_READBACK_MISSING")
        if receipt.to_state in {"WORKFLOW_VERIFIED", "OPERATIONAL_VERIFIED"}:
            if not receipt.health_check:
                failures.append("HEALTH_CHECK_MISSING")
            if not receipt.persistence_check:
                failures.append("PERSISTENCE_CHECK_MISSING")
        if receipt.to_state == "OPERATIONAL_VERIFIED" and not receipt.provider_receipt:
            failures.append("PROVIDER_RECEIPT_MISSING")
        return not failures, tuple(failures)
