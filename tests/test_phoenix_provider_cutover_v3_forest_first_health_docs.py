from __future__ import annotations

import unittest
from pathlib import Path


class ForestFirstHealthDocumentationTests(unittest.TestCase):
    def test_health_contract_exposes_user_visible_states(self) -> None:
        text = Path("evidenceops/lex_omega/FOREST_FIRST_HEALTH.md").read_text(encoding="utf-8")
        for token in (
            "ACTIVE_VERIFIED",
            "SYSTEM_READY_SESSION_NOT_RESTORED",
            "DEGRADED",
            "BLOCKED_HIGH_STAKES",
            "NOT_LOADED",
            "forest-first status",
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
