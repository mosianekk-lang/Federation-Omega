from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Mapping

from benchmarking.cfbe_omega.bubbles_work_graph_adapter_v1 import (
    BubblesWorkNode,
    plan_bubbles_work_graph,
)
from benchmarking.cfbe_omega.fidelity_constraint_isolation import (
    AdapterRoute,
    CanonicalSource,
    CapabilityRequirement,
    FidelityMode,
    InvariantKind,
    IsolationPolicy,
    MaturityEvidence,
    MaturityState,
    PlatformProfile,
    ProtectedInvariant,
    isolate_constraints,
)


SCHEMA = "CFBE-OMEGA-FIDELITY-ADAPTER-CERTIFICATION-SCORECARD-V1"
PROFILE_SCHEMA = "CFBE-OMEGA-FIDELITY-ADAPTER-PROFILES-V1"
OBSERVATION_SCHEMA = "CFBE-OMEGA-FIDELITY-ADAPTER-DISCOVERY-OBSERVATION-V1"
EXPECTED_PLATFORMS = ("github", "google-drive", "gmail", "canva")
PASSING_CANARY_STATES = frozenset({"PASS", "PASS_WITH_ROUTE_VARIANCE"})
PROFILES_PATH = Path(__file__).with_name("profiles_v1.json")


class CertificationError(ValueError):
    """Raised when a profile, observation, or scorecard input fails closed."""


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha(value: object) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CertificationError(code)


def _require_sha256(value: object, code: str) -> str:
    _require(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value),
        code,
    )
    return value


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def load_profiles(path: str | Path = PROFILES_PATH) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_profiles(payload)
    return payload


def validate_profiles(payload: Mapping[str, Any]) -> None:
    _require(payload.get("schema") == PROFILE_SCHEMA, "PROFILE_SCHEMA_MISMATCH")
    _require(payload.get("version") == "1.0.0", "PROFILE_VERSION_MISMATCH")
    canonical = _mapping(payload.get("canonicalContract"), "CANONICAL_CONTRACT_REQUIRED")
    controls = _mapping(canonical.get("controls"), "CANONICAL_CONTROLS_REQUIRED")
    for key in (
        "canonicalPreserved",
        "providerMutationAllowed",
        "authorityInheritanceAllowed",
        "credentialInheritanceAllowed",
        "userBurdenAllowed",
        "recurringCostAllowed",
        "fullDoctrineRollbackPreserved",
    ):
        _require(isinstance(controls.get(key), bool), f"CANONICAL_CONTROL_INVALID:{key}")
    _require(controls["canonicalPreserved"] is True, "CANONICAL_PRESERVATION_REQUIRED")
    _require(controls["providerMutationAllowed"] is False, "PROVIDER_MUTATION_MUST_BE_FALSE")
    _require(controls["authorityInheritanceAllowed"] is False, "AUTHORITY_INHERITANCE_MUST_BE_FALSE")
    _require(controls["credentialInheritanceAllowed"] is False, "CREDENTIAL_INHERITANCE_MUST_BE_FALSE")
    _require(controls["userBurdenAllowed"] is False, "USER_BURDEN_MUST_BE_FALSE")
    _require(controls["recurringCostAllowed"] is False, "RECURRING_COST_MUST_BE_FALSE")
    _require(controls["fullDoctrineRollbackPreserved"] is True, "ROLLBACK_PRESERVATION_REQUIRED")

    requirements = canonical.get("requiredCapabilities")
    _require(
        isinstance(requirements, list)
        and requirements
        and all(isinstance(item, str) and item for item in requirements)
        and len(set(requirements)) == len(requirements),
        "REQUIRED_CAPABILITIES_INVALID",
    )
    platforms = payload.get("platforms")
    _require(isinstance(platforms, list), "PLATFORMS_REQUIRED")
    platform_ids = tuple(item.get("platformId") for item in platforms if isinstance(item, Mapping))
    _require(platform_ids == EXPECTED_PLATFORMS, "PLATFORM_PORTFOLIO_OR_ORDER_MISMATCH")
    for platform in platforms:
        profile = _mapping(platform, "PLATFORM_PROFILE_INVALID")
        platform_id = str(profile["platformId"])
        _require(bool(str(profile.get("exactScope", "")).strip()), f"EXACT_SCOPE_REQUIRED:{platform_id}")
        _require(bool(str(profile.get("discoveryRef", "")).strip()), f"DISCOVERY_REF_REQUIRED:{platform_id}")
        _require_sha256(profile.get("connectorContractSha256"), f"CONTRACT_HASH_INVALID:{platform_id}")
        read_tools = profile.get("readTools")
        _require(
            isinstance(read_tools, list)
            and read_tools
            and all(isinstance(item, str) and item for item in read_tools),
            f"READ_TOOLS_REQUIRED:{platform_id}",
        )
        adapter = _mapping(profile.get("adapterRoute"), f"ADAPTER_REQUIRED:{platform_id}")
        _require(adapter.get("provides") == requirements, f"ADAPTER_CAPABILITY_ASYMMETRY:{platform_id}")
        _require(adapter.get("maturityState") == "DETERMINISTIC_TESTED", f"MATURITY_INVALID:{platform_id}")
        _require(adapter.get("authorityCeiling") == "A1", f"AUTHORITY_INVALID:{platform_id}")
        _require(adapter.get("recurringCost") == 0, f"RECURRING_COST_INVALID:{platform_id}")
        _require(adapter.get("userBurden") == 0, f"USER_BURDEN_INVALID:{platform_id}")
        _require(adapter.get("externalEffectRequired") is False, f"EXTERNAL_EFFECT_INVALID:{platform_id}")
        _require(adapter.get("preservesCanonicalSource") is True, f"FIDELITY_INVALID:{platform_id}")


