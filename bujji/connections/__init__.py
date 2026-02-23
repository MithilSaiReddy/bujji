"""
bujji/connections — Messaging gateway channels.

Available channels:
    TelegramChannel    Long-polling Telegram bot (requires: requests)
    DiscordChannel     Discord bot             (requires: pip install discord.py)

Adding a new channel
─────────────────────
1. Create bujji/connections/slack.py  (or matrix.py, whatsapp.py, …)
2. Implement a class with a .run() method (blocking, designed to run in a thread)
3. Wire it up in main.py cmd_gateway() — same pattern as Telegram/Discord.

Channels are imported lazily inside cmd_gateway() so that missing optional
dependencies (like discord.py) never cause an ImportError on startup.
"""


def get_telegram_channel():
    """Lazy import — only loads when actually needed."""
    from bujji.connections.telegram import TelegramChannel
    return TelegramChannel


def get_discord_channel():
    """Lazy import — only loads when actually needed."""
    from bujji.connections.discord import DiscordChannel
    return DiscordChannel


__all__ = [
    "get_telegram_channel",
    "get_discord_channel",
]