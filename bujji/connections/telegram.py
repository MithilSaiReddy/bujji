"""
bujji/connections/telegram.py  —  v2

Key improvements:
• Uses SessionManager — one AgentLoop per chat_id (not a new one per message)
  → skills/tools stay warm, history is properly managed
• send_message_fn wired in — agent can push async notifications
• Message splitting at 4096 chars
"""
from __future__ import annotations

import sys
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bujji.session import SessionManager

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

LOGO = "🦞"

class TelegramChannel:

    def __init__(self, token: str, allow_from: list, cfg: dict, mgr: "SessionManager"):
        self.token      = token
        self.allow_from = [str(a) for a in allow_from]
        self.cfg        = cfg
        self.mgr        = mgr
        self.offset     = 0
        self.base_url   = f"https://api.telegram.org/bot{token}"

    def run(self) -> None:
        if not _HAS_REQUESTS:
            print("[ERROR] requests not installed: pip install requests", file=sys.stderr)
            return
        print("[INFO] Telegram channel started (long polling)", file=sys.stderr)
        while True:
            try:
                self._poll_once()
            except Exception as e:
                print(f"[WARN] Telegram poll error: {e}", file=sys.stderr)
                time.sleep(5)

    def send(self, chat_id: str, text: str) -> None:
        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
            try:
                self._api("sendMessage", {"chat_id": chat_id, "text": chunk})
            except Exception as e:
                print(f"[WARN] Telegram send error: {e}", file=sys.stderr)

    def _api(self, method: str, data: dict = None) -> dict:
        r = _requests.post(f"{self.base_url}/{method}", json=data or {}, timeout=30)
        return r.json()

    def _poll_once(self) -> None:
        resp = self._api("getUpdates", {
            "offset": self.offset, "timeout": 20, "allowed_updates": ["message"]
        })
        for update in resp.get("result", []):
            self.offset  = update["update_id"] + 1
            msg_obj = update.get("message", {})
            chat_id = str(msg_obj.get("chat", {}).get("id", ""))
            from_id = str(msg_obj.get("from", {}).get("id", ""))
            text    = msg_obj.get("text", "").strip()
            if not text or not chat_id:
                continue
            if self.allow_from and from_id not in self.allow_from:
                self.send(chat_id, "⛔ Unauthorized.")
                continue
            print(f"[Telegram] {from_id}: {text[:80]}", file=sys.stderr)
            history = self.mgr.history(f"telegram:{chat_id}")
            threading.Thread(
                target=self._handle, args=(chat_id, text, history), daemon=True
            ).start()

    def _handle(self, chat_id: str, text: str, history: list) -> None:
        session_id = f"telegram:{chat_id}"
        parts: list[str] = []

        def send_msg(content: str) -> None:
            parts.append(content)
            self.send(chat_id, content)

        try:
            agent  = self.mgr.get(session_id, send_message_fn=send_msg)
            result = agent.run(text, history=history, stream=False)
            if result:
                parts.append(result)

            reply = "\n".join(parts) or "(no response)"
            if result:
                self.send(chat_id, result)

            self.mgr.append(session_id, "user",      text)
            self.mgr.append(session_id, "assistant", reply)

        except Exception as e:
            self.send(chat_id, f"⚠️ Error: {e}")
            print(f"[ERROR] Telegram handler: {e}", file=sys.stderr)

# ── Setup wizard ──────────────────────────────────────────────────────────────

def setup_telegram_interactive(cfg: dict) -> None:
    if not _HAS_REQUESTS:
        print("  ⚠️  requests not installed — pip install requests")
        return

    token = input("  Paste your bot token: ").strip()
    if not token:
        print("  [Skipped]")
        return

    print("  Verifying token…", end="", flush=True)
    try:
        r    = _requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=8)
        data = r.json()
        if data.get("ok"):
            bot = data["result"]
            print(f" ✅ @{bot.get('username')} ({bot.get('first_name')})")
        else:
            print(f" ❌ {data.get('description')}")
            if input("  Continue anyway? (y/N): ").strip().lower() != "y":
                return
    except Exception as e:
        print(f" ⚠️  ({e}), continuing.")

    raw        = input("  Your Telegram user ID(s) comma-separated (Enter = allow all): ").strip()
    allow_from = [u.strip() for u in raw.split(",") if u.strip()] if raw else []

    if not allow_from:
        print("  ⚠️  allow_from empty — ANY Telegram user can talk to your bot!")
        if input("  Confirm open access? (y/N): ").strip().lower() != "y":
            uid = input("  Enter your user ID now: ").strip()
            allow_from = [uid] if uid else []

    cfg.setdefault("channels", {})["telegram"] = {
        "enabled":    True,
        "token":      token,
        "allow_from": allow_from,
    }
    print(f"  ✅ Telegram configured (allow_from: {allow_from or 'everyone'})")
