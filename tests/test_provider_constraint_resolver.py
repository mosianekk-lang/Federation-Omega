from federation_consolidation.provider_constraint_resolver import (
    ExecutionRoute,
    ProviderState,
    ResolverError,
    resolve_constraints,
)


BASE = dict(
    live_main="2" * 40,
    phoenix_artifact_sha256="a" * 64,
    previous_main="1" * 40,
    previous_phoenix_artifact_sha256="b" * 64,
    github_installation_scope="selected",
    private_core_visible=False,
    private_ops_visible=False,
    private_github_admin_authority=False,
    gcp_admin_authority=False,
    gcp_native_runner_available=False,
    sealed_owner_artifact_available=True,
    openai_existing_key_management_available=False,
    current_candidate_sha256="c" * 64,
    candidate_bound_to_live_main=True,
    candidate_bound_to_artifact=True,
)


def test_selected_installation_is_eliminated_by_sealed_route():
    result = resolve_constraints(ProviderState(**BASE))
    assert result["selected_route"] == ExecutionRoute.OWNER_ONLY_SEALED_PACKET.value
    states = {x["constraint_id"]: x["state"] for x in result["constraints"]}
    assert states["GITHUB_INSTALLATION_SCOPE"] == "ELIMINATED_BY_ALTERNATE_ROUTE"
    assert states["PRIVATE_GITHUB_ADMIN_AUTHORITY"] == "ELIMINATED_BY_ALTERNATE_ROUTE"
    assert states["PRIVATE_CORE_OPS_VISIBILITY"] == "ELIMINATED_BY_ALTERNATE_ROUTE"
    assert result["provider_gates"] == [
        "GOOGLE_CLOUD_AUTHORITY",
        "OPENAI_EXISTING_KEY_MANAGEMENT",
    ]


def test_gcp_native_route_removes_github_dependency():
    state = ProviderState(
        **{
            **BASE,
            "gcp_admin_authority": True,
            "gcp_native_runner_available": True,
        }
    )
    result = resolve_constraints(state)
    assert result["selected_route"] == ExecutionRoute.GCP_NATIVE_SEALED_ARTIFACT.value
    assert "GITHUB_INSTALLATION_SCOPE" in result["internally_closed"]
    assert result["provider_gates"] == ["OPENAI_EXISTING_KEY_MANAGEMENT"]


def test_private_github_route_when_all_authority_exists():
    state = ProviderState(
        **{
            **BASE,
            "github_installation_scope": "all",
            "private_core_visible": True,
            "private_ops_visible": True,
            "private_github_admin_authority": True,
            "gcp_admin_authority": True,
            "gcp_native_runner_available": True,
            "openai_existing_key_management_available": True,
        }
    )
    result = resolve_constraints(state)
    assert result["selected_route"] == ExecutionRoute.PRIVATE_GITHUB_OPS_WIF.value
    assert result["provider_gates"] == []
    assert result["admission_state"] == "READY_FOR_FRESH_OWNER_AUTHORITY"


def test_candidate_drift_fails_closed():
    state = ProviderState(
        **{
            **BASE,
            "candidate_bound_to_artifact": False,
        }
    )
    result = resolve_constraints(state)
    states = {x["constraint_id"]: x for x in result["constraints"]}
    assert states["LIVE_MAIN_OR_ARTIFACT_DRIFT"]["state"] == "BLOCKED"
    assert states["LIVE_MAIN_OR_ARTIFACT_DRIFT"]["next_gate"] == (
        "REGENERATE_JUST_IN_TIME_CANDIDATE"
    )


def test_partial_private_topology_rejected():
    state = ProviderState(
        **{
            **BASE,
            "private_core_visible": True,
            "private_ops_visible": False,
        }
    )
    try:
        resolve_constraints(state)
    except ResolverError:
        return
    raise AssertionError("partial topology must fail")


def test_receipt_is_deterministic():
    state = ProviderState(**BASE)
    assert resolve_constraints(state) == resolve_constraints(state)
