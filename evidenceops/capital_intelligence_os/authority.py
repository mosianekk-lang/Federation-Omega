from __future__ import annotations

from .models import ActionDecision, ActionDisposition, ActionRequest, AuthorityLevel, Domain, InformationClass


class AuthorityGuard:
    """Fail-closed authority firewall for the Capital Intelligence OS."""

    def __init__(self, restriction_lookup=None, tenant_id: str | None = None) -> None:
        self.restriction_lookup = restriction_lookup
        self.tenant_id = tenant_id

    HARD_DENY = {
        "LIVE_ORDER", "WITHDRAWAL", "TRANSFER", "AUTONOMOUS_FINANCIAL_EFFECT",
        "DELETE_EVIDENCE", "ERASE_AUDIT_LOG", "DISABLE_INFORMATION_BARRIER",
        "PLACE_ORDER", "EXECUTE_ORDER", "EXECUTE_TRADE", "BUY_SECURITY",
        "SELL_SECURITY", "SUBMIT_TRADE", "INITIATE_TRANSFER",
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
        if request.target_domain == Domain.PUBLIC_MARKETS and self.restriction_lookup is not None and self.tenant_id:
            issuer_id = request.context.get("issuer_id")
            security_id = request.context.get("security_id")
            if self.restriction_lookup.is_restricted(self.tenant_id, issuer_id=issuer_id, security_id=security_id):
                return ActionDecision(ActionDisposition.DENY, ("RESTRICTED_LIST_MATCH", "MARKET_ACTION_QUARANTINED"), AuthorityLevel.A5_SOVEREIGN_AUTHORITY)
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
