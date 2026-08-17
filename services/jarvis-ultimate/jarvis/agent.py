"""Google ADK entrypoint. The deterministic kernel remains the execution authority."""

from .providers import SYSTEM_PROMPT

try:
    from google.adk import Agent
    root_agent = Agent(name="jarvis_ultimate", model="gemini-flash-latest", instruction=SYSTEM_PROMPT)
except Exception:
    root_agent = None
