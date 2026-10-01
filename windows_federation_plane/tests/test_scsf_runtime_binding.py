from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch
import unittest

from federation_windows_plane import combined_service


class _FakeRelay:
    pass


class SCSFRuntimeBindingTests(unittest.TestCase):
    def test_agent_only_server_preserves_legacy_routes_and_adds_scsf_routes(self) -> None:
        env = {
            "FUSE_WINDOWS_SOURCE_EPOCH": "a" * 40,
            "FUSE_WINDOWS_POLICY_EPOCH": "FUSE_WINDOWS_H1_TPM_PAIRING_V1",
        }
        with patch.dict(os.environ, env, clear=True):
            server = combined_service.build_agent_only_server(relay=_FakeRelay())
        paths = {
            str(getattr(route, "path", ""))
            for route in getattr(server, "_custom_starlette_routes", ())
            if getattr(route, "path", None)
        }
        for path in (
            "/agent/enroll/start",
            "/agent/enroll/complete",
            "/agent/runtime/poll",
            "/agent/runtime/complete",
            "/v1/agent/enroll",
            "/v1/agent/heartbeat",
            "/v1/agent/poll",
            "/v1/agent/complete",
        ):
            self.assertIn(path, paths)

    def test_production_entrypoint_is_combined_service(self) -> None:
        root = Path(__file__).resolve().parents[2]
        pyproject = (root / "windows_federation_plane" / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(
            'federation-windows-relay = "federation_windows_plane.combined_service:main"',
            pyproject,
        )

    def test_combined_service_has_no_ephemeral_control_signer_fallback(self) -> None:
        root = Path(__file__).resolve().parents[2]
        source = (
            root
            / "windows_federation_plane"
            / "src"
            / "federation_windows_plane"
            / "combined_service.py"
        ).read_text(encoding="utf-8")
        self.assertIn("control_signer_from_env()", source)
        self.assertNotIn("P256SoftwareControlSigner.generate", source)
        self.assertNotIn("ECDSASigner.generate", source)


if __name__ == "__main__":
    unittest.main()
