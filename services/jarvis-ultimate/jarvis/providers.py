from __future__ import annotations

import os
from typing import Any


SYSTEM_PROMPT = """You are JARVIS Ultimate Federation. Be precise, calm and evidence-led.
Separate observations, inferences and unknowns. Use scientific reasoning and minimum sufficient action.
Never claim credentials, access, deployment, learning, autonomy or provider fruit without current proof.
Effectful actions require a current Formation decision and single-use permit. Unknown actions fail closed.
Kung-fu principles are strategic heuristics: economy, balance, adaptation and disciplined restraint.
"""


class OfflineReasoner:
    name = "offline-deterministic"

    def respond(self, message: str, context: dict[str, Any]) -> str:
        live = [c["id"] for c in context["capabilities"] if str(c["state"]).endswith("VERIFIED_LIVE")]
        return f"JARVIS offline analysis: objective={message.strip()!r}; verified live capabilities={', '.join(live)}. Gemini requires verified GOOGLE_API_KEY or ADC."


class GeminiReasoner:
    name = "google-genai"

    def __init__(self, model: str | None = None) -> None:
        from google import genai
        self.client = genai.Client()
        self.model = model or os.getenv("JARVIS_GEMINI_MODEL", "gemini-flash-latest")

    def respond(self, message: str, context: dict[str, Any]) -> str:
        prompt = SYSTEM_PROMPT + "\nCURRENT CAPABILITY STATES:\n" + str(context["capabilities"]) + "\nUSER:\n" + message
        result = self.client.models.generate_content(model=self.model, contents=prompt)
        return result.text or ""


def select_reasoner() -> OfflineReasoner | GeminiReasoner:
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_CLOUD_PROJECT"):
        try:
            return GeminiReasoner()
        except Exception:
            return OfflineReasoner()
    return OfflineReasoner()
