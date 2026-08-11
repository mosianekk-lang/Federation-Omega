from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping,Protocol,runtime_checkable
from .evidence_ref import is_concrete_evidence_ref
from .receipt_auth import AuthenticatedReceipt,ReceiptEnvelope

@dataclass(frozen=True)
class ProviderCapabilities:
    provider_id:str
    south_africa_supported:bool
    one_to_one_identity_verification:bool
    live_presence_check:bool
    trusted_reference_check:bool
    document_verification:bool
    signed_receipts:bool
    raw_biometric_media_required_by_evidenceops:bool
    production_evidence_ref:str=""

@runtime_checkable
class IdentityProviderAdapter(Protocol):
    """Provider-specific trust adapter.

    The adapter authenticates provider-native receipts/webhooks and normalises only
    minimum result fields. It does not expose raw face images/templates to the
    EvidenceOps domain layer.
    """
    @property
    def capabilities(self)->ProviderCapabilities: ...
    def authenticate(self,envelope:ReceiptEnvelope)->AuthenticatedReceipt: ...
    def health(self)->Mapping[str,object]: ...

class ProviderNotProductionQualified(RuntimeError):pass

def require_production_provider(adapter:IdentityProviderAdapter)->None:
    c=adapter.capabilities
    required=(c.south_africa_supported,c.one_to_one_identity_verification,c.live_presence_check,c.signed_receipts)
    if not all(required):raise ProviderNotProductionQualified("IDENTITY_PROVIDER_CAPABILITY_GATE_FAILED")
    if c.raw_biometric_media_required_by_evidenceops:raise ProviderNotProductionQualified("RAW_BIOMETRIC_MEDIA_BOUNDARY_FAILED")
    if not is_concrete_evidence_ref(c.production_evidence_ref):raise ProviderNotProductionQualified("PROVIDER_NATIVE_PRODUCTION_EVIDENCE_MISSING")
