from __future__ import annotations

"""Provider-neutral authority planning for Bubbles Ω.

This module does not mint provider authority. It compiles MissionIR requirements
against explicitly supplied, proof-bound grants and produces short-lived
capability-lease decisions. A provider credential reference is metadata only;
secret values are never accepted or stored here.

The owning effect boundary remains Secure Capability Box (or another injected
authority backend) when a real provider action is executed.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Iterable, Protocol, Sequence

from federation.mission_ir import MissionIR

SCHEMA = "BUBBLES-OMEGA-PROVIDER-AUTHORITY-FABRIC-V1"
_AUTHORITY_ORDER = {"A0": 0, "A1": 1, "A2": 2, "A3": 3}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(item).strip() for item in values if str(item).strip()}))


class AuthorityState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    RESOLVED = "RESOLVED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    PROVIDER_GATED = "PROVIDER_GATED"
    CREDENTIAL_GATED = "CREDENTIAL_GATED"
    DENIED = "DENIED"


@dataclass(frozen=True, slots=True)
class CapabilityAuthorityContract:
    capability_id: str
    provider: str
    connector: str
    action: str
    minimum_authority: str
    effect_class: str
    credential_reference: str = ""
    resource_ref: str = ""
    proof_requirements: tuple[str, ...] = ()
    rollback_required: bool = True
    max_cost_microunits: int | None = None

    def validate(self) -> "CapabilityAuthorityContract":
        for name in ("capability_id", "provider", "connector", "action", "minimum_authority", "effect_class"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"AUTHORITY_CONTRACT_REQUIRED:{name}")
        authority = self.minimum_authority.upper()
        if authority not in _AUTHORITY_ORDER:
            raise ValueError("AUTHORITY_CONTRACT_CLASS_INVALID")
        effect = self.effect_class.upper()
        if effect not in {"NO_EFFECT", "READ_ONLY", "BOUNDED_EFFECT", "CONSEQUENTIAL_EFFECT"}:
            raise ValueError("AUTHORITY_CONTRACT_EFFECT_INVALID")
        if self.max_cost_microunits is not None and self.max_cost_microunits < 0:
            raise ValueError("AUTHORITY_CONTRACT_COST_INVALID")
        if effect not in {"NO_EFFECT", "READ_ONLY"} and not self.rollback_required and effect != "CONSEQUENTIAL_EFFECT":
            raise ValueError("AUTHORITY_CONTRACT_EFFECT_REQUIRES_ROLLBACK")
        return self

    def canonical_mapping(self) -> dict[str, Any]:
        self.validate()
        payload = asdict(self)
        payload["minimum_authority"] = self.minimum_authority.upper()
        payload["effect_class"] = self.effect_class.upper()
        payload["proof_requirements"] = list(_clean(self.proof_requirements))
        payload["credential_reference"] = str(self.credential_reference).strip()
        payload["resource_ref"] = str(self.resource_ref).strip()
        payload["secret_value_present"] = False
        return payload

    @property
    def digest(self) -> str:
        return _digest(self.canonical_mapping())


@dataclass(frozen=True, slots=True)
class AuthorityGrant:
    grant_id: str
    capability_id: str
    provider: str
    connector: str
    action: str
    authority_class: str
    credential_reference: str
    mission_id: str
    expires_at_epoch: float
    provider_native: bool
    semantic_readback_route: str
    proof_refs: tuple[str, ...] = ()
    cost_ceiling_microunits: int | None = None
    owner_approval_ref: str = ""

    def validate(self) -> "AuthorityGrant":
        required = (
            self.grant_id, self.capability_id, self.provider, self.connector,
            self.action, self.authority_class, self.mission_id,
        )
        if not all(str(item).strip() for item in required):
            raise ValueError("AUTHORITY_GRANT_REQUIRED_FIELD_MISSING")
        if self.authority_class.upper() not in _AUTHORITY_ORDER:
            raise ValueError("AUTHORITY_GRANT_CLASS_INVALID")
        if self.expires_at_epoch <= 0:
            raise ValueError("AUTHORITY_GRANT_EXPIRY_INVALID")
        if self.cost_ceiling_microunits is not None and self.cost_ceiling_microunits < 0:
            raise ValueError("AUTHORITY_GRANT_COST_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class AuthorityLeaseDecision:
    schema: str
    mission_id: str
    capability_id: str
    contract_sha256: str
    state: str
    grant_id: str = ""
    provider: str = ""
    connector: str = ""
    action: str = ""
    credential_reference: str = ""
    semantic_readback_route: str = ""
    proof_refs: tuple[str, ...] = ()
    reason: str = ""
    expires_at_epoch: float | None = None
    provider_effect_authorized: bool = False
    secret_value_recorded: bool = False
    resource_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["proof_refs"] = list(self.proof_refs)
        return payload


class AuthorityGrantSource(Protocol):
    def grants_for(self, mission_id: str, capability_id: str) -> Sequence[AuthorityGrant]:
        ...


class ProviderAuthorityFabric:
    """Resolve exact mission authority from supplied/provider-backed grant metadata.

    This class is deliberately not an authority issuer. A real grant source can
    be backed by Secure Capability Box, provider IAM, OAuth, or another trusted
    system. Only proof-bound metadata crosses into this fabric.
    """

    def __init__(self, grant_source: AuthorityGrantSource | None = None) -> None:
        self.grant_source = grant_source

    @staticmethod
    def _mission_allows_provider(mission: MissionIR, provider: str) -> bool:
        item = mission.normalized(); provider = provider.strip()
        if provider in item.provider_denylist:
            return False
        if item.provider_allowlist and provider not in item.provider_allowlist:
            return False
        return True

    @staticmethod
    def _authority_sufficient(required: str, actual: str) -> bool:
        return _AUTHORITY_ORDER[actual.upper()] >= _AUTHORITY_ORDER[required.upper()]

    @staticmethod
    def _decision(contract: CapabilityAuthorityContract, **kwargs) -> AuthorityLeaseDecision:
        kwargs.setdefault("resource_ref", contract.resource_ref)
        return AuthorityLeaseDecision(**kwargs)

    def resolve(
        self,
        mission: MissionIR,
        contract: CapabilityAuthorityContract,
        *,
        now_epoch: float,
        grants: Sequence[AuthorityGrant] = (),
    ) -> AuthorityLeaseDecision:
        mission = mission.normalized(); mission.validate(); contract.validate()

        if contract.effect_class.upper() != mission.effect_class:
            return self._decision(contract,
                schema=SCHEMA, mission_id=mission.mission_id, capability_id=contract.capability_id,
                contract_sha256=contract.digest, state=AuthorityState.DENIED.value,
                provider=contract.provider, connector=contract.connector, action=contract.action,
                reason="MISSION_EFFECT_CLASS_MISMATCH",
            )

        if not self._mission_allows_provider(mission, contract.provider):
            return self._decision(contract,
                schema=SCHEMA, mission_id=mission.mission_id, capability_id=contract.capability_id,
                contract_sha256=contract.digest, state=AuthorityState.DENIED.value,
                provider=contract.provider, connector=contract.connector, action=contract.action,
                reason="MISSION_PROVIDER_POLICY_REJECTED",
            )

        if mission.max_cost_microunits is not None and contract.max_cost_microunits is not None:
            if contract.max_cost_microunits > mission.max_cost_microunits:
                return self._decision(contract,
                    schema=SCHEMA, mission_id=mission.mission_id, capability_id=contract.capability_id,
                    contract_sha256=contract.digest, state=AuthorityState.DENIED.value,
                    provider=contract.provider, connector=contract.connector, action=contract.action,
                    reason="MISSION_COST_CEILING_EXCEEDED",
                )

        if mission.effect_class in {"NO_EFFECT", "READ_ONLY"} and not mission.authority_requirements:
            return self._decision(contract,
                schema=SCHEMA, mission_id=mission.mission_id, capability_id=contract.capability_id,
                contract_sha256=contract.digest, state=AuthorityState.NOT_REQUIRED.value,
                provider=contract.provider, connector=contract.connector, action=contract.action,
                semantic_readback_route=contract.resource_ref,
                reason="MISSION_DOES_NOT_REQUIRE_EFFECT_AUTHORITY",
            )

        candidate_grants = list(grants)
        if self.grant_source is not None:
            candidate_grants.extend(self.grant_source.grants_for(mission.mission_id, contract.capability_id))

        candidates: list[AuthorityGrant] = []
        for grant in candidate_grants:
            grant.validate()
            exact = (
                grant.mission_id == mission.mission_id
                and grant.capability_id == contract.capability_id
                and grant.provider == contract.provider
                and grant.connector == contract.connector
                and grant.action == contract.action
                and grant.expires_at_epoch > now_epoch
                and self._authority_sufficient(contract.minimum_authority, grant.authority_class)
            )
            if not exact:
                continue
            if contract.credential_reference and grant.credential_reference != contract.credential_reference:
                continue
            if not grant.provider_native or not grant.semantic_readback_route:
                continue
            if contract.max_cost_microunits is not None and grant.cost_ceiling_microunits is not None:
                if contract.max_cost_microunits > grant.cost_ceiling_microunits:
                    continue
            candidates.append(grant)

        if not candidates:
            state = AuthorityState.APPROVAL_REQUIRED if mission.owner_approval_required or mission.effect_class == "CONSEQUENTIAL_EFFECT" else AuthorityState.PROVIDER_GATED
            return self._decision(contract,
                schema=SCHEMA, mission_id=mission.mission_id, capability_id=contract.capability_id,
                contract_sha256=contract.digest, state=state.value,
                provider=contract.provider, connector=contract.connector, action=contract.action,
                credential_reference=contract.credential_reference,
                reason="NO_EXACT_FRESH_PROVIDER_NATIVE_GRANT",
            )

        chosen = max(candidates, key=lambda item: (item.expires_at_epoch, item.grant_id))
        if mission.owner_approval_required and not chosen.owner_approval_ref:
            return self._decision(contract,
                schema=SCHEMA, mission_id=mission.mission_id, capability_id=contract.capability_id,
                contract_sha256=contract.digest, state=AuthorityState.APPROVAL_REQUIRED.value,
                provider=contract.provider, connector=contract.connector, action=contract.action,
                credential_reference=chosen.credential_reference,
                semantic_readback_route=chosen.semantic_readback_route,
                proof_refs=_clean(chosen.proof_refs), reason="MISSION_OWNER_APPROVAL_REQUIRED",
                expires_at_epoch=chosen.expires_at_epoch,
            )

        return self._decision(contract,
            schema=SCHEMA, mission_id=mission.mission_id, capability_id=contract.capability_id,
            contract_sha256=contract.digest, state=AuthorityState.RESOLVED.value,
            grant_id=chosen.grant_id, provider=chosen.provider, connector=chosen.connector,
            action=chosen.action, credential_reference=chosen.credential_reference,
            semantic_readback_route=chosen.semantic_readback_route, proof_refs=_clean(chosen.proof_refs),
            reason="EXACT_FRESH_PROVIDER_NATIVE_GRANT_RESOLVED",
            expires_at_epoch=chosen.expires_at_epoch,
            provider_effect_authorized=mission.effect_class == "BOUNDED_EFFECT",
            secret_value_recorded=False,
        )


__all__ = [
    "AuthorityGrant", "AuthorityGrantSource", "AuthorityLeaseDecision", "AuthorityState",
    "CapabilityAuthorityContract", "ProviderAuthorityFabric",
]
