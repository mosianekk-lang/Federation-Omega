from __future__ import annotations

from .live_thread import include_live_thread_if_enabled
from .secure_service import app

include_live_thread_if_enabled(app)
