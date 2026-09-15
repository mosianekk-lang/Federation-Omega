from __future__ import annotations

import os
from typing import Any

from mcp.server.mcpserver import MCPServer

from . import pairing_service
from .firestore_relay import FirestoreRelay
from .scsf_control_signer import control_signer_from_env
from .scsf_protocol import FirestoreSCSFStore, SCSFRuntime, bind_scsf_routes
from .trust_spine_v21 import relay_mode


def _bind_scsf(server: MCPServer, relay: Any) -> MCPServer:
    """Attach SCSF to the existing relay without creating a second state root."""
    runtime = SCSFRuntime(
        store=FirestoreSCSFStore(relay),
        control_signer=control_signer_from_env(),
    )
    bind_scsf_routes(server, runtime)
    return server


def build_agent_only_server(*, relay: Any) -> MCPServer:
    """Preserve the admitted legacy pairing surface and add SCSF v1 routes."""
    return _bind_scsf(pairing_service.build_agent_only_server(relay=relay), relay)


def build_server(*, relay: Any, issuer: str, resource_url: str, jwks_url: str) -> MCPServer:
    """Preserve full MCP + legacy pairing while adding the native SCSF surface."""
    server = pairing_service.build_server(
        relay=relay,
        issuer=issuer,
        resource_url=resource_url,
        jwks_url=jwks_url,
    )
    return _bind_scsf(server, relay)


def server_from_env() -> MCPServer:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise RuntimeError("MISSING_REQUIRED_ENV:GOOGLE_CLOUD_PROJECT")

    relay = FirestoreRelay(
        project=project,
        root_secret=os.environ.get("FUSE_RELAY_ROOT_SECRET"),
    )
    issuer = os.environ.get("FUSE_OIDC_ISSUER")
    jwks = os.environ.get("FUSE_OIDC_JWKS_URL")
    mode = relay_mode(oidc_issuer=issuer, oidc_jwks_url=jwks)

    if mode == "AGENT_ONLY_BOOTSTRAP":
        return build_agent_only_server(relay=relay)

    resource = os.environ.get("FUSE_MCP_RESOURCE_URL")
    if not resource:
        raise RuntimeError("MISSING_REQUIRED_ENV:FUSE_MCP_RESOURCE_URL")
    return build_server(
        relay=relay,
        issuer=str(issuer),
        resource_url=resource,
        jwks_url=str(jwks),
    )


def main() -> None:
    server_from_env().run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
