from __future__ import annotations

import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "strategic-fuse-appsscript-read-zero-traffic.yml"


def embedded_python_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    active: list[str] | None = None
    for line in text.splitlines():
        if active is None:
            if line.strip() == "python - <<'PY'":
                active = []
            continue
        if line.strip() == "PY":
            blocks.append(textwrap.dedent("\n".join(active)) + "\n")
            active = None
            continue
        active.append(line)
    if active is not None:
        raise AssertionError("UNTERMINATED_EMBEDDED_PYTHON_BLOCK")
    return blocks


class StrategicFuseEmbeddedPythonCompileTests(unittest.TestCase):
    def test_every_embedded_python_block_compiles(self) -> None:
        blocks = embedded_python_blocks(WORKFLOW.read_text(encoding="utf-8"))
        self.assertGreater(len(blocks), 0, "NO_EMBEDDED_PYTHON_BLOCKS_FOUND")
        for index, block in enumerate(blocks, start=1):
            with self.subTest(block=index):
                compile(block, f"{WORKFLOW}::embedded-python-{index}", "exec")


if __name__ == "__main__":
    unittest.main()
