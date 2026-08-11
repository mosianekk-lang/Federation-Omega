from __future__ import annotations

_NON_PROOF_PREFIXES=(
    "UNBOUND","PENDING","REFERENCE","TEST","MOCK","SYNTHETIC","UNVERIFIED",
    "PLACEHOLDER","TODO","TBD","DRAFT","TEMPLATE","HOLD","UNKNOWN",
)
_NON_PROOF_EXACT={"NONE","N/A","NA","UNKNOWN","NOT_APPLICABLE","NOT APPLICABLE"}

def is_concrete_evidence_ref(ref:str)->bool:
    """Return True only for a non-placeholder evidence/proof reference.

    This is a source-level semantic gate, not proof that the referenced provider or
    private record actually exists. Provider/native readback remains required at the
    boundary where the reference is consumed.
    """
    value=str(ref or "").strip()
    if not value:return False
    upper=value.upper()
    if upper in _NON_PROOF_EXACT:return False
    return not upper.startswith(_NON_PROOF_PREFIXES)
