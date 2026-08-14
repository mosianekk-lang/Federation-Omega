"""Airlock-discovered deterministic provider-binding regressions for ChatBridge Ω4.

The tests use a fake provider surface. They prove source/runtime contracts for provider
identity binding, cross-process restore, RunState fencing and approval resume without
claiming a live OpenAI API canary.
"""

from bubbles.chatbridge_omega4.test_openai_provider import ChatBridgeOmega4OpenAIProviderTests

__all__ = ["ChatBridgeOmega4OpenAIProviderTests"]
