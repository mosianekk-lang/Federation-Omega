from __future__ import annotations

import importlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "services" / "sol62_client_runtime"


class Sol62ContainerContractV1Tests(unittest.TestCase):
    def test_dockerfile_uses_service_dependency_manifest_and_nonroot_runtime(self) -> None:
        docker = (SERVICE / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("FROM python:3.12-slim", docker)
        self.assertIn(
            "COPY services/sol62_client_runtime/requirements.txt /tmp/sol62-requirements.txt",
            docker,
        )
        self.assertIn(
            "RUN pip install --no-cache-dir -r /tmp/sol62-requirements.txt",
            docker,
        )
        self.assertIn("USER fuse", docker)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", docker)
        self.assertNotIn(" latest", docker.lower())

    def test_manifest_covers_transitive_gateway_runtime_imports(self) -> None:
        requirements = (SERVICE / "requirements.txt").read_text(encoding="utf-8")
        required = (
            "fastapi==",
            "uvicorn[standard]==",
            "pydantic==",
            "httpx==",
            "google-auth==",
            "google-cloud-firestore==",
        )
        for marker in required:
            self.assertIn(marker, requirements)

    def test_runtime_modules_import_in_admission_environment(self) -> None:
        modules = (
            "services.sol62_client_runtime.app",
            "services.sol62_client_runtime.gateway_adapter",
            "services.fuse_mobile_gateway.runtime",
            "services.fuse_mobile_gateway.bindings",
        )
        for module in modules:
            with self.subTest(module=module):
                importlib.import_module(module)


if __name__ == "__main__":
    unittest.main()
