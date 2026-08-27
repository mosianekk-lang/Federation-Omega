from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Dict, Mapping, Optional

from .design_provenance_fabric import (
    DesignProvenanceBridge,
    RawCaptureManifest,
)


class ObservableCaptureScopeError(ValueError):
    """Observable-scope evidence is malformed or attempts to widen its truth boundary."""


ScopeEvidenceResolver = Callable[[str], Optional[Mapping[str, Any]]]


_ALLOWED_RENDERED_INTEGRITY = frozenset({"HASH_CHAIN_VERIFIED", "PASS_EXACT"})
_ALLOWED_RENDERED_PROVIDERS = frozenset({"CHATGPT_RENDERED_DOM", "CHATGPT_WEB_EDGE", "CHATGPT_WEB"})


def _list_is_empty(value: Any) -> bool:
    return value is None or value == [] or value == ()


def _observable_scope_complete(
    proof: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> bool:
    scope = str(evidence.get("capture_scope", "")).strip().upper()
    if scope != "RENDERED_DOM":
        return False
    provider = str(evidence.get("source_provider", "")).strip().upper()
    if provider not in _ALLOWED_RENDERED_PROVIDERS:
        return False
    if bool(evidence.get("provider_native_complete", False)):
        raise ObservableCaptureScopeError(
            "rendered-DOM evidence cannot self-declare provider-native completeness"
        )
    if not bool(evidence.get("exact_rendered_transcript_complete", False)):
        return False
    if str(evidence.get("integrity_state", "")) not in _ALLOWED_RENDERED_INTEGRITY:
        return False
    if not _list_is_empty(evidence.get("missing_ranges")):
        return False
    if not _list_is_empty(evidence.get("unresolved_artifacts")):
        return False
    if int(evidence.get("first_source_sequence", 0) or 0) != 1:
        return False
    last_source = int(evidence.get("last_source_sequence", 0) or 0)
    latest_rendered = int(evidence.get("latest_rendered_message_count", 0) or 0)
    if last_source < 1 or latest_rendered < 1 or last_source != latest_rendered:
        return False
    evidence_events = int(evidence.get("captured_event_count", 0) or 0)
    proof_events = int(proof.get("event_count", 0) or 0)
    if evidence_events < latest_rendered or proof_events < latest_rendered:
        return False
    if str(proof.get("integrity_state", "")) == "FAIL_HASH_CHAIN":
        return False
    return True


class ObservableCaptureScopeLedger:
    """Read-only DPF view over a stricter ChatBridge ledger.

    The wrapped ledger remains authoritative. This adapter may mark the DPF view complete
    only inside the declared *observable rendered-chat* scope when separately supplied,
    validated scope evidence proves a gap-free hash-valid rendered transcript. It never
    promotes rendered evidence to provider-native completeness.
    """

    def __init__(
        self,
        ledger: Any,
        evidence_resolver: ScopeEvidenceResolver,
    ) -> None:
        self.ledger = ledger
        self.evidence_resolver = evidence_resolver

    def verify(self, conversation_key: str) -> Dict[str, Any]:
        proof = dict(self.ledger.verify(conversation_key))
        provider_native_complete = bool(proof.get("exact_context_complete", False))
        proof["dpf_provider_native_complete"] = provider_native_complete
        proof["dpf_observable_complete"] = provider_native_complete
        proof["dpf_capture_scope"] = (
            "PROVIDER_NATIVE_EXACT" if provider_native_complete else "BOUNDED"
        )

        evidence = self.evidence_resolver(conversation_key)
        if evidence is None or provider_native_complete:
            return proof
        evidence = dict(evidence)
        observable_complete = _observable_scope_complete(proof, evidence)
        proof["dpf_observable_complete"] = observable_complete
        if not observable_complete:
            proof["dpf_capture_scope"] = "BOUNDED_RENDERED_DOM"
            proof["dpf_scope_evidence_fingerprint"] = str(
                evidence.get("evidence_fingerprint", "")
            )
            return proof

        # DPF's generic bridge uses exact_context_complete as its cleanup/reconciliation
        # gate. In this *view only*, exact means exact within the declared observable scope.
        # Provider-native completeness is preserved separately and remains false.
        proof["exact_context_complete"] = True
        proof["start_to_finish_guarantee"] = True
        proof["dpf_capture_scope"] = "FULL_OBSERVABLE_RENDERED_CHAT"
        proof["dpf_scope_evidence_fingerprint"] = str(
            evidence.get("evidence_fingerprint", "")
        )
        proof["dpf_scope_truth_boundary"] = (
            "FULL_OBSERVABLE_RENDERED_CHAT_VERIFIED / "
            "PROVIDER_NATIVE_HIDDEN_EVENTS_NOT_INFERRED"
        )
        return proof

    def reconstruct(self, conversation_key: str, *, require_exact: bool = False) -> Dict[str, Any]:
        # The underlying ledger may remain deliberately bounded because it does not claim
        # hidden provider events. Observable-scope exactness is enforced by verify(), so
        # reconstruction itself remains a pass-through and never rewrites raw provenance.
        return self.ledger.reconstruct(conversation_key, require_exact=False)


class ObservableScopeDesignProvenanceBridge(DesignProvenanceBridge):
    """DPF bridge whose completeness claim is explicitly scoped to observable chat."""

    VERSION = "FEDERATION-DPF-OBSERVABLE-CAPTURE-SCOPE-1.0"

    def build_raw_manifest(self, **kwargs: Any) -> RawCaptureManifest:
        manifest = super().build_raw_manifest(**kwargs)
        proof = self.ledger.verify(manifest.conversation_key)
        scope = str(proof.get("dpf_capture_scope", "BOUNDED"))
        provider_native = bool(proof.get("dpf_provider_native_complete", False))
        observable = bool(proof.get("dpf_observable_complete", False))
        if provider_native:
            boundary = "PROVIDER_NATIVE_EXACT_CAPTURE_VERIFIED"
        elif observable and scope == "FULL_OBSERVABLE_RENDERED_CHAT":
            boundary = (
                "FULL_OBSERVABLE_RENDERED_CHAT_VERIFIED / "
                "PROVIDER_NATIVE_COMPLETE_FALSE / HIDDEN_PROVIDER_EVENTS_NOT_INFERRED"
            )
        else:
            boundary = (
                "CAPTURE_BOUNDED_WITH_EXPLICIT_SCOPE_GAPS / "
                "PROVIDER_NATIVE_COMPLETENESS_NOT_INFERRED"
            )
        return replace(manifest, truth_boundary=boundary)

    @classmethod
    def contract(cls) -> Dict[str, Any]:
        base = dict(super().contract())
        base.update(
            {
                "version": cls.VERSION,
                "completeness_dimensions": [
                    "FULL_OBSERVABLE_RENDERED_CHAT",
                    "PROVIDER_NATIVE_EXACT",
                ],
                "observable_scope_truth": (
                    "A gap-free hash-valid rendered transcript can satisfy DPF whole-chat "
                    "provenance without claiming hidden provider-native events."
                ),
            }
        )
        return base


def bind_observable_design_provenance_fabric(
    chatbridge_runtime: Any,
    *,
    evidence_resolver: ScopeEvidenceResolver,
    manifest_sink: Optional[Callable[[Dict[str, Any]], Any]] = None,
    reconciliation_sink: Optional[Callable[[Dict[str, Any]], Any]] = None,
    cleanup_sink: Optional[Callable[[Dict[str, Any]], Any]] = None,
    design_gene_extractor: Optional[Callable[..., Any]] = None,
) -> ObservableScopeDesignProvenanceBridge:
    ledger = getattr(chatbridge_runtime, "full_fidelity", None)
    if ledger is None:
        raise ValueError("chatbridge_runtime must expose full_fidelity ledger authority")
    scoped_ledger = ObservableCaptureScopeLedger(ledger, evidence_resolver)
    return ObservableScopeDesignProvenanceBridge(
        scoped_ledger,
        manifest_sink=manifest_sink,
        reconciliation_sink=reconciliation_sink,
        cleanup_sink=cleanup_sink,
        design_gene_extractor=design_gene_extractor,
    )


__all__ = [
    "ObservableCaptureScopeError",
    "ObservableCaptureScopeLedger",
    "ObservableScopeDesignProvenanceBridge",
    "ScopeEvidenceResolver",
    "bind_observable_design_provenance_fabric",
]
