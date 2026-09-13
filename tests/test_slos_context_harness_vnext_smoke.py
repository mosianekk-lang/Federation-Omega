import unittest

from superior_logic.context_tournament import ContextTournament
from superior_logic.harness_tournament import HarnessTournament


class SmokeTests(unittest.TestCase):
    def test_components_construct(self):
        self.assertIsInstance(ContextTournament(), ContextTournament)
        self.assertIsInstance(HarnessTournament(), HarnessTournament)


if __name__ == "__main__":
    unittest.main()
