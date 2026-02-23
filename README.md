<div align="center">

# bujji

**A minimal, hackable personal AI agent that runs anywhere Python runs.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Core Dependency](https://img.shields.io/badge/core%20dep-requests-brightgreen)](https://pypi.org/project/requests/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/MithilSaiReddy/bujji/pulls)

Named after the loyal robot companion from *Kalki 2898 AD*.  
Inspired by [PicoClaw](https://github.com/sipeed/picoclaw) by Sipeed.

[Quick Start](#-quick-start) · [Architecture](#-architecture) · [Marketplace](#-marketplace) · [Extending Bujji](#-extending-bujji) · [Contributing](#-contributing)

</div>

---

## What is bujji?

Bujji is a self-hosted, open-source AI agent framework. It connects any OpenAI-compatible LLM to a set of tools (shell, web, files, memory) and runs as a web app, a terminal chat, a Telegram bot, or a Discord bot — all from a single codebase with minimal setup.

The core philosophy: **a small agent you own and understand beats a large agent you rent and don't**.

- **Runs anywhere** — a Raspberry Pi, an old laptop, a $10 board, a cloud VM.
- **Minimal dependencies** — the core agent, web UI, Telegram, and all built-in tools need only `pip install requests`. Optional features like Discord add one extra package. No LangChain, no vector DB, no Docker.
- **Hot-reload everything** — drop a tool file or a skill file and it's live on the next message. No restart.
- **You own your data** — all memory, config, and history lives on your machine as plain files.
- **Works with any LLM** — OpenAI, Anthropic, Google, Groq, Mistral, DeepSeek, Ollama (local), or any OpenAI-compatible endpoint via OpenRouter.

---

## Table of Contents

- [Quick Start](#-quick-start)
- [Features](#-features)
- [Architecture](#-architecture)
- [Configuration](#-configuration)
- [Commands](#-commands)
- [The Workspace](#-the-workspace)
- [Marketplace](#-marketplace)
- [Extending Bujji](#-extending-bujji)
- [LLM Providers](#-llm-providers)
- [Connections](#-connections-telegram--discord)
- [Contributing](#-contributing)
- [Roadmap](#-roadmap)
- [License](#-license)

---

## ⚡ Quick Start

```bash
# 1. Clone
git clone https://github.com/MithilSaiReddy/bujji.git
cd bujji

# 2. Install the core dependency
pip install requests

# 3. Configure your LLM provider (interactive wizard)
python main.py onboard

# 4. Launch
python main.py serve        # Web UI  →  http://localhost:7337
# or
python main.py agent        # Terminal chat
```

That's it for the core setup. Optional features (Discord, web search) need one extra step each — covered below.

### Dependencies at a glance

| Feature | Extra install needed |
|---|---|
| Core agent, web UI, terminal chat | *(none — stdlib only)* |
| Telegram bot | *(none — uses `requests`)* |
| Web search | *(none — uses `requests`)* + [Brave API key](https://brave.com/search/api) (free, 2k queries/month) |
| Discord bot | `pip install discord.py` |
| Future marketplace tools (Gmail, Notion…) | Varies per tool — each prints a clear install message if missing |

---

## ✨ Features

### Core Agent
- **Agentic tool-use loop** — the LLM reasons, calls tools, sees results, and loops until the task is done (up to 20 iterations by default).
- **Streaming responses** — tokens stream in real time via the web UI, terminal, or Telegram.
- **Structured error feedback** — every tool failure becomes a `[TOOL ERROR]` message the LLM can read and recover from, instead of crashing silently.

### Memory
- **Persistent USER.md** — bujji remembers things about you across sessions: your name, projects, preferences, anything you tell it.
- **Atomic writes** — memory updates use `tmp → rename` so a crash mid-write never corrupts your file.
- **Auto-backup** — `USER.md.bak` is saved before every update.
- **Append-only by default** — new facts are appended, not overwritten. The LLM can't accidentally erase your memory.

### Skills
- **Markdown-based skills** — drop a `SKILL.md` file in `workspace/skills/<name>/` to give bujji domain-specific instructions.
- **Hot-reload** — changed skill files are picked up on the next message with mtime tracking. No restart.

### Tools (built-in)
| Tool | Description |
|---|---|
| `exec` | Run shell commands |
| `web_search` | Search the web via Brave API *(requires free Brave API key — [get one here](https://brave.com/search/api))* |
| `read_file` / `write_file` / `append_file` | File operations (atomic writes) |
| `list_files` / `delete_file` | Directory listing and deletion |
| `read_user_memory` | Read persistent USER.md |
| `append_user_memory` | Add new facts to memory without erasing existing |
| `update_user_memory` | Full USER.md rewrite (for restructuring) |
| `get_time` | Current date and time |
| `message` | Push a message to the user mid-task |

> **Web search setup:** `web_search` uses the [Brave Search API](https://brave.com/search/api) — free tier is 2,000 queries/month, no extra Python package needed. Set it up during `python main.py onboard` or add it later in the web UI. Without a key, the tool gracefully returns a manual search URL instead of erroring.

### Background Services
- **Heartbeat** — reads `HEARTBEAT.md` every 30 minutes and runs its contents as an agent prompt. Use it for automated tasks like disk checks, weather summaries, or journal entries.
- **Cron** — `cron/jobs.json` schedules tasks at any interval. Define a prompt, set an interval in minutes, and bujji runs it automatically.

### Interfaces
- **Web UI** — single-file HTML interface, no Node.js, no build step, served by bujji itself.
- **Terminal** — interactive `--stream` chat or single `-m "message"` invocations.
- **Telegram** — full bot with per-user session isolation and `allow_from` whitelist. Needs only `requests`.
- **Discord** — per-channel sessions with the same isolation model. Requires `pip install discord.py`.

---

## 🏗 Architecture

```
bujji/
├── main.py                     CLI entry point — 6 commands
│
├── bujji/
│   ├── agent.py                AgentLoop · HeartbeatService · CronService
│   ├── llm.py                  OpenAI-compatible LLM client (streaming + retry)
│   ├── session.py              SessionManager — one AgentLoop per user/channel
│   ├── server.py               Pure-Python HTTP + SSE server (zero extra deps)
│   ├── config.py               Config schema, provider registry, load/save
│   ├── identity.py             SOUL / IDENTITY / USER / AGENT.md management
│   │
│   ├── tools/
│   │   ├── base.py             @register_tool decorator · ToolContext · ToolRegistry
│   │   ├── shell.py            exec
│   │   ├── web.py              web_search
│   │   ├── file_ops.py         read / write / append / list / delete
│   │   ├── memory.py           read / append / update USER.md
│   │   └── utils.py            get_time, message
│   │
│   └── connections/
│       ├── telegram.py         Telegram bot (long-polling)
│       └── discord.py          Discord bot
│
├── ui/
│   └── index.html              Single-file web UI — no build step
│
└── workspace/                  Your personal agent workspace
    ├── SOUL.md                 Core values and ethics
    ├── IDENTITY.md             Name, personality, purpose
    ├── USER.md                 Persistent memory about you
    ├── AGENT.md                Active tools and capabilities
    ├── HEARTBEAT.md            Periodic background tasks
    ├── skills/                 Drop SKILL.md files here
    └── cron/                   jobs.json for scheduled tasks
```

### How a message flows through bujji

```
User message
     │
     ▼
SessionManager.get(session_id)
     │  (creates AgentLoop on first contact, reuses after)
     ▼
AgentLoop.run(message, history)
     │
     ├─ Rebuilds system prompt (reads SOUL/IDENTITY/USER/AGENT.md + skills)
     │
     ├─ LLMProvider.chat(messages, tools_schema, stream=True)
     │       ├── tokens streamed via on_token callback → UI / terminal
     │       └── tool_calls assembled from SSE deltas
     │
     ├─ For each tool_call:
     │       ├── ToolRegistry.call(name, args)
     │       │       ├── hot-reload check (mtime scan)
     │       │       ├── inject ToolContext
     │       │       ├── execute function
     │       │       └── smart-truncate output (75% head + 25% tail)
     │       └── append tool result to messages
     │
     └─ Loop until no tool_calls → return final text
```

---

## ⚙️ Configuration

Config lives at `~/.bujji/config.json` and is created by `python main.py onboard`.

```json
{
  "agents": {
    "defaults": {
      "workspace":             "~/.bujji/workspace",
      "model":                 "gpt-4o-mini",
      "max_tokens":            8192,
      "temperature":           0.7,
      "max_tool_iterations":   20,
      "restrict_to_workspace": false,
      "max_tool_output_chars": 8000
    }
  },
  "providers": {
    "openrouter": {
      "api_key":  "sk-...",
      "api_base": "https://openrouter.ai/api/v1"
    }
  },
  "channels": {
    "telegram": { "enabled": false, "token": "", "allow_from": [] },
    "discord":  { "enabled": false, "token": "", "allow_from": [] }
  },
  "tools": {
    "web": {
      "search": { "api_key": "", "max_results": 5 }
    }
  }
}
```

You can also edit everything from the web UI at `http://localhost:7337`.

---

## 📋 Commands

| Command | Description |
|---|---|
| `python main.py onboard` | First-time setup wizard — configure LLM, workspace, Telegram |
| `python main.py serve` | Web UI at `http://localhost:7337` |
| `python main.py serve --port 8080` | Custom port |
| `python main.py agent` | Interactive terminal chat |
| `python main.py agent -m "What's my disk usage?"` | Single message, non-interactive |
| `python main.py agent --no-stream` | Disable streaming (useful for piping output) |
| `python main.py gateway` | Start Telegram + Discord bots + heartbeat + cron |
| `python main.py setup-telegram` | Configure Telegram bot interactively |
| `python main.py status` | Health check — provider, tools, channels |

---

## 🗂 The Workspace

The workspace (`~/.bujji/workspace/` by default) is where bujji's "mind" lives. Every file is plain Markdown or JSON — readable, editable, and version-controllable.

### Identity files

| File | Written by | Purpose |
|---|---|---|
| `SOUL.md` | You | Core values, ethics, and personality traits. Bujji reads this on every message. |
| `IDENTITY.md` | You | Name, description, purpose, capabilities. |
| `USER.md` | Bujji + you | Persistent memory about you. Appended automatically. Never overwritten. |
| `AGENT.md` | Bujji | Self-description of active tools and current capabilities. |

### Automation files

| File | Format | Purpose |
|---|---|---|
| `HEARTBEAT.md` | Markdown task list | Runs every 30 minutes as an agent prompt |
| `cron/jobs.json` | JSON array | Scheduled tasks with intervals and last-run timestamps |

**Example HEARTBEAT.md:**
```markdown
- Check disk space on /. If above 80%, append a warning to USER.md.
- Append today's date and a one-line summary of the weather to journal.md.
```

**Example cron/jobs.json:**
```json
[
  {
    "name": "daily-news",
    "prompt": "Search for today's top AI news and save a summary to news.md",
    "interval_minutes": 1440,
    "last_run": null
  }
]
```

### Skills

Drop a Markdown file at `workspace/skills/<skill-name>/SKILL.md`. Bujji reads it on the next message — no restart.

```markdown
# Python Expert

You are a Python expert. Always:
- Prefer list comprehensions over map/filter
- Use f-strings instead of .format()
- Suggest type hints for function signatures
- Recommend dataclasses for structured data
```

---

## 🛒 Marketplace

The bujji marketplace lets you install community-built skills, tools, and connections without writing any code.

### Skills Marketplace *(available now)*

Browse and install skills directly from the web UI. A skill is a Markdown file with instructions for a specific domain — Python, SQL, writing, DevOps, etc.

**Installing a skill from the marketplace:**
1. Open `http://localhost:7337`
2. Navigate to the Marketplace tab
3. Click Install on any skill
4. It's live immediately — no restart

**Publishing a skill:**
```
workspace/skills/my-skill/SKILL.md
```
Skills are plain Markdown files. Anyone can publish one.

---

### Channels Marketplace *(coming soon)*

Install messaging channel integrations beyond Telegram and Discord.

**Planned channels:**
- **Slack** — respond in channels and DMs
- **Linear** — turn Linear issues into agent tasks
- **WhatsApp** — via WhatsApp Business API
- **Email** — IMAP/SMTP polling agent
- *More contributed by the community*

A channel integration is a single Python file dropped into `bujji/connections/`. Each channel may require its own pip package (e.g. `slack-sdk` for Slack) — installed only when you actually use that channel, never forced on everyone.

---

### Tools Marketplace *(coming soon)*

Install tool integrations that give bujji access to external services.

**Planned tools:**
- **Gmail** — read, send, search emails
- **Notion** — read and write pages and databases
- **GitHub** — open issues, read PRs, search code
- **Google Calendar** — read and create events
- **Jira** — create and update tickets
- *More contributed by the community*

A tool integration is a Python file with `@register_tool`-decorated functions, dropped into `bujji/tools/`. Hot-reloaded automatically. Each marketplace tool may need its own pip package — installed on demand, with a clear error message if missing. The core agent is never affected.

---

## 🔧 Extending Bujji

### Add a custom tool

Create any `.py` file in `bujji/tools/`:

```python
# bujji/tools/weather.py
from bujji.tools.base import ToolContext, register_tool

@register_tool(
    description="Get current weather for a city.",
    parameters={
        "type": "object",
        "required": ["city"],
        "properties": {
            "city": {"type": "string", "description": "City name"}
        }
    }
)
def get_weather(city: str, _ctx: ToolContext = None) -> str:
    # Replace with a real weather API call
    return f"Weather in {city}: sunny, 25°C"
```

Save the file. Bujji picks it up on the next message. No restart, no registration step.

The `_ctx: ToolContext` parameter is optional. If your function accepts it, bujji injects it automatically. It gives you access to `cfg`, `workspace`, and callbacks.

### Add a custom skill

```
workspace/skills/sql-expert/SKILL.md
```

```markdown
# SQL Expert

You are an expert in SQL and database design. Always:
- Prefer CTEs over nested subqueries for readability
- Suggest indexes when queries involve large tables
- Use parameterized queries in code examples to prevent SQL injection
- Mention the target database (PostgreSQL, MySQL, SQLite) when syntax differs
```

Save and it's active. Delete the file to deactivate it.

### Add a custom connection

1. Create `bujji/connections/slack.py`
2. Implement a class with a `.run()` method (blocking, designed for a daemon thread)
3. Wire it into `main.py`'s `cmd_gateway()` — follow the Telegram pattern

```python
# bujji/connections/slack.py
class SlackChannel:
    def __init__(self, token: str, cfg: dict, mgr: SessionManager):
        ...

    def run(self):
        # polling / event loop here
        ...
```

---

## 🤖 LLM Providers

Bujji works with any OpenAI-compatible API. Run `python main.py onboard` to configure interactively, or edit `~/.bujji/config.json` directly.

| Provider | Free Tier | Notes |
|---|---|---|
| [OpenRouter](https://openrouter.ai/keys) | ✅ Yes | Access to all major models via one key |
| [OpenAI](https://platform.openai.com/api-keys) | — | gpt-4o-mini is cheapest |
| [Anthropic](https://console.anthropic.com/settings/keys) | — | Claude Haiku is fastest |
| [Groq](https://console.groq.com/keys) | ✅ Yes | Very fast inference, free tier |
| [Google AI Studio](https://aistudio.google.com/app/apikey) | ✅ Yes | Gemini 2.0 Flash, free tier |
| [Mistral](https://console.mistral.ai/) | — | Small model is affordable |
| [DeepSeek](https://platform.deepseek.com/) | — | Affordable, strong reasoning |
| Ollama | ✅ Fully local | No API key. `ollama serve` + pick a model |

**To use Ollama (fully offline):**
```bash
ollama serve
# then in bujji onboard, pick "ollama" and model e.g. "llama3.2"
```

---

## 🔌 Connections (Telegram + Discord)

### Telegram

```bash
python main.py setup-telegram
python main.py gateway
```

Use `allow_from` in config to whitelist specific chat IDs. Without a whitelist, anyone who finds your bot can use it.

### Discord

```bash
pip install discord.py
```

Add your Discord bot token to `~/.bujji/config.json`:

```json
"channels": {
  "discord": {
    "enabled": true,
    "token": "your-discord-bot-token",
    "allow_from": ["channel_id_1", "channel_id_2"]
  }
}
```

Then: `python main.py gateway`

> If `discord.py` is not installed, bujji will print a clear error and skip the Discord connection — Telegram and the web UI continue working normally.

---

## 🤝 Contributing

Contributions are welcome — especially new tools, skills, and connection integrations.

### Getting started

```bash
git clone https://github.com/MithilSaiReddy/bujji.git
cd bujji
pip install requests
python main.py onboard
```

### What to contribute

- **Tools** — integrations with external services (`bujji/tools/`)
- **Skills** — Markdown instruction sets for domains (Python, SQL, writing, DevOps, etc.)
- **Connections** — messaging channel integrations (`bujji/connections/`)
- **Bug fixes** — especially around edge cases in streaming, retry, or memory handling
- **Documentation** — usage examples, tutorials, translated docs

### Guidelines

- Keep the core lean. New features inside `bujji/` core (agent, server, session, llm) must not add pip dependencies beyond `requests`. The core must stay runnable with `pip install requests` only.
- Tool and connection integrations may add optional dependencies — but they must import them lazily and print a clear, actionable install message if the package is missing. They must never crash the agent.
- Prefer small, focused commits. One feature or fix per PR.
- Test with at least one provider (Ollama works fully offline — no API key needed).
- Follow the existing code style: type hints, docstrings on public classes, `[TOOL ERROR]` for tool failures.

### Submitting

1. Fork the repo
2. Create a branch: `git checkout -b feature/gmail-tool`
3. Commit your changes
4. Open a pull request with a description of what it does and how to test it

---

## 🗺 Roadmap

### Now
- [x] Core agent loop with tool-use
- [x] Hot-reload tools and skills (no restart)
- [x] Persistent memory (USER.md, atomic writes)
- [x] Web UI with SSE streaming
- [x] Session management (per-user agent isolation)
- [x] Telegram + Discord connections
- [x] Heartbeat and cron background services
- [x] Skills marketplace

### Next
- [ ] Channels marketplace (Slack, Linear, Email, WhatsApp)
- [ ] Tools marketplace (Gmail, Notion, GitHub, Google Calendar)
- [ ] Multi-agent support (bujji coordinating sub-agents)
- [ ] Voice input/output support
- [ ] Mobile web UI improvements

### Future
- [ ] Plugin SDK — standardized packaging for marketplace submissions
- [ ] RAG over local documents (still zero-cloud, vector index on device)
- [ ] Skill / tool versioning and auto-update

---

## 📄 License

MIT — fork it, modify it, use it commercially, run it offline.  
See [LICENSE](LICENSE) for the full text.

---

<div align="center">

*"Small agents that run anywhere are more powerful than big agents that need the cloud."*

**[⭐ Star on GitHub](https://github.com/MithilSaiReddy/bujji)** · **[Report a Bug](https://github.com/MithilSaiReddy/bujji/issues)** · **[Start a Discussion](https://github.com/MithilSaiReddy/bujji/discussions)**

</div>