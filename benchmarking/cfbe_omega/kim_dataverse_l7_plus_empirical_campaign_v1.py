from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmpiricalCampaign:
    campaign_id: str
    maintenance_target: int
    recovery_target: int
    no_chat_resume_target: int
    owner_value_pair_target: int
    provider_native_target: int
    synthetic_allowed: bool = False
    shadow_counts_as_owner_value: bool = False


LEVEL7_CAMPAIGN = EmpiricalCampaign(
    "KIM-DATAVERSE-L7-EMPIRICAL-V1",
    maintenance_target=10,
    recovery_target=10,
    no_chat_resume_target=3,
    owner_value_pair_target=30,
    provider_native_target=1,
)
