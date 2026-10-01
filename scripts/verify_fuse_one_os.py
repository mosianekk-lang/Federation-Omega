#!/usr/bin/env python3
"""Run bounded FUSE-ONE integration courts without provider calls or deployment.

Use the runtime's pinned dependencies plus pytest. State is isolated in a
temporary directory. The existing source-admission and provider-canary pipeline
remains responsible for release; this command cannot grant release authority.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
COURTS = (
    "tests/test_fuse_unified_service_catalog_v1.py",
    "tests/test_fuse_one_os_api.py",
    "tests/test_sol62_atomic_owned_mission.py",
    "tests/test_fuse_ecosystem_v1.py",
    "tests/test_fuse_unified_capability_fabric_v1.py",
    "tests/test_sol62_capability_registry.py",
    "tests/test_sol62_sovereign_attachment_canary_contract.py",
    "tests/test_sol62_browser_carrier_resilience.py",
    "tests/test_sol62_alpha_omega_formation_binding.py",
)


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("Node.js is required for the browser source syntax check.", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="fuse-one-verification-") as state:
        env = dict(os.environ)
        # These tests are local. Do not inherit a real configured provider.
        for name in tuple(env):
            if name.startswith(("FUSE_MOBILE_", "SOL62_WORKER_")):
                env.pop(name)
        for name, suffix in (
            ("SOL62_CLIENT_ROOT", "sol"),
            ("SOL62_STRATEGY_ROOT", "strategy"),
            ("FUSE_GENESIS_HOST_ROOT", "genesis"),
        ):
            env[name] = str(Path(state) / suffix)
        commands = [
            [node, "--check", "services/sol62_client_runtime/static/app.js"],
            [sys.executable, "-m", "pytest", "-q", *COURTS],
        ]
        for command in commands:
            result = subprocess.run(command, cwd=ROOT, env=env, check=False)
            if result.returncode:
                return result.returncode
    print("FUSE-ONE local integration courts passed. Provider release remains separately gated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
