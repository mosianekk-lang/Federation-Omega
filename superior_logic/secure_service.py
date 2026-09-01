from __future__ import annotations

from fastapi import FastAPI

from .runtime import SuperiorLogicRuntime
from .security import SlosAuthPolicy, SlosSecurityMiddleware
from .service import create_app, runtime


def create_secure_app(
    active_runtime: SuperiorLogicRuntime,
    *,
    auth_policy: SlosAuthPolicy | None = None,
) -> FastAPI:
    policy = auth_policy or SlosAuthPolicy.from_env()
    api = create_app(active_runtime)
    api.add_middleware(SlosSecurityMiddleware, policy=policy)

    @api.get("/security-state")
    def security_state() -> dict:
        return {
            "schema": "SLOS_APPLICATION_SECURITY_STATE_V1",
            "auth_mode": policy.mode.value,
            "audience": policy.audience,
            "read_auth_required": policy.require_read_auth,
            "mutation_auth_enforced": True,
            "trusted_proxy_enabled": policy.trusted_proxy_enabled,
            "raw_credentials_exposed": False,
            "legacy_service_module_network_safe": False,
            "deployment_entrypoint": "superior_logic.secure_service:app",
        }

    return api


# Canonical externally deployable application. The underlying service module is
# retained for compatibility and unit tests, but Docker/runtime deployment must
# point here so state-changing routes cannot be exposed unauthenticated.
app = create_secure_app(runtime)


__all__ = ["app", "create_secure_app"]
