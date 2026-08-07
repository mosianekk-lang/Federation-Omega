from __future__ import annotations

from .models import ActionDecision, ActionDisposition, ActionRequest, AuthorityLevel, Domain, InformationClass


class AuthorityGuard:
    """Fail-closed authority firewall for the Capital Intelligence OS."""

    HARD_DENY = {
        "LIVE_ORDER", "WITHDRAWAL", "TRANSFER", "AUTONOMOUS_FINANCIAL_EFFECT",
        "DELETE_EVIDENCE", "ERASE_AUDIT_LOG", "DISABLE_INFORMATION_BARRIER",
    }
    HUMAN_GATE = {
        "SIGN_TRANSACTION", "ACCEPT_CONTRACT", "MAKE_PAYMENT", "REGULATORY_FILING",
        "EXTERNAL_COMMUNICATION", "FINAL_ACQUISITION_RECOMMENDATION",
        "FINAL_VALUATION_APPROVAL", "CLOSING_AUTHORISATION",
    }
    PRIVATE_CLASSES = {
        InformationClass.CONFIDENTIAL, InformationClass.CLEAN_TEAM,
        InformationClass.POTENTIALLY_MNPI, InformationClass.RESTRICTED,
        InformationClass.PRIVILEGED, InformationClass.UNKNOWN,
    }

    def evaluate(self, request: ActionRequest) -> ActionDecision:
        action = request.action_type.upper().strip()
        if action in self.HARD_DENY:
            return ActionDecision(ActionDisposition.DENY, ("CONSTITUTIONAL_HARD_DENY",), AuthorityLevel.A5_SOVEREIGN_AUTHORITY)
        if (
            request.target_domain == Domain.PUBLIC_MARKETS
            and request.source_domain != Domain.PUBLIC_MARKETS
            and request.information_class in self.PRIVATE_CLASSES
        ):
            return ActionDecision(
                ActionDisposition.DENY,
                ("PRIVATE_TO_TRADING_FIREWALL", "MNPI_FAIL_CLOSED"),
                AuthorityLevel.A5_SOVEREIGN_AUTHORITY,
            )
        if request.target_domain == Domain.PUBLIC_MARKETS and request.information_class == InformationClass.UNKNOWN:
            return ActionDecision(ActionDisposition.DENY, ("UNKNOWN_CLASSIFICATION_FAIL_CLOSED",), AuthorityLevel.A5_SOVEREIGN_AUTHORITY)
        if (
            action in self.HUMAN_GATE or request.external_effect or request.financial_effect
            or request.destructive or not request.reversible
        ):
            return ActionDecision(
                ActionDisposition.REQUIRE_HUMAN,
                ("CONSEQUENTIAL_EFFECT", "OWNER_RESERVED_AUTHORITY"),
                AuthorityLevel.A2_PREPARED,
            )
        if request.requested_authority in {
            AuthorityLevel.A3_SUPERVISED_AUTOMATION,
            AuthorityLevel.A4_BOUNDED_AUTONOMY,
            AuthorityLevel.A5_SOVEREIGN_AUTHORITY,
        }:
            return ActionDecision(ActionDisposition.REQUIRE_HUMAN, ("CURRENT_RELEASE_A1_CEILING",), AuthorityLevel.A2_PREPARED)
        return ActionDecision(
            ActionDisposition.ALLOW_LOGGED if request.requested_authority == AuthorityLevel.A1_ASSISTED else ActionDisposition.ALLOW_INTERNAL,
            ("A0_A1_INTERNAL_SAFE",),
            AuthorityLevel.A1_ASSISTED,
        )
