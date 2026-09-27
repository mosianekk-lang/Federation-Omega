from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CoreRuntimeSourcePresenceTests(unittest.TestCase):
    def test_capability_bearing_runtime_sources_survive_core_export(self):
        required = (
            "fuse_runtime/output_mirror_v1.mjs",
            "fuse_runtime/autonomous_improvement_loop_v1.mjs",
            "benchmarks/output_mirror_v3_power_diary_court.mjs",
            "products/fuse_localllm_desktop/v0.2.2/upstream/BUILD_INSTALL_LAUNCH_WINDOWS.cmd",
            "products/fuse_localllm_desktop/v0.2.2/upstream/src/main.cpp",
            "services/sol62_client_runtime/Dockerfile",
        )
        missing = [path for path in required if not (ROOT / path).is_file()]
        self.assertEqual([], missing, f"CORE_RUNTIME_SOURCE_MISSING:{missing}")


if __name__ == "__main__":
    unittest.main()
