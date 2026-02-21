# 🦞 bujji v2

**Ultra-lightweight personal AI assistant** — runs on a Raspberry Pi, an old Mac, anywhere Python runs.
Inspired by [PicoClaw](https://github.com/sipeed/picoclaw) by Sipeed. Named after the loyal robot from *Kalki 2898 AD*.

---

## ✨ What's new in v2

| Area | v1 | v2 |
|---|---|---|
| **Tools** | `_ctx` dict injection, silent failures | `ToolContext` dataclass, structured errors fed back to LLM |
| **Hot-reload** | Restart required for new tools/skills | Drop a file → picked up instantly |
| **Memory** | Full overwrite (dangerous!) | `append_user_memory` + atomic writes + `.bak` backups |
| **Sessions** | New `AgentLoop` per message | `SessionManager` — one agent per chat, history persists |
| **Skills** | Raw Markdown dump, no reload | Per-file mtime tracking, clean structured injection |
| **Streaming** | Hard-wired to stdout | `on_token` / `on_tool_start` / `on_tool_done` callbacks |
| **Web UI** | ❌ None | ✅ `python main.py serve` → opens http://localhost:7337 |
| **File ops** | Non-atomic writes | Atomic writes via `.tmp → rename` |
| **Output truncation** | Hard cut | Smart: head (75%) + tail (25%) — LLM sees both ends |

---

## 🚀 Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/bujji.git
cd bujji
pip install requests        # only hard dependency
python main.py onboard      # configure your LLM provider
python main.py serve        # open web UI → http://localhost:7337
```

Or for terminal purists:
```bash
python main.py agent -m "What's my disk usage?"
python main.py agent        # interactive chat
```

---

## 🗺️ Architecture

```
bujji/
├── main.py                     CLI entry point (5 commands)
├── bujji/
│   ├── agent.py                AgentLoop + HeartbeatService + CronService
│   ├── llm.py                  OpenAI-compatible LLM client (streaming + retry)
│   ├── session.py              ← NEW: SessionManager (one AgentLoop per user)
│   ├── server.py               ← NEW: Web UI HTTP server (zero extra deps)
│   ├── config.py               Config load/save, provider registry
│   ├── identity.py             SOUL/IDENTITY/USER/AGENT.md management
│   ├── tools/
│   │   ├── base.py             ToolContext + register_tool + ToolRegistry (v2)
│   │   ├── shell.py            exec (shell command runner)
│   │   ├── web.py              web_search (Brave API)
│   │   ├── file_ops.py         read/write/append/list/delete (atomic writes)
│   │   ├── memory.py           read/append/update USER.md (safe, atomic)
│   │   └── utils.py            get_time, message
│   └── connections/
│       ├── telegram.py         Telegram bot (uses SessionManager)
│       └── discord.py          Discord bot  (uses SessionManager)
└── ui/
    └── index.html              Web UI (single HTML, zero dependencies)
```

---

## 🛠️ Extending bujji

### Add a Tool (5 lines)
```python
# bujji/tools/weather.py
from bujji.tools.base import ToolContext, register_tool

@register_tool(
    description="Get current weather for a city.",
    parameters={"type":"object","required":["city"],
                "properties":{"city":{"type":"string","description":"City name"}}}
)
def get_weather(city: str, _ctx: ToolContext = None) -> str:
    return f"Weather in {city}: sunny 25°C"   # replace with real API call
```
→ Drop the file. Bujji picks it up on the next message. No restart.

### Add a Skill (pure Markdown)
```
workspace/skills/python_expert/SKILL.md
```
```markdown
# Python Expert

You are a Python expert. Always:
- Prefer list comprehensions over map/filter
- Use f-strings instead of .format()
- Suggest type hints for function signatures
```
→ Save the file. Active immediately. No restart.

### Add a Connection
1. Create `bujji/connections/slack.py`
2. Implement a class with `.run()` (blocking, designed for a thread)
3. Wire it up in `main.py` `cmd_gateway()` — same pattern as Telegram

---

## 📋 Commands

| Command | Description |
|---|---|
| `python main.py onboard` | First-time setup wizard |
| `python main.py serve` | **Web UI** → http://localhost:7337 |
| `python main.py agent` | Interactive terminal chat |
| `python main.py agent -m "..."` | Single message, non-interactive |
| `python main.py gateway` | Start Telegram + Discord bots |
| `python main.py setup-telegram` | Configure Telegram |
| `python main.py status` | Health check |

---

## 🗂️ Workspace files

| File | Who writes it | Purpose |
|---|---|---|
| `SOUL.md` | You | Core values and ethics |
| `IDENTITY.md` | You | Name, personality, tone |
| `USER.md` | bujji + you | Persistent memory about you |
| `AGENT.md` | bujji | Active tools and capabilities |
| `HEARTBEAT.md` | You | Periodic tasks (runs every 30 min) |
| `cron/jobs.json` | You | Scheduled tasks with intervals |
| `skills/NAME/SKILL.md` | You | Domain-specific instructions |

---

## 🛡️ License

MIT — fork it, break it, improve it.

---

*"Small agents that run anywhere are more powerful than big agents that need the cloud."*
