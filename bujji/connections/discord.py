"""
bujji/connections/discord.py
Discord gateway — requires: pip install discord.py
"""

import sys

LOGO = "🦞"


class DiscordChannel:
    """
    Discord bot gateway.
    Responds to messages in any channel the bot can read.
    Per-channel history is maintained in memory (last 20 messages).
    """

    def __init__(self, token: str, allow_from: list, cfg: dict):
        self.token      = token
        self.allow_from = [str(a) for a in allow_from]
        self.cfg        = cfg
        self.sessions: dict[str, list] = {}  # channel_id -> history

    def run(self) -> None:
        """Start the Discord client (blocking — run in a thread)."""
        try:
            import discord
        except ImportError:
            print(
                "[ERROR] discord.py not installed.\n"
                "        Install it with: pip install discord.py",
                file=sys.stderr,
            )
            return

        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready() -> None:
            print(f"[INFO] Discord logged in as {client.user}", file=sys.stderr)

        @client.event
        async def on_message(message) -> None:
            if message.author == client.user:
                return

            user_id = str(message.author.id)
            if self.allow_from and user_id not in self.allow_from:
                return

            text = message.content.strip()
            if not text:
                return

            chan_id = str(message.channel.id)
            history = list(self.sessions.get(chan_id, []))
            cfg     = self.cfg

            import asyncio

            async with message.channel.typing():
                try:
                    parts: list[str] = []

                    def run_agent() -> str:
                        from bujji.agent import AgentLoop
                        agent = AgentLoop(cfg, send_message_fn=lambda c: parts.append(c))
                        return agent.run(text, history=history, stream=False)

                    result = await asyncio.get_event_loop().run_in_executor(
                        None, run_agent
                    )
                    if result:
                        parts.append(result)

                    reply = "\n".join(parts) or "(no response)"

                    # Split into 2000-char Discord chunks
                    for chunk in [reply[i:i + 2000] for i in range(0, len(reply), 2000)]:
                        await message.channel.send(chunk)

                    history.extend([
                        {"role": "user",      "content": text},
                        {"role": "assistant", "content": reply},
                    ])
                    self.sessions[chan_id] = history[-20:]

                except Exception as e:
                    await message.channel.send(f"⚠️ Error: {e}")
                    print(f"[ERROR] Discord handler: {e}", file=sys.stderr)

        client.run(self.token)