def load_observations(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_observations(payload)
    return payload


def validate_observations(payload: Mapping[str, Any]) -> None:
    _require(payload.get("schema") == OBSERVATION_SCHEMA, "OBSERVATION_SCHEMA_MISMATCH")
    _require(isinstance(payload.get("observedAt"), str) and payload["observedAt"], "OBSERVED_AT_REQUIRED")
    source_head = payload.get("sourceHead")
    _require(
        isinstance(source_head, str)
        and len(source_head) == 40
        and all(character in "0123456789abcdef" for character in source_head),
        "SOURCE_HEAD_INVALID",
    )
    _require(payload.get("externalEffects") == 0, "OBSERVATION_EXTERNAL_EFFECT_PRESENT")
    _require(payload.get("providerWrites") == 0, "OBSERVATION_PROVIDER_WRITE_PRESENT")
    _require(payload.get("manualUserTasks") == [], "OBSERVATION_USER_BURDEN_PRESENT")
    platforms = payload.get("platforms")
    _require(isinstance(platforms, list), "OBSERVATION_PLATFORMS_REQUIRED")
    ids = tuple(item.get("platformId") for item in platforms if isinstance(item, Mapping))
    _require(ids == EXPECTED_PLATFORMS, "OBSERVATION_PLATFORM_PORTFOLIO_OR_ORDER_MISMATCH")
    for item in platforms:
        platform_id = str(item["platformId"])
        _require_sha256(
            item.get("connectorContractSha256"),
            f"OBSERVATION_CONTRACT_HASH_INVALID:{platform_id}",
        )
        _require(
            item.get("readCanaryState") in PASSING_CANARY_STATES | {"FAIL"},
            f"READ_CANARY_STATE_INVALID:{platform_id}",
        )
        refs = item.get("proofRefs")
        _require(
            isinstance(refs, list)
            and refs
            and all(isinstance(ref, str) and ref for ref in refs),
            f"READ_CANARY_PROOF_REQUIRED:{platform_id}",
        )


def _canonical_source(config: Mapping[str, Any]) -> CanonicalSource:
    contract = config["canonicalContract"]
    controls = contract["controls"]
    invariants = tuple(
        ProtectedInvariant(
            invariant_id=f"control-{name}",
            kind=InvariantKind.JSON_POINTER,
            selector=f"/controls/{name}",
        )
        for name in sorted(controls)
    ) + (
        ProtectedInvariant(
            invariant_id="required-capability-symmetry",
            kind=InvariantKind.JSON_POINTER,
            selector="/requiredCapabilities",
        ),
    )
    return CanonicalSource(
        source_id="cfbe-omega-fidelity-adapter-wave1",
        version=str(config["version"]),
        media_type="application/json",
        content=_stable_json(contract),
        fidelity_mode=FidelityMode.PROTECTED_INVARIANTS,
        protected_invariants=invariants,
    )


def _evidence(payload: Mapping[str, Any]) -> MaturityEvidence:
    return MaturityEvidence(
        source_ref=str(payload.get("sourceRef", "")),
        test_ref=str(payload.get("testRef", "")),
        rollback_ref=str(payload.get("rollbackRef", "")),
    )


def _adapter(profile: Mapping[str, Any]) -> AdapterRoute:
    payload = profile["adapterRoute"]
    return AdapterRoute(
        adapter_id=str(payload["adapterId"]),
        provides=tuple(str(item) for item in payload["provides"]),
        maturity=MaturityState(str(payload["maturityState"])),
        evidence=_evidence(payload["evidence"]),
        authority_ceiling=str(payload["authorityCeiling"]),
        recurring_cost=float(payload["recurringCost"]),
        user_burden=float(payload["userBurden"]),
        external_effect_required=bool(payload["externalEffectRequired"]),
        preserves_canonical_source=bool(payload["preservesCanonicalSource"]),
        fidelity_evidence_ref=str(payload["fidelityEvidenceRef"]),
        priority=int(payload.get("priority", 100)),
    )


def _sanitized_observations(
    observations: Mapping[str, Any] | None,
    profiles: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any] | None:
    if observations is None:
        return None
    validate_observations(observations)
    sanitized_platforms: list[dict[str, Any]] = []
    for item in observations["platforms"]:
        platform_id = str(item["platformId"])
        expected_hash = profiles[platform_id]["connectorContractSha256"]
        _require(
            item["connectorContractSha256"] == expected_hash,
            f"OBSERVATION_PROFILE_CONTRACT_MISMATCH:{platform_id}",
        )
        sanitized_platforms.append(
            {
                "platformId": platform_id,
                "connectorContractSha256": item["connectorContractSha256"],
                "readCanaryState": item["readCanaryState"],
                "proofRefs": sorted(set(item["proofRefs"])),
            }
        )
    return {
        "schema": OBSERVATION_SCHEMA,
        "observedAt": observations["observedAt"],
        "sourceHead": observations["sourceHead"],
        "externalEffects": 0,
        "providerWrites": 0,
        "manualUserTasks": [],
        "platforms": sanitized_platforms,
    }


def run_certification(
    config: Mapping[str, Any] | None = None,
    *,
    observations: Mapping[str, Any] | None = None,
    candidate_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    profiles_config = deepcopy(dict(config)) if config is not None else load_profiles()
    validate_profiles(profiles_config)
    profiles = {
        str(item["platformId"]): item for item in profiles_config["platforms"]
    }
    canonical = _canonical_source(profiles_config)
    candidate = _stable_json(
        deepcopy(dict(candidate_contract))
        if candidate_contract is not None
        else profiles_config["canonicalContract"]
    )
    requirement_ids = tuple(profiles_config["canonicalContract"]["requiredCapabilities"])
    requirements = tuple(
        CapabilityRequirement(item, f"Provide {item} without canonical dilution")
        for item in requirement_ids
    )

    nodes = tuple(
        BubblesWorkNode(
            work_id=f"CERTIFY-{platform_id.upper()}",
            capability=f"{platform_id} fidelity adapter court",
            rail=f"SURFACE_{platform_id.upper().replace('-', '_')}",
            next_action="run identical effect-free CFBE fidelity isolation court",
            closure_state="INTEGRATE",
            priority=index,
            role="PRIMARY",
        )
        for index, platform_id in enumerate(EXPECTED_PLATFORMS, start=1)
    )
    wave = plan_bubbles_work_graph(nodes)
    selected_work_ids = tuple(item.capability_id for item in wave.selected)
    _require(
        set(selected_work_ids) == {node.work_id for node in nodes} and not wave.held,
        "BUBBLES_FOUR_SURFACE_WAVE_NOT_SELECTED",
    )

    sanitized = _sanitized_observations(observations, profiles)
    observation_by_platform = (
        {item["platformId"]: item for item in sanitized["platforms"]}
        if sanitized is not None
        else {}
    )
    courts: list[dict[str, Any]] = []
    for platform_id in EXPECTED_PLATFORMS:
        profile = profiles[platform_id]
        result = isolate_constraints(
            canonical=canonical,
            candidate=candidate,
            platform=PlatformProfile(
                platform_id=platform_id,
                exact_scope=str(profile["exactScope"]),
                discovery_ref=str(profile["discoveryRef"]),
            ),
            requirements=requirements,
            adapters=(_adapter(profile),),
            policy=IsolationPolicy(
                available_authority="A1",
                max_recurring_cost=0,
                max_user_burden=0,
                allow_external_effects=False,
            ),
        )
        observation = observation_by_platform.get(platform_id)
        court_pass = (
            result["resultState"] == "ROUTE_READY_LOCAL"
            and result["fidelity"]["verdict"] == "ACCEPT_ZERO_DILUTION"
            and result["truthBoundary"]["canonicalPreserved"] is True
            and result["truthBoundary"]["providerMutationPerformed"] is False
            and result["selectedAdapters"] == [profile["adapterRoute"]["adapterId"]]
        )
        courts.append(
            {
                "platformId": platform_id,
                "courtPass": court_pass,
                "resultState": result["resultState"],
                "executionState": result["executionState"],
                "fidelityVerdict": result["fidelity"]["verdict"],
                "canonicalPreserved": result["truthBoundary"]["canonicalPreserved"],
                "selectedAdapters": result["selectedAdapters"],
                "requirementCount": len(result["requirementDecisions"]),
                "buildTriggerCount": len(result["buildTriggers"]),
                "providerMutationPerformed": result["truthBoundary"]["providerMutationPerformed"],
                "connectorContractSha256": profile["connectorContractSha256"],
                "readCanaryState": observation["readCanaryState"] if observation else "NOT_SUPPLIED",
                "kernelReceiptSha256": result["receiptSha256"],
            }
        )

    court_pass_count = sum(item["courtPass"] for item in courts)
    live_canary_pass_count = sum(
        item["readCanaryState"] in PASSING_CANARY_STATES for item in courts
    )
    if court_pass_count != len(EXPECTED_PLATFORMS):
        certification_state = "COURT_FAILURE"
    elif sanitized is None:
        certification_state = "LOCAL_COURTS_4_OF_4_PASS"
    elif live_canary_pass_count == len(EXPECTED_PLATFORMS):
        certification_state = "LIVE_READ_CANARIES_4_OF_4_AND_LOCAL_COURTS_4_OF_4_PASS"
    else:
        certification_state = "LIVE_CANARY_FAILURE"

    observation_block = {
        "state": "NOT_SUPPLIED" if sanitized is None else "SUPPLIED_PUBLIC_SAFE",
        "sha256": "" if sanitized is None else _sha(sanitized),
        "payload": sanitized,
    }
    scorecard: dict[str, Any] = {
        "schema": SCHEMA,
        "version": "1.0.0",
        "certificationState": certification_state,
        "executionState": "NOT_EXECUTED",
        "profileContract": {
            "schema": PROFILE_SCHEMA,
            "version": profiles_config["version"],
            "sha256": _sha(profiles_config),
        },
        "canonicalSource": {
            "sourceId": canonical.source_id,
            "sha256": canonical.sha256,
            "fidelityMode": canonical.fidelity_mode.value,
        },
        "bubblesWave": {
            "selectedWorkIds": sorted(selected_work_ids),
            "heldCount": len(wave.held),
            "providerEffectAuthorized": wave.provider_effect_authorized,
            "financialEffectAuthorized": wave.financial_effect_authorized,
            "receiptSha256": wave.receipt_sha256,
        },
        "courts": courts,
        "comparison": {
            "platformCount": len(EXPECTED_PLATFORMS),
            "courtPassCount": court_pass_count,
            "liveCanaryPassCount": live_canary_pass_count,
            "requirementCountPerCourt": len(requirement_ids),
            "profileSymmetry": all(
                profile["adapterRoute"]["provides"] == list(requirement_ids)
                for profile in profiles.values()
            ),
            "canonicalPreservationRate": court_pass_count / len(EXPECTED_PLATFORMS),
            "externalEffects": 0,
            "providerWrites": 0,
            "recurringCost": 0,
            "ownerBurden": 0,
            "authorityCeiling": "A1",
        },
        "connectorObservation": observation_block,
        "truthBoundary": {
            "providerMutationPerformed": False,
            "providerDeploymentClaimed": False,
            "authorityInherited": False,
            "credentialsInherited": False,
            "stablePromotionAllowed": False,
            "fullDoctrineRollbackPreserved": True,
            "statement": (
                "Wave 1 certifies deterministic adapter fidelity and supplied live read "
                "canaries only. It performs no provider write, deployment, or stable promotion."
            ),
        },
    }
    scorecard["receiptSha256"] = _sha(scorecard)
    return scorecard


def write_json_atomic(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
