"""
bujji/connections/discord.py  —  v2
Uses SessionManager for persistent per-channel history.
"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bujji.session import SessionManager

LOGO = "🦞"

class DiscordChannel:

    def __init__(self, token: str, allow_from: list, cfg: dict, mgr: "SessionManager"):
        self.token      = token
        self.allow_from = [str(a) for a in allow_from]
        self.cfg        = cfg
        self.mgr        = mgr

    def run(self) -> None:
        try:
            import discord
        except ImportError:
            print("[ERROR] discord.py not installed — pip install discord.py", file=sys.stderr)
            return

        intents = discord.Intents.default()
        intents.message_content = True
        client  = discord.Client(intents=intents)

        @client.event
        async def on_ready():
            print(f"[INFO] Discord logged in as {client.user}", file=sys.stderr)

        @client.event
        async def on_message(message):
            if message.author == client.user:
                return
            user_id = str(message.author.id)
            if self.allow_from and user_id not in self.allow_from:
                return
            text = message.content.strip()
            if not text:
                return

            chan_id    = str(message.channel.id)
            session_id = f"discord:{chan_id}"
            history    = self.mgr.history(session_id)

            import asyncio

            async with message.channel.typing():
                try:
                    parts: list[str] = []

                    def run_agent() -> str:
                        agent = self.mgr.get(
                            session_id,
                            send_message_fn=lambda c: parts.append(c),
                        )
                        return agent.run(text, history=history, stream=False)

                    result = await asyncio.get_event_loop().run_in_executor(None, run_agent)
                    if result:
                        parts.append(result)

                    reply = "\n".join(parts) or "(no response)"
                    for chunk in [reply[i:i+2000] for i in range(0, len(reply), 2000)]:
                        await message.channel.send(chunk)

                    self.mgr.append(session_id, "user",      text)
                    self.mgr.append(session_id, "assistant", reply)

                except Exception as e:
                    await message.channel.send(f"⚠️ Error: {e}")
                    print(f"[ERROR] Discord handler: {e}", file=sys.stderr)

        client.run(self.token)
