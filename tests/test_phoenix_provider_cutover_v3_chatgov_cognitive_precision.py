from __future__ import annotations

import unittest

from bubbles.chat_governor_omega3 import test_cognitive_precision as cognitive_precision_tests


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None) -> unittest.TestSuite:
    """Bridge the canonical ChatGov cognitive-precision suite into Airlock discovery.

    Federation Omega Airlock executes test_phoenix_provider_cutover_v3*.py.
    Keeping this bridge tiny ensures the canonical ChatGov suite is actually
    executed by admission CI without duplicating or weakening its assertions.
    """
    del tests, pattern
    return loader.loadTestsFromModule(cognitive_precision_tests)


if __name__ == "__main__":
    unittest.main()
