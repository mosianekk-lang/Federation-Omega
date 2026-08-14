from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import GovernanceCapsule, ProviderContinuationRef
from .store import ChatBridgeStore


class ChatBridgeOmega4:
    """Governed durable conversation OS kernel.

    This class intentionally does not call the OpenAI API. It is the durable routing,
    lineage, governance and restore layer. Provider adapters can bind one continuation
    strategy to the `ProviderContinuationRef` without changing namespace semantics.
    """

    VERSION = "CHATBRIDGE-Ω4.0-SOURCE-CANDIDATE"
    GCP_VERSION = "GCP-Ω3.0-SOURCE-CANDIDATE"

    def __init__(self, store: ChatBridgeStore) -> None:
        self.store = store

    def backup(
        self,
        namespace: str,
        capsule: GovernanceCapsule,
        *,
        hot_state: Dict[str, Any],
        warm_pointers: Optional[List[str]] = None,
        cold_pointers: Optional[List[str]] = None,
        provider_ref: ProviderContinuationRef = ProviderContinuationRef(),
    ) -> Dict[str, Any]:
        result = self.store.backup(
            namespace,
            capsule,
            hot_state=hot_state,
            warm_pointers=list(warm_pointers or []),
            cold_pointers=list(cold_pointers or []),
            provider_ref=provider_ref,
        )
        return {
            **result,
            "state": "NAMESPACE_BACKUP_VERIFIED_LOCAL",
            "chatbridge_version": self.VERSION,
            "gcp_version": self.GCP_VERSION,
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
    ) -> Dict[str, Any]:
        return self.backup(
            namespace,
            capsule,
            hot_state=hot_state,
            warm_pointers=warm_pointers,
            cold_pointers=cold_pointers,
            provider_ref=provider_ref,
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
        return payload

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
        result = self.store.clone(source, target)
        return {
            **result,
            "state": "BRANCH_CREATED_VERIFIED_LOCAL",
            "source_namespace": source,
            "target_namespace": target,
        }
