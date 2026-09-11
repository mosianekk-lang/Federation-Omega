import json
from federation.product_release_factory_v1 import (
    ProductReleaseInput, compile_product_release_bundle, release_gate,
)


def spec(**overrides):
    d = dict(
        product_id="FUSE",
        product_contract_fingerprint="a" * 64,
        version="1.0.0",
        executable_entrypoints=("fuse.exe", "fuse-service"),
        website_routes=("/", "/docs", "/trust"),
        installer_targets=("MSI", "MSIX"),
        feature_flags=("new_ui", "local_ai"),
    )
    d.update(overrides)
    return ProductReleaseInput(**d)


def test_deterministic_bundle_and_complete_component_set():
    a = compile_product_release_bundle(spec())
    b = compile_product_release_bundle(spec())
    assert a == b
    assert len(a.components) == 12
    assert len({c.kind for c in a.components}) == 12


def test_source_factory_never_authorizes_provider_effect():
    b = compile_product_release_bundle(spec())
    assert b.provider_effect_authorized is False
    assert all(c.effect_class == "SOURCE_ONLY" for c in b.components)


def test_installer_requires_full_lifecycle_and_signing():
    b = compile_product_release_bundle(spec())
    installer = next(c for c in b.components if c.kind == "INSTALLER")
    assert set(installer.contract["operations"]) == {"CLEAN_INSTALL", "UPGRADE", "REPAIR", "UNINSTALL", "ROLLBACK"}
    assert installer.contract["signing"] == "REQUIRED_BEFORE_RELEASE"
    assert "SIGNATURE" in installer.proof_required


def test_secure_update_is_threshold_root_with_rollback_protection():
    b = compile_product_release_bundle(spec())
    update = next(c for c in b.components if c.kind == "SECURE_UPDATE_ROOT")
    assert update.contract["model"] == "TUF_STYLE_THRESHOLD_ROOT"
    assert update.contract["rollback_protection"] is True
    assert "ROLLBACK_ATTACK_TEST" in update.proof_required


def test_feature_flags_are_provider_neutral_and_fail_closed():
    b = compile_product_release_bundle(spec())
    f = next(c for c in b.components if c.kind == "FEATURE_FLAGS")
    assert f.contract["contract"] == "OPENFEATURE_COMPATIBLE_PROVIDER_NEUTRAL"
    assert f.contract["default_behavior"] == "FAIL_CLOSED"
    assert f.contract["kill_switch"] is True


def test_promotion_graph_requires_canary_before_production():
    b = compile_product_release_bundle(spec())
    assert ("STAGING", "CANARY") in b.promotion_edges
    assert ("CANARY", "PRODUCTION") in b.promotion_edges
    assert ("STAGING", "PRODUCTION") not in b.promotion_edges


def test_trust_center_forbids_unsupported_claims():
    b = compile_product_release_bundle(spec())
    trust = next(c for c in b.components if c.kind == "TRUST_CENTER")
    assert trust.contract["claims"] == "EVIDENCE_GATED_ONLY"
    assert trust.contract["unsupported_claims"] == "FORBIDDEN"


def test_ai_bom_requires_model_license_and_eval_identity():
    b = compile_product_release_bundle(spec())
    aibom = next(c for c in b.components if c.kind == "AI_BOM")
    assert {"MODEL_PROVIDER", "MODEL_ID", "VERSION", "LICENSE", "EVAL_RECEIPT"}.issubset(set(aibom.contract["fields"]))
    assert aibom.contract["unknowns_fail_closed"] is True


def test_tenant_and_auth_contracts_encode_isolation_and_step_up():
    b = compile_product_release_bundle(spec())
    tenant = next(c for c in b.components if c.kind == "TENANT_CONTROL")
    auth = next(c for c in b.components if c.kind == "AUTH")
    assert tenant.contract["isolation"] == "TENANT_SCOPED_IDENTITY_DATA_CONFIG_LIMITS"
    assert auth.contract["step_up"] == "CONSEQUENTIAL_EFFECTS"
    assert "PASSKEY_CONFORMANCE" in auth.proof_required


def test_release_gate_holds_until_every_terminal_proof_present():
    b = compile_product_release_bundle(spec())
    partial = release_gate(b, ("WEBSITE_DEPLOYED_READBACK",))
    assert partial["status"] == "HOLD"
    assert "INSTALLER_SIGNED" in partial["missing"]
    complete = release_gate(b, b.required_terminal_proofs)
    assert complete["status"] == "RELEASE_READY"
    assert complete["missing"] == ()
    assert complete["provider_effect_authorized"] is False


def test_missing_required_inputs_fail_closed():
    import pytest
    with pytest.raises(ValueError, match="PRF_EXECUTABLE_ENTRYPOINT_REQUIRED"):
        compile_product_release_bundle(spec(executable_entrypoints=()))
    with pytest.raises(ValueError, match="PRF_PRODUCT_CONTRACT_FINGERPRINT_REQUIRED"):
        compile_product_release_bundle(spec(product_contract_fingerprint="bad"))


def test_canonical_json_round_trip_is_stable():
    b = compile_product_release_bundle(spec())
    payload = json.dumps({"id": b.bundle_id, "sha": b.fingerprint_sha256}, sort_keys=True)
    assert json.loads(payload)["sha"] == b.fingerprint_sha256
