"""
bujji/connections/telegram.py
Telegram gateway — long-polling bot, no webhook required.
Works on any network (NAT, no public IP, old hardware, etc.).
"""

import sys
import threading
import time

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

LOGO = "🦞"


class TelegramChannel:
    """
    Runs a Telegram bot via getUpdates long-polling.

    Per-chat conversation history is kept in memory (last 20 messages)
    so the bot maintains context across multiple messages in the same chat.
    Each incoming message is handled in its own thread so slow LLM calls
    never block the polling loop.
    """

    def __init__(self, token: str, allow_from: list, cfg: dict):
        self.token      = token
        self.allow_from = [str(a) for a in allow_from]
        self.cfg        = cfg
        self.offset     = 0
        self.base_url   = f"https://api.telegram.org/bot{token}"
        self.sessions: dict[str, list] = {}  # chat_id -> message history

    # ── Public ────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the polling loop (blocking — run in a thread)."""
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
        """Send a text message, splitting if it exceeds Telegram's 4096-char limit."""
        for chunk in [text[i:i + 4000] for i in range(0, len(text), 4000)]:
            try:
                self._api("sendMessage", {"chat_id": chat_id, "text": chunk})
            except Exception as e:
                print(f"[WARN] Telegram send error: {e}", file=sys.stderr)

    # ── Private ───────────────────────────────────────────────────────────

    def _api(self, method: str, data: dict = None) -> dict:
        r = _requests.post(
            f"{self.base_url}/{method}",
            json=data or {},
            timeout=30,
        )
        return r.json()

    def _poll_once(self) -> None:
        resp = self._api("getUpdates", {
            "offset":          self.offset,
            "timeout":         20,
            "allowed_updates": ["message"],
        })

        for update in resp.get("result", []):
            self.offset = update["update_id"] + 1
            msg_obj = update.get("message", {})
            chat_id = str(msg_obj.get("chat", {}).get("id", ""))
            from_id = str(msg_obj.get("from", {}).get("id", ""))
            text    = msg_obj.get("text", "").strip()

            if not text or not chat_id:
                continue

            # ── Auth check ──
            if self.allow_from and from_id not in self.allow_from:
                self.send(chat_id, "⛔ Unauthorized.")
                continue

            print(f"[Telegram] {from_id}: {text[:80]}", file=sys.stderr)

            # Snapshot history before spawning thread
            history = list(self.sessions.get(chat_id, []))
            threading.Thread(
                target=self._handle,
                args=(chat_id, text, history),
                daemon=True,
            ).start()

    def _handle(self, chat_id: str, text: str, history: list) -> None:
        """Process one incoming message in a dedicated thread."""
        # Import here to avoid circular imports at module load time
        from bujji.agent import AgentLoop

        try:
            parts: list[str] = []

            def capture(content: str) -> None:
                parts.append(content)

            agent  = AgentLoop(self.cfg, send_message_fn=capture)
            result = agent.run(text, history=history, stream=False)
            if result:
                parts.append(result)

            reply = "\n".join(parts) or "(no response)"
            self.send(chat_id, reply)

            # Update session history (keep last 20 messages = 10 turns)
            history.extend([
                {"role": "user",      "content": text},
                {"role": "assistant", "content": reply},
            ])
            self.sessions[chat_id] = history[-20:]

        except Exception as e:
            self.send(chat_id, f"⚠️ Error: {e}")
            print(f"[ERROR] Telegram handler: {e}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────────
#  SETUP HELPER (used by onboard and setup-telegram commands)
# ─────────────────────────────────────────────────────────────────────────────

def setup_telegram_interactive(cfg: dict) -> None:
    """
    Interactive Telegram configuration wizard.
    Mutates cfg in place; caller is responsible for calling save_config().
    """
    if not _HAS_REQUESTS:
        print("  ⚠️  requests not installed — cannot verify token online.")
        print("  Install it first: pip install requests\n")

    token = input("  Paste your bot token: ").strip()
    if not token:
        print("  [Skipped] No token entered.")
        return

    # ── Verify token ──
    if _HAS_REQUESTS:
        print("  Verifying token...", end="", flush=True)
        try:
            r    = _requests.get(
                f"https://api.telegram.org/bot{token}/getMe", timeout=8
            )
            data = r.json()
            if data.get("ok"):
                bot = data["result"]
                print(f" ✅ Bot: @{bot.get('username')} ({bot.get('first_name')})")
            else:
                print(f" ❌ {data.get('description', 'unknown error')}")
                if input("  Continue anyway? (y/N): ").strip().lower() != "y":
                    return
        except Exception as e:
            print(f" ⚠️  Could not verify ({e}), continuing anyway.")

    # ── Allow-list ──
    raw = input(
        "  Your Telegram user ID(s) (comma-separated, Enter = allow all): "
    ).strip()
    allow_from = [uid.strip() for uid in raw.split(",") if uid.strip()] if raw else []

    if not allow_from:
        print("  ⚠️  allow_from is empty — ANY Telegram user can chat with your bot!")
        if input("  Confirm open access? (y/N): ").strip().lower() != "y":
            uid = input("  Enter your user ID now: ").strip()
            allow_from = [uid] if uid else []

    cfg.setdefault("channels", {})["telegram"] = {
        "enabled":    True,
        "token":      token,
        "allow_from": allow_from,
    }
    label = allow_from if allow_from else "everyone"
    print(f"  ✅ Telegram configured  (allow_from: {label})")
    print("  Run 'python main.py gateway' to start the bot.")