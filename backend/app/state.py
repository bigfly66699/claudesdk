"""Process-wide mutable state (in-memory session cache, chat coordination)."""

from __future__ import annotations

sessions: dict[str, dict] = {}
stopped_sessions: set[str] = set()
active_chats: set[str] = set()
