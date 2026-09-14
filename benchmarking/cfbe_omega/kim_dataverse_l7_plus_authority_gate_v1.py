from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthorityGate:
    gate_id: str
    explicit_owner_authorization_required: bool
    generic_continue_sufficient: bool
    lane_local: bool


GOOGLE_WIF_GATE = AuthorityGate(
    gate_id="AUTHORIZE_SOVARA_WIF_HARDENING",
    explicit_owner_authorization_required=True,
    generic_continue_sufficient=False,
    lane_local=True,
)
