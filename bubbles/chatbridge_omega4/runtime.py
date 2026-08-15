from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import GovernanceCapsule, ProviderContinuationRef
from .operating_profile import OperatingProfile
from .restore_assurance import RestoreAssuranceEngine, RestoreAttestation
from .store import ChatBridgeStore


class ChatBridgeOmega4:
    """Governed durable conversation OS kernel.

    The core owns durable routing, lineage, governance and restore semantics. Provider
    adapters bind one continuation strategy to `ProviderContinuationRef` without changing
    the namespace contract. Ω4.4 binds a portable OperatingProfile; Ω4.5 adds a
    destination restore attestation and independent drift/repair contract; Ω4.6 makes
    pre-owner assurance and audit-before-architecture part of the restored behaviour.
    """

    VERSION = "CHATBRIDGE-Ω4.6-PRE-OWNER-ASSURANCE"
    GCP_VERSION = "GCP-Ω3.3"
    OPERATING_PROFILE_KEY = "__chatbridge_operating_profile__"

    def __init__(self, store: ChatBridgeStore) -> None:
        self.store = store

    def _pack_hot_state(
        self,
        hot_state: Dict[str, Any],
        operating_profile: Optional[OperatingProfile],
    ) -> Dict[str, Any]:
        packed = dict(hot_state)
        profile = operating_profile or OperatingProfile.default()
        packed[self.OPERATING_PROFILE_KEY] = profile.to_dict()
        return packed

    def backup(
        self,
        namespace: str,
        capsule: GovernanceCapsule,
        *,
        hot_state: Dict[str, Any],
        warm_pointers: Optional[List[str]] = None,
        cold_pointers: Optional[List[str]] = None,
        provider_ref: ProviderContinuationRef = ProviderContinuationRef(),
        operating_profile: Optional[OperatingProfile] = None,
    ) -> Dict[str, Any]:
        profile = operating_profile or OperatingProfile.default()
        result = self.store.backup(
            namespace,
            capsule,
            hot_state=self._pack_hot_state(hot_state, profile),
            warm_pointers=list(warm_pointers or []),
            cold_pointers=list(cold_pointers or []),
            provider_ref=provider_ref,
        )
        return {
            **result,
            "state": "NAMESPACE_BACKUP_VERIFIED_LOCAL",
            "chatbridge_version": self.VERSION,
            "gcp_version": self.GCP_VERSION,
            "operating_profile": profile.to_dict(),
        }

    def refresh(
        self,
        namespace: str,
        capsule: GovernanceCapsule,
        *,
        hot_state: Dict[str, Any],
        warm_pointers: Optional[List[str]] = None,
        cold_pointers: Optional[List[str]] = None,
        provider_ref: ProviderContinuationRef = ProviderContinuationRef(),
        operating_profile: Optional[OperatingProfile] = None,
    ) -> Dict[str, Any]:
        return self.backup(
            namespace,
            capsule,
            hot_state=hot_state,
            warm_pointers=warm_pointers,
            cold_pointers=cold_pointers,
            provider_ref=provider_ref,
            operating_profile=operating_profile,
        )

    def restore(
        self,
        namespace: str,
        *,
        destination_session_key: str,
        generation_number: Optional[int] = None,
        material_delta: bool = False,
        governance_degraded: bool = False,
    ) -> Dict[str, Any]:
        envelope = self.store.restore(
            namespace,
            destination_session_key=destination_session_key,
            generation_number=generation_number,
            material_delta=material_delta,
            governance_degraded=governance_degraded,
        )
        payload = envelope.to_dict()
        hot = dict(payload["hot_state"])
        raw_profile = hot.pop(self.OPERATING_PROFILE_KEY, None)
        if isinstance(raw_profile, dict):
            profile = OperatingProfile.from_dict(raw_profile)
            profile_source = "CHECKPOINT_BOUND"
        else:
            profile = OperatingProfile.default()
            profile_source = "LEGACY_DEFAULT_SYNTHESIZED"
        payload["hot_state"] = hot
        payload["operating_profile"] = profile.to_dict()
        payload["operating_profile_source"] = profile_source
        payload["restore_directives"] = {
            "execution_posture": profile.execution_posture,
            "reconcile_not_rebuild": profile.reconcile_not_rebuild,
            "creator_mode": profile.creator_mode,
            "federation_route_scan": profile.federation_route_scan,
            "realityguard_assurance": profile.realityguard_assurance,
            "pre_owner_assurance": profile.pre_owner_assurance,
            "assurance_policy": profile.assurance_policy,
            "major_change_discovery_policy": profile.major_change_discovery_policy,
            "assurance_receipt_policy": profile.assurance_receipt_policy,
            "owner_interrupt_policy": profile.owner_interrupt_policy,
            "capture_policy": profile.capture_policy,
            "restore_policy": profile.restore_policy,
            "anticipatory_policy": profile.anticipatory_policy,
        }
        payload["restore_state"] = (
            "RESTORE_PREVIEW_REQUIRED"
            if envelope.preview_required
            else "NAMESPACE_RESTORE_VERIFIED_LOCAL"
        )
        payload["consequential_action_locked"] = (
            envelope.governance.consequentially_locked()
            or governance_degraded
            or envelope.preview_required
        )
        payload["chatbridge_version"] = self.VERSION
        payload["gcp_version"] = self.GCP_VERSION
        payload["restore_assurance_required"] = True
        payload["pre_owner_assurance_required"] = profile.pre_owner_assurance
        payload["restore_attestation_contract"] = RestoreAssuranceEngine.contract(payload)
        return payload

    def assess_restore_attestation(
        self,
        expected_restore: Dict[str, Any],
        observed: RestoreAttestation,
    ) -> Dict[str, Any]:
        """Independent conformance check for a destination restore observation."""
        return RestoreAssuranceEngine.assess(expected_restore, observed)

    def list(self, *, include_released: bool = False) -> List[Dict[str, Any]]:
        return self.store.list_namespaces(include_released=include_released)

    def status(self, namespace: str) -> Dict[str, Any]:
        return self.store.status(namespace)

    def history(self, namespace: str) -> List[Dict[str, Any]]:
        return self.store.history(namespace)

    def rename(self, source: str, target: str) -> Dict[str, Any]:
        return self.store.rename(source, target)

    def release(self, namespace: str) -> Dict[str, Any]:
        return self.store.release(namespace)

    def clone(self, source: str, target: str) -> Dict[str, Any]:
        """Clone governed state while resetting the active provider continuation.

        The provider-neutral store preserves the exact source checkpoint as branch
        ancestry. The public Ω4 runtime then advances the branch to an independent active
        generation with no provider continuation identity. This prevents two live
        branches from silently sharing one OpenAI conversation/session lineage. The
        operating profile remains part of HOT state and therefore follows the governed
        branch unless a later refresh deliberately changes it.
        """
        source_status = self.store.status(source)
        initial = self.store.clone(source, target)
        branch = self.store.restore(
            target,
            destination_session_key=f"clone-normalize:{initial['generation_id']}",
        )
        if branch.provider_ref != ProviderContinuationRef():
            result = self.store.backup(
                target,
                branch.governance,
                hot_state=branch.hot_state,
                warm_pointers=branch.warm_pointers,
                cold_pointers=branch.cold_pointers,
                provider_ref=ProviderContinuationRef(),
                branch_origin_namespace_id=source_status["namespace_id"],
                branch_origin_generation_id=source_status["active_generation_id"],
            )
            provider_binding_reset = True
        else:
            result = initial
            provider_binding_reset = False
        return {
            **result,
            "state": "BRANCH_CREATED_VERIFIED_LOCAL",
            "source_namespace": source,
            "target_namespace": target,
            "provider_binding_reset": provider_binding_reset,
        }
