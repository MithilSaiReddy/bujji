"""
bujji/session.py  —  v2  (NEW)

SessionManager — keeps one AgentLoop alive per user/channel.

Problem with v1
───────────────
The Telegram handler called `AgentLoop(cfg)` on every single message.
That means:
  • New LLMProvider object every time (no warm state)
  • Skills re-read from disk on each message even if unchanged
  • "History" was just a list passed around by the caller — easy to lose

SessionManager fixes all of this by mapping a session_id → AgentLoop
and keeping those objects alive for the lifetime of the gateway process.

Usage
─────
mgr = SessionManager(cfg)

# In Telegram handler:
agent = mgr.get("telegram:123456789")   # created once, reused forever
result = agent.run(text, history=mgr.history("telegram:123456789"))
mgr.append("telegram:123456789", "user", text)
mgr.append("telegram:123456789", "assistant", result)
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

from bujji.agent import AgentLoop

class SessionManager:
    """
    Thread-safe registry of AgentLoop instances keyed by session_id.

    session_id convention:
        "cli"                   → interactive CLI
        "telegram:<chat_id>"    → one Telegram chat
        "discord:<channel_id>"  → one Discord channel
        "web:<uuid>"            → one browser tab
    """

    MAX_HISTORY = 40   # messages (20 turns)

    def __init__(self, cfg: dict):
        self.cfg      = cfg
        self._agents:  dict[str, AgentLoop]   = {}
        self._history: dict[str, list]        = {}
        self._lock = threading.Lock()

    # ── Agents ────────────────────────────────────────────────────────────

    def get(
        self,
        session_id:      str,
        send_message_fn: Optional[Callable[[str], None]] = None,
        callbacks:       Optional[dict]                  = None,
    ) -> AgentLoop:
        """Return the AgentLoop for this session, creating it if needed."""
        with self._lock:
            if session_id not in self._agents:
                self._agents[session_id] = AgentLoop(
                    self.cfg,
                    send_message_fn = send_message_fn,
                    callbacks       = callbacks or {},
                )
            return self._agents[session_id]

    def update_callbacks(self, session_id: str, callbacks: dict) -> None:
        """
        Attach new callbacks to an existing session (e.g. when a new web
        request comes in for the same session_id).
        """
        with self._lock:
            if session_id in self._agents:
                self._agents[session_id].callbacks = callbacks

    def close(self, session_id: str) -> None:
        """Remove a session and its history."""
        with self._lock:
            self._agents.pop(session_id, None)
            self._history.pop(session_id, None)

    # ── History ───────────────────────────────────────────────────────────

    def history(self, session_id: str) -> list:
        """Return a copy of the message history for this session."""
        with self._lock:
            return list(self._history.get(session_id, []))

    def append(self, session_id: str, role: str, content: str) -> None:
        """Append one message to the session history (auto-trims to MAX_HISTORY)."""
        with self._lock:
            hist = self._history.setdefault(session_id, [])
            hist.append({"role": role, "content": content})
            if len(hist) > self.MAX_HISTORY:
                # Keep system message if present, then trim oldest turns
                if hist and hist[0]["role"] == "system":
                    self._history[session_id] = [hist[0]] + hist[-(self.MAX_HISTORY - 1):]
                else:
                    self._history[session_id] = hist[-self.MAX_HISTORY:]

    def clear(self, session_id: str) -> None:
        """Wipe history for a session without destroying the agent."""
        with self._lock:
            self._history[session_id] = []

    def sessions(self) -> list[str]:
        """Return list of active session IDs."""
        with self._lock:
            return list(self._agents)
