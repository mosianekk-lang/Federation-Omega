"""Airlock bridge for the ChatGov Ω3.1 completion-witness regression suite.

The canonical tests live beside the implementation. This bridge deliberately binds
that exact suite into the existing provider-cutover-v3 Airlock discovery path so a
new completion-witness implementation cannot receive admission credit merely from
source or test-file existence.
"""

from bubbles.chat_governor_omega3.test_completion import ChatGovCompletionInterlockTests


__all__ = ["ChatGovCompletionInterlockTests"]
