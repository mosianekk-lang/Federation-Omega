from __future__ import annotations
from .provider_canary import ProviderCanarySpec
from .verify_rc2 import verify as verify_rc2

def verify() -> dict[str, object]:
    rc2=verify_rc2(); memory_rejected=False; mismatch_rejected=False
    try: ProviderCanarySpec("a"*40,"a"*40,"runtime","tenant",":memory:").validate()
    except ValueError: memory_rejected=True
    try: ProviderCanarySpec("a"*40,"b"*40,"runtime","tenant","/tmp/cios-canary.db").validate()
    except ValueError: mismatch_rejected=True
    checks={"rc2_regression":bool(rc2.get("passed")),"provider_canary_requires_persistent_storage":memory_rejected,"provider_canary_requires_exact_source_identity":mismatch_rejected,"production_still_requires_provider_native_proof":rc2.get("maturity")=="PROVIDER_QUALIFICATION_REQUIRED"}
    return {"passed":all(checks.values()),"release":"1.0.0-rc3","maturity":"PROVIDER_CANARY_READY","checks":checks}
