"""Airlock-discovered regression binding for ChatBridge Ω4.

The canonical deterministic suite lives with the Ω4 package. This wrapper binds it into
Federation Omega's already-admitted `test_phoenix_provider_cutover_v3*.py` discovery
surface without adding a new GitHub Actions workflow or widening workflow authority.
"""

from bubbles.chatbridge_omega4.test_omega4 import ChatBridgeOmega4Tests

__all__ = ["ChatBridgeOmega4Tests"]
