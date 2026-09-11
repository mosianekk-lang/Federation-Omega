"""Deterministic product/release factory contracts for Federation Omega.

This module compiles an already-approved ProductContract fingerprint plus explicit
product inputs into a source-level release bundle.  It does not deploy, publish,
sign, spend, alter IAM, or claim installer/runtime success.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence

SCHEMA = "FUSE_PRODUCT_RELEASE_FACTORY_V1"
SOURCE_EFFECT_ONLY = True
PROVIDER_EFFECT_AUTHORIZED = False


def _canon(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _sha(value: object) -> str:
    return sha256(_canon(value).encode("utf-8")).hexdigest()


def _norm(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(v).strip() for v in values if str(v).strip()}))


@dataclass(frozen=True, slots=True)
class ProductReleaseInput:
    product_id: str
    product_contract_fingerprint: str
    version: str
    executable_entrypoints: tuple[str, ...]
    website_routes: tuple[str, ...]
    installer_targets: tuple[str, ...]
    feature_flags: tuple[str, ...] = ()
    auth_adapters: tuple[str, ...] = ("OIDC", "PASSKEY")
    tenant_modes: tuple[str, ...] = ("SINGLE_TENANT", "MULTI_TENANT_READY")
    authority_ceiling: str = "A1_INTERNAL"
    data_boundary: str = "PRIVATE"

    def validate(self) -> "ProductReleaseInput":
        if not self.product_id.strip() or not self.version.strip():
            raise ValueError("PRF_PRODUCT_VERSION_REQUIRED")
        if len(self.product_contract_fingerprint) != 64:
            raise ValueError("PRF_PRODUCT_CONTRACT_FINGERPRINT_REQUIRED")
        if not self.executable_entrypoints:
            raise ValueError("PRF_EXECUTABLE_ENTRYPOINT_REQUIRED")
        if not self.website_routes:
            raise ValueError("PRF_WEBSITE_ROUTE_REQUIRED")
        if not self.installer_targets:
            raise ValueError("PRF_INSTALLER_TARGET_REQUIRED")
        if not self.authority_ceiling.strip() or not self.data_boundary.strip():
            raise ValueError("PRF_AUTHORITY_DATA_BOUNDARY_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class ReleaseComponent:
    component_id: str
    kind: str
    contract: Mapping[str, object]
    proof_required: tuple[str, ...]
    effect_class: str
    fingerprint_sha256: str


@dataclass(frozen=True, slots=True)
class ProductReleaseBundle:
    schema: str
    bundle_id: str
    product_id: str
    version: str
    contract_fingerprint: str
    components: tuple[ReleaseComponent, ...]
    promotion_edges: tuple[tuple[str, str], ...]
    required_terminal_proofs: tuple[str, ...]
    provider_effect_authorized: bool
    fingerprint_sha256: str

    def validate(self) -> "ProductReleaseBundle":
        expected = {
            "PRODUCT_SCAFFOLD", "WEBSITE", "INSTALLER", "SECURE_UPDATE_ROOT",
            "FEATURE_FLAGS", "ENVIRONMENT_PROMOTION", "TRUST_CENTER", "AI_BOM",
            "TENANT_CONTROL", "AUTH", "SUPPORT_INCIDENT", "QUALITY_LAB",
        }
        kinds = {c.kind for c in self.components}
        if kinds != expected:
            raise ValueError("PRF_COMPONENT_SET_INCOMPLETE")
        if self.provider_effect_authorized:
            raise ValueError("PRF_SOURCE_FACTORY_CANNOT_AUTHORIZE_PROVIDER_EFFECT")
        if len(self.fingerprint_sha256) != 64:
            raise ValueError("PRF_BUNDLE_FINGERPRINT_INVALID")
        return self


def _component(kind: str, contract: Mapping[str, object], proofs: Sequence[str], effect: str = "SOURCE_ONLY") -> ReleaseComponent:
    payload = {"kind": kind, "contract": contract, "proofs": sorted(set(proofs)), "effect": effect}
    digest = _sha(payload)
    return ReleaseComponent(
        component_id=f"{kind}-{digest[:12].upper()}",
        kind=kind,
        contract=dict(contract),
        proof_required=tuple(sorted(set(proofs))),
        effect_class=effect,
        fingerprint_sha256=digest,
    )


def compile_product_release_bundle(spec: ProductReleaseInput) -> ProductReleaseBundle:
    spec.validate()
    entrypoints = _norm(spec.executable_entrypoints)
    routes = _norm(spec.website_routes)
    targets = _norm(spec.installer_targets)
    flags = _norm(spec.feature_flags)
    auth = _norm(spec.auth_adapters)
    tenants = _norm(spec.tenant_modes)

    components = (
        _component("PRODUCT_SCAFFOLD", {
            "entrypoints": entrypoints,
            "config_contract": "ENV_PLUS_TYPED_CONFIG",
            "health_contract": "ACTION_SPECIFIC_SEMANTIC_HEALTH",
            "rollback_contract": "EXACT_PREVIOUS_RELEASE_ID",
        }, ("SOURCE", "UNIT_TESTS", "INTEGRATION_TESTS")),
        _component("WEBSITE", {
            "routes": routes,
            "responsive": True,
            "accessibility_target": "WCAG_2_2_AA",
            "publish_default": "HELD",
        }, ("SOURCE", "ACCESSIBILITY", "DEPLOYMENT_RECEIPT", "PROVIDER_READBACK")),
        _component("INSTALLER", {
            "targets": targets,
            "operations": ("CLEAN_INSTALL", "UPGRADE", "REPAIR", "UNINSTALL", "ROLLBACK"),
            "signing": "REQUIRED_BEFORE_RELEASE",
        }, ("ARTIFACT_DIGEST", "SBOM", "SIGNATURE", "CLEAN_INSTALL", "UPGRADE", "UNINSTALL", "ROLLBACK")),
        _component("SECURE_UPDATE_ROOT", {
            "model": "TUF_STYLE_THRESHOLD_ROOT",
            "root_rotation": "EXPLICIT",
            "rollback_protection": True,
            "offline_root_supported": True,
        }, ("ROOT_METADATA", "THRESHOLD_SIGNATURES", "ROTATION_TEST", "ROLLBACK_ATTACK_TEST")),
        _component("FEATURE_FLAGS", {
            "contract": "OPENFEATURE_COMPATIBLE_PROVIDER_NEUTRAL",
            "default_behavior": "FAIL_CLOSED",
            "evaluation_context_minimized": True,
            "kill_switch": True,
        }, ("CONTRACT_TESTS", "DEFAULT_VALUE_TEST", "KILL_SWITCH_TEST")),
        _component("ENVIRONMENT_PROMOTION", {
            "graph": (("DEV", "TEST"), ("TEST", "STAGING"), ("STAGING", "CANARY"), ("CANARY", "PRODUCTION")),
            "progression": "PROOF_GATED",
            "automatic_rollback": "ON_HARD_GATE_REGRESSION",
        }, ("ARTIFACT_IDENTITY", "CANARY", "SEMANTIC_READBACK", "ROLLBACK")),
        _component("TRUST_CENTER", {
            "claims": "EVIDENCE_GATED_ONLY",
            "sections": ("SECURITY", "PRIVACY", "RELIABILITY", "SUPPLY_CHAIN", "AI_GOVERNANCE", "RECOVERY"),
            "unsupported_claims": "FORBIDDEN",
        }, ("CONTROL_EVIDENCE", "PROVIDER_EVIDENCE", "CURRENTNESS")),
        _component("AI_BOM", {
            "fields": ("MODEL_PROVIDER", "MODEL_ID", "VERSION", "LICENSE", "DATA_BOUNDARY", "REGION", "PURPOSE", "EVAL_RECEIPT"),
            "unknowns_fail_closed": True,
        }, ("MODEL_IDENTITY", "LICENSE", "PROVENANCE", "EVAL_RECEIPT")),
        _component("TENANT_CONTROL", {
            "modes": tenants,
            "isolation": "TENANT_SCOPED_IDENTITY_DATA_CONFIG_LIMITS",
            "quota_contract": "PER_TENANT",
            "admin_actions": "AUDITED",
        }, ("ISOLATION_TEST", "AUTHZ_TEST", "QUOTA_TEST", "AUDIT_TEST")),
        _component("AUTH", {
            "adapters": auth,
            "password_storage": "NOT_REQUIRED_FOR_PASSKEY_OIDC_PATH",
            "step_up": "CONSEQUENTIAL_EFFECTS",
        }, ("OIDC_CONFORMANCE", "PASSKEY_CONFORMANCE", "SESSION_REVOCATION", "STEP_UP_TEST")),
        _component("SUPPORT_INCIDENT", {
            "compiler": "FAILURE_FINGERPRINT_TO_RUNBOOK",
            "required_fields": ("FINGERPRINT", "IMPACT", "EVIDENCE", "ROLLBACK", "DO_NOT_RETRY_UNTIL"),
            "secret_redaction": True,
        }, ("REPLAY_TEST", "REDACTION_TEST", "ROLLBACK_LINK")),
        _component("QUALITY_LAB", {
            "personas": "SYNTHETIC_PRIVACY_SAFE",
            "courts": ("HAPPY_PATH", "FAILURE_PATH", "ACCESSIBILITY", "SECURITY", "RECOVERY", "UPGRADE"),
            "production_data_default": "FORBIDDEN",
        }, ("TEST_MATRIX", "FAILURE_FIXTURE", "RECOVERY_FIXTURE")),
    )
    promotion_edges = (("DEV", "TEST"), ("TEST", "STAGING"), ("STAGING", "CANARY"), ("CANARY", "PRODUCTION"))
    terminal = (
        "WEBSITE_DEPLOYED_READBACK", "INSTALLER_SIGNED", "CLEAN_INSTALL_VERIFIED",
        "UPGRADE_VERIFIED", "UNINSTALL_VERIFIED", "SECURE_UPDATE_VERIFIED",
        "TENANT_ISOLATION_VERIFIED", "AUTH_VERIFIED", "RECOVERY_VERIFIED",
        "SUPPLY_CHAIN_VERIFIED", "TRUST_CENTER_CLAIMS_CURRENT", "OWNER_VALUE_VERIFIED",
    )
    body = {
        "schema": SCHEMA,
        "product_id": spec.product_id,
        "version": spec.version,
        "contract": spec.product_contract_fingerprint,
        "authority": spec.authority_ceiling,
        "data_boundary": spec.data_boundary,
        "components": [asdict(c) for c in components],
        "promotion_edges": promotion_edges,
        "terminal": terminal,
        "provider_effect_authorized": False,
    }
    digest = _sha(body)
    return ProductReleaseBundle(
        schema=SCHEMA,
        bundle_id=f"PRB-{digest[:16].upper()}",
        product_id=spec.product_id,
        version=spec.version,
        contract_fingerprint=spec.product_contract_fingerprint,
        components=components,
        promotion_edges=promotion_edges,
        required_terminal_proofs=terminal,
        provider_effect_authorized=False,
        fingerprint_sha256=digest,
    ).validate()


def release_gate(bundle: ProductReleaseBundle, observed_proofs: Iterable[str]) -> dict[str, object]:
    bundle.validate()
    observed = set(observed_proofs)
    missing = tuple(p for p in bundle.required_terminal_proofs if p not in observed)
    status = "RELEASE_READY" if not missing else "HOLD"
    return {
        "schema": "FUSE_PRODUCT_RELEASE_GATE_V1",
        "bundle_id": bundle.bundle_id,
        "status": status,
        "missing": missing,
        "provider_effect_authorized": False,
        "fingerprint_sha256": _sha((bundle.fingerprint_sha256, status, missing)),
    }
