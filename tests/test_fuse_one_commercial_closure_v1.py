import pytest

from benchmarking.cfbe_omega.production_genesis_v1 import (
    MaturityStage,
    ProofKey,
)
from federation.fuse_one_commercial_closure_v1 import (
    CommercialClosureInput,
    OWNER_INTENT_HASH,
    PRODUCT_ID,
    canonical_product_contract,
    compile_commercial_closure,
)
from federation.product_release_factory_v1 import (
    ProductReleaseInput,
    compile_product_release_bundle,
)


def test_canonical_product_contract_is_commercially_bounded_and_stable():
    contract = canonical_product_contract()
    assert contract.product_id == PRODUCT_ID
    assert len(OWNER_INTENT_HASH) == 64
    assert "INSTALL_WITHOUT_ADMIN_ON_WINDOWS" in contract.user_journeys
    assert "LOCAL_OFFLINE_CORE" in contract.required_outcomes
    assert "PROVIDER_NEUTRAL_ROUTING" in contract.required_outcomes
    assert "OWNER_CUSTOMER_VALUE_MEASURED" in contract.required_outcomes


def test_source_only_state_cannot_false_promote_to_commercial_release():
    report = compile_commercial_closure(
        CommercialClosureInput(
            observed_proofs=(
                ProofKey.PRODUCT_CONTRACT.value,
                ProofKey.SYSTEM_GENOME.value,
                ProofKey.ARCHITECTURE.value,
                ProofKey.SOURCE.value,
            ),
        )
    )
    assert report.commercial_state == "COMMERCIAL_CLOSURE_IN_PROGRESS"
    assert report.release_status == "HOLD"
    assert report.provider_effect_authorized is False


def test_deterministic_test_state_is_not_runtime_or_value_proof():
    proofs = tuple(
        key.value
        for key in (
            ProofKey.PRODUCT_CONTRACT,
            ProofKey.SYSTEM_GENOME,
            ProofKey.ARCHITECTURE,
            ProofKey.SOURCE,
            ProofKey.UNIT_TESTS,
            ProofKey.INTEGRATION_TESTS,
            ProofKey.CONTRACT_TESTS,
            ProofKey.SECURITY_TESTS,
            ProofKey.PERFORMANCE_TESTS,
        )
    )
    report = compile_commercial_closure(
        CommercialClosureInput(observed_proofs=proofs)
    )
    assert report.maturity_stage == MaturityStage.DETERMINISTIC_TESTED.name
    assert report.commercial_state == "COMMERCIAL_BUILD_VALIDATED"
    assert report.go_live_status != "READY_FOR_PROGRESSIVE_GO_LIVE"


def test_hypercube_compiles_every_canonical_project_bottleneck():
    report = compile_commercial_closure(CommercialClosureInput())
    assert len(report.hypercube_resolution_receipts) == 5
    assert all(len(item) == 64 for item in report.hypercube_resolution_receipts)
    assert "Windows non-admin install" in report.commercial_features
    assert "durable resumable missions" in report.commercial_features
    assert any(
        action.startswith("HYPERCUBE_RESOLVE:")
        for action in report.next_actions
    )


def test_unknown_proof_fails_closed():
    with pytest.raises(ValueError, match="FUSE_COMMERCIAL_UNKNOWN_PROOF"):
        compile_commercial_closure(
            CommercialClosureInput(observed_proofs=("MADE_UP_PROOF",))
        )


def test_report_is_deterministic_for_identical_inputs():
    request = CommercialClosureInput()
    assert (
        compile_commercial_closure(request).receipt_sha256
        == compile_commercial_closure(request).receipt_sha256
    )


def test_release_factory_targets_user_installable_windows_distribution():
    contract = canonical_product_contract()
    bundle = compile_product_release_bundle(
        ProductReleaseInput(
            product_id=PRODUCT_ID,
            product_contract_fingerprint=contract.fingerprint,
            version="0.1.0-candidate",
            executable_entrypoints=(
                "fuse-one-desktop.exe",
                "fuse-one-cli.exe",
            ),
            website_routes=("/", "/download", "/docs", "/trust", "/status"),
            installer_targets=("MSIX_USER", "ZIP_PORTABLE"),
        )
    )
    installer = next(c for c in bundle.components if c.kind == "INSTALLER")
    assert "MSIX_USER" in installer.contract["targets"]
    assert "ZIP_PORTABLE" in installer.contract["targets"]
    assert installer.contract["signing"] == "REQUIRED_BEFORE_RELEASE"


def test_even_all_product_release_proofs_do_not_replace_value_maturity():
    report = compile_commercial_closure(
        CommercialClosureInput(
            release_terminal_proofs=(
                "WEBSITE_DEPLOYED_READBACK",
                "INSTALLER_SIGNED",
                "CLEAN_INSTALL_VERIFIED",
                "UPGRADE_VERIFIED",
                "UNINSTALL_VERIFIED",
                "SECURE_UPDATE_VERIFIED",
                "TENANT_ISOLATION_VERIFIED",
                "AUTH_VERIFIED",
                "RECOVERY_VERIFIED",
                "SUPPLY_CHAIN_VERIFIED",
                "TRUST_CENTER_CLAIMS_CURRENT",
                "OWNER_VALUE_VERIFIED",
            ),
        )
    )
    assert report.release_status == "RELEASE_READY"
    assert report.commercial_state != "COMMERCIAL_RELEASE_READY"


def test_full_synthetic_proof_vector_reaches_release_ready_only_with_all_gates():
    report = compile_commercial_closure(
        CommercialClosureInput(
            observed_proofs=tuple(item.value for item in ProofKey),
            release_terminal_proofs=(
                "WEBSITE_DEPLOYED_READBACK",
                "INSTALLER_SIGNED",
                "CLEAN_INSTALL_VERIFIED",
                "UPGRADE_VERIFIED",
                "UNINSTALL_VERIFIED",
                "SECURE_UPDATE_VERIFIED",
                "TENANT_ISOLATION_VERIFIED",
                "AUTH_VERIFIED",
                "RECOVERY_VERIFIED",
                "SUPPLY_CHAIN_VERIFIED",
                "TRUST_CENTER_CLAIMS_CURRENT",
                "OWNER_VALUE_VERIFIED",
            ),
            exact_effect_authority=True,
            rollback_verified=True,
            semantic_canary_defined=True,
        )
    )
    assert report.maturity_stage == MaturityStage.VALUE_VERIFIED.name
    assert report.go_live_status == "READY_FOR_PROGRESSIVE_GO_LIVE"
    assert report.release_status == "RELEASE_READY"
    assert report.commercial_state == "COMMERCIAL_RELEASE_READY"
