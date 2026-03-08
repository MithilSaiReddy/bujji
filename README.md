<div align="center">

```
▗▄▄▖ ▗▖ ▗▖   ▗▖   ▗▖▗▄▄▄▖
▐▌ ▐▌▐▌ ▐▌   ▐▌   ▐▌  █  
▐▛▀▚▖▐▌ ▐▌   ▐▌   ▐▌  █  
▐▙▄▞▘▝▚▄▞▘▗▄▄▞▘▗▄▄▞▘▗▄█▄▖
```

**A minimal, hackable personal AI agent that runs anywhere Python runs.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Core Dependency](https://img.shields.io/badge/core%20dep-requests-brightgreen)](https://pypi.org/project/requests/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/MithilSaiReddy/bujji/pulls)

Named after the loyal robot companion from *Kalki 2898 AD*.  
Inspired by [PicoClaw](https://github.com/sipeed/picoclaw) by Sipeed.

[Quick Start](#-quick-start) · [How It Works](#-how-it-works) · [Adding Tools](#-adding-tools) · [Sub-Agents](#-sub-agents) · [Configuration](#-configuration) · [LLM Providers](#-llm-providers) · [Contributing](#-contributing)

</div>

---

## What is bujji?

Bujji is a self-hosted AI agent framework. It connects any OpenAI-compatible LLM to a set of tools — shell, web, files, memory, and whatever else you wire up — and runs as a web app, a terminal chat, a Telegram bot, or a Discord bot, all from a single codebase with minimal setup.

The core philosophy: **a small agent you own and understand beats a large agent you rent and don't.**

- **Runs anywhere** — a Raspberry Pi, an old laptop, a $10 board, a cloud VM.
- **Minimal dependencies** — the core agent, web UI, Telegram, and all built-in tools need only `pip install requests`. No LangChain, no vector DB, no Docker.
- **Hot-reload everything** — drop a `.py` file into `bujji/tools/` and it's live on the next message. No restart.
- **You own your data** — all memory, config, and history lives on your machine as plain files.
- **Works with any LLM** — OpenAI, Anthropic, Google, Groq, Mistral, DeepSeek, Ollama (local), or any OpenAI-compatible endpoint.

---

## Table of Contents

- [Quick Start](#-quick-start)
- [How It Works](#-how-it-works)
- [Adding Tools](#-adding-tools)
  - [Scaffold a tool in 30 seconds](#scaffold-a-tool-in-30-seconds)
  - [The Basics](#the-basics)
  - [Parameters](#parameters)
  - [Credentials](#credentials)
  - [HTTP APIs](#http-apis)
  - [Full Example — Weather API](#full-example--weather-api)
  - [Error Handling](#error-handling)
  - [Optional Dependencies](#optional-dependencies)
  - [Tool Checklist](#tool-checklist)
- [Sub-Agents](#-sub-agents)
- [Built-in Tools](#-built-in-tools)
- [Skills](#-skills)
- [Background Automation](#-background-automation)
- [Configuration](#-configuration)
- [Commands](#-commands)
- [The Workspace](#-the-workspace)
- [LLM Providers](#-llm-providers)
- [Channels — Telegram & Discord](#-channels--telegram--discord)
- [Architecture](#-architecture)
- [Contributing](#-contributing)
- [Roadmap](#-roadmap)
- [License](#-license)

---

## ⚡ Quick Start

```bash
# 1. Clone
git clone https://github.com/MithilSaiReddy/bujji.git
cd bujji

# 2. Install core dependency
pip install requests

# 3. Run the setup wizard — configures your LLM provider
python main.py onboard

# 4. Launch
python main.py serve        # Web UI  →  http://localhost:7337
# or
python main.py agent        # Terminal chat
```

### Dependencies at a glance

| Feature | Extra install needed |
|---|---|
| Core agent, web UI, terminal chat | *(none — only `requests`)* |
| Telegram bot | *(none — uses `requests`)* |
| Web search | `pip install ddgs` — no API key needed |
| Discord bot | `pip install discord.py` |
| Community tools | Varies per tool — each prints a clear install message if missing |

---

## ⚙ How It Works

When you send a message, bujji runs this loop:

```
Your message
     │
     ▼
AgentLoop.run()
     │
     ├─ Builds system prompt from SOUL.md + IDENTITY.md + USER.md + active skills
     │
     ├─ Calls LLM with your message + tool schemas
     │       └─ Tokens stream live to UI / terminal
     │
     ├─ LLM decides to call a tool:
     │       ├── ToolRegistry.call("tool_name", {args})
     │       │       ├── Hot-reload check (re-imports changed .py files)
     │       │       ├── Injects ToolContext
     │       │       ├── Runs the function
     │       │       └── Smart-truncates output to 8,000 chars
     │       └── Appends tool result to conversation
     │
     └─ Loop repeats until LLM produces a final reply (no tool calls)
```

Everything is plain Python. No magic. No framework overhead.

---

## 🔧 Adding Tools

A tool is a Python function with a `@register_tool` decorator. Drop the file into `bujji/tools/` and it's live immediately — no restart, no registration step.

### Scaffold a tool in 30 seconds

```bash
python main.py new-tool weather
```

This launches an interactive wizard that asks 4 questions and generates a ready-to-edit file at `bujji/tools/weather.py`:

```
bujji  New tool scaffold: Weather
──────────────────────────────────────────────────────
  API docs / key URL: https://openweathermap.org/api
  API base URL: https://api.openweathermap.org/data/2.5
  Auth pattern: 1  (Bearer token)
  First tool function name: weather_get

  ✅ Created: bujji/tools/weather.py

  Next steps:
    1. Open bujji/tools/weather.py and fill in your API endpoints
    2. Add your credential to ~/.bujji/config.json
    ...
  The tool is already live — no restart needed.
```

Open the file, fill in your endpoint, save. Done.

---

### The Basics

```python
# bujji/tools/my_tool.py
from bujji.tools.base import register_tool, param, ToolContext

@register_tool(
    description="A clear description the LLM uses to decide when to call this tool.",
    params=[
        param("city", "City name to look up"),
    ]
)
def my_tool_name(city: str, _ctx: ToolContext = None) -> str:
    return f"You asked about {city}"
```

Three rules:
1. The function **must return a string**. The LLM reads whatever you return.
2. The function name becomes the tool name. Keep it descriptive: `notion_search`, `github_list_issues`, `weather_get`.
3. `_ctx: ToolContext = None` is optional — include it when you need config, credentials, or workspace access.

---

### Parameters

Use `param()` to declare parameters. It replaces raw JSON schema with one line per parameter.

```python
@register_tool(
    description="Search issues in a project.",
    params=[
        param("query",    "Search query"),
        param("limit",    "Max results to return",   type="integer", default=10),
        param("status",   "Filter by status",        enum=["open", "closed", "all"], default="open"),
        param("assignee", "Filter by assignee",      default=""),
        param("verbose",  "Include full descriptions", type="boolean", default=False),
        param("labels",   "Filter by labels",        type="array", default=[]),
    ]
)
```

**`param()` reference:**

```python
param(
    name,                    # must match the function argument name exactly
    description,             # what the LLM sees — be specific
    type     = "string",     # "string" | "integer" | "number" | "boolean" | "array"
    required = True,         # auto-set to False when you pass a default
    default  = _MISSING,     # any value; makes the param optional
    enum     = None,         # list of allowed string values
    items    = None,         # for type="array": {"type": "string"} by default
)
```

---

### Credentials

Credentials live in `~/.bujji/config.json` under `tools.<service>.<key>`. Use `_ctx.cred()` to access them.

**1. Add to `config.py`** — so the default config schema includes it:

```python
# bujji/config.py → DEFAULT_CONFIG["tools"]
"tools": {
    "web":          {"search": {"api_key": ""}},
    "openweather":  {"api_key": ""},   # ← add your service
},
```

**2. Add masking to `server.py`** — so the key is never returned in full to the UI:

```python
# bujji/server.py → _mask_config()
weather_key = s.get("tools", {}).get("openweather", {}).get("api_key", "")
if weather_key:
    s["tools"]["openweather"]["api_key"] = weather_key[:6] + "…"
```

**3. Add a UI card to `ui/index.html`** — so users can paste the key in Settings:

```html
<div class="card">
  <div class="card-title">🌤 OpenWeather</div>
  <div class="form-group">
    <label>API Key</label>
    <input type="password" class="field" id="s-openweather"
           placeholder="xxxxxxxxxxxxxxxx" autocomplete="off">
    <div class="hint">
      <a href="https://openweathermap.org/api" target="_blank">openweathermap.org</a>
      — free tier available
    </div>
  </div>
  <div class="btn-row">
    <button class="btn btn-primary btn-sm" onclick="saveOpenWeather()">Save</button>
  </div>
</div>
```

**4. Use it in your tool:**

```python
def weather_get(city: str, _ctx: ToolContext = None) -> str:
    key = _ctx.cred("openweather.api_key")
    ...
```

If the key is missing, bujji returns a clear message to the LLM:

```
[openweather] 'api_key' not configured.
  → Add it in the web UI: Settings → OpenWeather
  → Or in config.json:   tools.openweather.api_key
```

---

### HTTP APIs

Use `HttpClient` for any REST API. It handles base URLs, auth headers, JSON parsing, and error messages.

```python
from bujji.tools.base import HttpClient, ToolContext

def _client(_ctx: ToolContext) -> HttpClient:
    return HttpClient(
        base_url = "https://api.example.com/v1",
        headers  = {
            "Authorization": "Bearer " + _ctx.cred("example.api_key"),
            "Content-Type":  "application/json",
        },
    )
```

```python
data   = client.get("/search", params={"q": query, "limit": 10})
result = client.post("/items", json={"name": "New item"})
client.patch(f"/items/{item_id}", json={"status": "closed"})
client.delete(f"/items/{item_id}")
```

Non-2xx responses raise `RuntimeError` with the status code and body — `ToolRegistry` catches it automatically.

---

### Full Example — Weather API

```python
# bujji/tools/weather.py
from bujji.tools.base import HttpClient, ToolContext, param, register_tool


def _client(_ctx: ToolContext) -> HttpClient:
    return HttpClient(
        base_url = "https://api.openweathermap.org/data/2.5",
        headers  = {"Content-Type": "application/json"},
    )


@register_tool(
    description=(
        "Get current weather for any city. "
        "Returns temperature, conditions, humidity, and wind speed."
    ),
    params=[
        param("city",  "City name, e.g. 'London' or 'New York'"),
        param("units", "Temperature unit", enum=["metric", "imperial"], default="metric"),
    ]
)
def weather_get(city: str, units: str = "metric", _ctx: ToolContext = None) -> str:
    key    = _ctx.cred("openweather.api_key")
    client = _client(_ctx)

    data = client.get("/weather", params={"q": city, "units": units, "appid": key})

    unit_symbol = "°C" if units == "metric" else "°F"
    temp        = data["main"]["temp"]
    feels_like  = data["main"]["feels_like"]
    description = data["weather"][0]["description"].capitalize()
    wind        = data["wind"]["speed"]

    return (
        f"{data.get('name', city)}: {description}\n"
        f"Temperature : {temp}{unit_symbol} (feels like {feels_like}{unit_symbol})\n"
        f"Humidity    : {data['main']['humidity']}%\n"
        f"Wind        : {wind} {'m/s' if units == 'metric' else 'mph'}"
    )
```

---

### Error Handling

`ToolRegistry` catches all exceptions automatically. What you should handle explicitly:

```python
def my_tool(query: str, _ctx: ToolContext = None) -> str:
    if not query.strip():
        return "Please provide a search query."          # ← validate input

    items = fetch_items(query)
    if not items:
        return f"No results found for '{query}'."        # ← never return ""

    lines = []
    for item in items:
        try:
            lines.append(format_item(item))
        except Exception:
            lines.append(f"(could not format item {item.get('id', '?')})")

    return "\n".join(lines)
```

What you don't need to handle — the framework does this automatically:

- Missing credentials → clean "not configured" message
- HTTP errors from `HttpClient` → `[TOOL ERROR] HTTP 401 from ...`
- Any unhandled exception → `[TOOL ERROR] 'tool_name' raised ValueError: ...`

---

### Optional Dependencies

Import lazily inside the function and give a clear install message:

```python
def pdf_read(path: str, _ctx: ToolContext = None) -> str:
    try:
        import pdfplumber
    except ImportError:
        return "[pdf_read] Run: pip install pdfplumber"

    with pdfplumber.open(path) as pdf:
        return "\n\n".join(page.extract_text() or "" for page in pdf.pages)
```

---

### Tool Checklist

- [ ] Function name follows `service_action` pattern (e.g. `github_list_issues`)
- [ ] `description=` is a full sentence explaining when the LLM should use it
- [ ] Every `param()` has a useful description
- [ ] Returns a non-empty string even when there are no results
- [ ] Credential key added to `DEFAULT_CONFIG` in `config.py`
- [ ] Credential masking added in `server.py`
- [ ] UI input card added in `index.html` (see [Credentials](#credentials))
- [ ] Optional pip packages imported lazily with a clear install message

---

## 🤖 Sub-Agents

Sub-agents let the main agent delegate focused tasks to specialist agents. Each sub-agent runs its own `AgentLoop` with a custom persona, executes the task, and returns a result.

Drop `bujji/tools/subagents.py` from the repo into your tools folder — it's hot-reloaded instantly.

### `spawn_subagent`

```
You: Research the latest developments in edge AI and summarise them
```

Internally, the main agent can call:

```json
{
  "tool": "spawn_subagent",
  "args": {
    "role": "researcher",
    "task": "Find and summarise the 5 most important edge AI developments from the last 3 months."
  }
}
```

Built-in role shortcuts:

| Role | Behaviour |
|---|---|
| `researcher` | Web search, summarise, cite sources |
| `coder` | Write, review, or debug code |
| `planner` | Break a goal into ordered subtasks |
| `writer` | Draft documents, emails, or reports |
| `analyst` | Read files/data and extract insights |
| `memory` | Cleanly update USER.md with new facts |

Or pass any free-form role description.

### `agent_pipeline`

Chain agents in sequence — each agent's output feeds the next via `{previous}`:

```json
{
  "tool": "agent_pipeline",
  "args": {
    "stages": [
      {"role": "researcher", "task": "Find recent AI hardware news"},
      {"role": "analyst",    "task": "Identify the 3 biggest trends from: {previous}"},
      {"role": "writer",     "task": "Write a 200-word briefing from: {previous}"}
    ]
  }
}
```

This is the pattern for any multi-step automated workflow.

---

## 🛠 Built-in Tools

| Tool | Description |
|---|---|
| `exec` | Run shell commands |
| `web_search` | Search the web via DuckDuckGo — no API key needed (`pip install ddgs`) |
| `read_file` | Read a file's contents |
| `write_file` | Write or overwrite a file (atomic) |
| `append_file` | Append to a file |
| `list_files` | List files in a directory |
| `delete_file` | Delete a file |
| `read_user_memory` | Read persistent `USER.md` |
| `append_user_memory` | Add new facts to memory without erasing existing |
| `update_user_memory` | Full `USER.md` rewrite (for restructuring) |
| `get_time` | Current date and time |
| `message` | Push a message to the user mid-task |
| `spawn_subagent` | Delegate a task to a specialist sub-agent |
| `agent_pipeline` | Run a chain of sub-agents in sequence |

---

## 🧩 Skills

Skills are Markdown files injected into the system prompt on every message.

```
workspace/skills/python-expert/SKILL.md
```

```markdown
# Python Expert

You are a Python expert. Always:
- Prefer list comprehensions over map/filter
- Use f-strings instead of .format()
- Add type hints to all function signatures
- Recommend dataclasses for structured data
```

Save and it's active. Delete to deactivate. No restart. Skills are also installable from the Marketplace tab in the web UI.

---

## ⏱ Background Automation

### Heartbeat

`HEARTBEAT.md` in your workspace runs every 30 minutes as an agent prompt.

```markdown
- Check disk usage on /. If above 85%, append a warning to USER.md.
- Append today's weather summary to journal.md.
```

### Cron

`workspace/cron/jobs.json` schedules tasks at any interval.

```json
[
  {
    "name": "daily-news",
    "prompt": "Search for today's top AI news and append a summary to workspace/news.md",
    "interval_minutes": 1440,
    "last_run": null
  }
]
```

Start background services:

```bash
python main.py gateway
```

---

## ⚙️ Configuration

Config lives at `~/.bujji/config.json`. Created by `python main.py onboard`, fully editable from the web UI.

```json
{
  "active_provider": "openrouter",
  "agents": {
    "defaults": {
      "workspace":             "~/.bujji/workspace",
      "model":                 "openai/gpt-4o-mini",
      "max_tokens":            8192,
      "temperature":           0.7,
      "max_tool_iterations":   20,
      "restrict_to_workspace": false,
      "max_tool_output_chars": 8000
    }
  },
  "providers": {
    "openrouter": {
      "api_key":  "sk-or-...",
      "api_base": "https://openrouter.ai/api/v1"
    }
  },
  "channels": {
    "telegram": { "enabled": false, "token": "", "allow_from": [] },
    "discord":  { "enabled": false, "token": "", "allow_from": [] }
  },
  "tools": {
    "web": { "search": { "api_key": "", "max_results": 5 } }
  }
}
```

| Key | Description |
|---|---|
| `agents.defaults.max_tool_iterations` | Max tool calls per message (default: 20) |
| `agents.defaults.restrict_to_workspace` | Sandbox file tools to the workspace directory |
| `agents.defaults.max_tool_output_chars` | Tool output truncation limit (default: 8000) |

---

## 📋 Commands

| Command | What it does |
|---|---|
| `python main.py onboard` | First-time wizard — LLM, workspace, Telegram |
| `python main.py serve` | Web UI at `http://localhost:7337` |
| `python main.py serve --port 8080` | Custom port |
| `python main.py agent` | Interactive terminal chat |
| `python main.py agent -m "message"` | Single message, non-interactive |
| `python main.py agent --no-stream` | Disable streaming |
| `python main.py new-tool <name>` | Scaffold a new tool (e.g. `new-tool github`) |
| `python main.py gateway` | Start Telegram + Discord + heartbeat + cron |
| `python main.py setup-telegram` | Configure Telegram bot interactively |
| `python main.py status` | Health check — provider, tools, channels |

---

## 🗂 The Workspace

```
workspace/
├── SOUL.md         Core values and ethics
├── IDENTITY.md     Name, personality, and purpose
├── USER.md         Persistent memory — bujji appends automatically, never overwrites
├── AGENT.md        Self-description of active tools
├── HEARTBEAT.md    Task list bujji runs every 30 minutes
├── skills/
│   └── my-skill/SKILL.md
└── cron/
    └── jobs.json
```

Every file is plain Markdown or JSON — readable, editable, version-controllable with git.

---

## 🤖 LLM Providers

bujji works with any OpenAI-compatible API.

| Provider | Free Tier | Notes |
|---|---|---|
| [OpenRouter](https://openrouter.ai/keys) | ✅ Yes | All major models via one key |
| [OpenAI](https://platform.openai.com/api-keys) | — | gpt-4o-mini is cheapest |
| [Anthropic](https://console.anthropic.com/settings/keys) | — | Claude Haiku is fastest |
| [Groq](https://console.groq.com/keys) | ✅ Yes | Very fast, generous free tier |
| [Google AI Studio](https://aistudio.google.com/app/apikey) | ✅ Yes | Gemini 2.0 Flash |
| [Mistral](https://console.mistral.ai/) | — | mistral-small is affordable |
| [DeepSeek](https://platform.deepseek.com/) | — | Strong reasoning at low cost |
| [Ollama](https://ollama.com/) | ✅ Fully local | No API key. `ollama serve` first. |

```bash
# Fully offline with Ollama:
ollama pull llama3.2
ollama serve
python main.py onboard   # select "ollama", model "llama3.2"
```

---

## 🔌 Channels — Telegram & Discord

### Telegram

```bash
python main.py setup-telegram
python main.py gateway
```

Use `allow_from` to whitelist specific Telegram user IDs. Find yours by messaging [@userinfobot](https://t.me/userinfobot).

### Discord

```bash
pip install discord.py
# Add token to config, then:
python main.py gateway
```

### Adding a new channel

1. Create `bujji/connections/myplatform.py`
2. Implement a class with a `.run()` blocking method
3. Wire it into `cmd_gateway()` in `main.py` following the Telegram pattern

```python
class MyPlatformChannel:
    def __init__(self, token: str, cfg: dict, mgr: SessionManager):
        ...
    def run(self):
        while True:
            for msg in self.poll():
                session = self.mgr.get(msg.user_id)
                reply   = session.run(msg.text)
                self.send(msg.user_id, reply)
```

---

## 🏗 Architecture

```
bujji/
├── main.py                     CLI — 7 commands including new-tool
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
│   │   ├── base.py             @register_tool · param() · ToolContext · HttpClient · ToolRegistry
│   │   ├── shell.py            exec
│   │   ├── web.py              web_search
│   │   ├── file_ops.py         read / write / append / list / delete
│   │   ├── memory.py           read / append / update USER.md
│   │   ├── utils.py            get_time · message
│   │   ├── subagents.py        spawn_subagent · agent_pipeline
│   │   └── TEMPLATE.py         Copy-paste starting point for new tools
│   │
│   └── connections/
│       ├── telegram.py         Telegram bot (long-polling)
│       └── discord.py          Discord bot
│
├── ui/
│   └── index.html              Single-file web UI — no build step
│
└── workspace/
    ├── SOUL.md
    ├── IDENTITY.md
    ├── USER.md
    ├── AGENT.md
    ├── HEARTBEAT.md
    ├── skills/
    └── cron/
```

### Key design decisions

**Why only `requests` as a core dependency?**
The core agent, server, and all built-in tools run on `requests` alone — bujji runs on any Python 3.9+ environment, including Raspberry Pi OS and minimal cloud VMs, without a complex install.

**Why hot-reload?**
The tool iteration loop is: write → save → test. Not: write → save → restart → wait → test. `ToolRegistry` rescans `bujji/tools/` on every message using file mtimes, reloading only changed files.

**Why plain Markdown for memory?**
`USER.md` is just a text file — readable, editable, grep-able, versionable with git. No vector DB, no embeddings, no special format required.

**Why a single-file web UI?**
`ui/index.html` has no build step, no Node.js, no npm. The server serves it as a static file alongside a small set of JSON endpoints.

---

## 🤝 Contributing

Contributions are welcome — especially new tools, skills, and connection integrations.

```bash
git clone https://github.com/MithilSaiReddy/bujji.git
cd bujji
pip install requests
python main.py onboard   # any free provider works (Google, Groq, OpenRouter, Ollama)
```

### What to contribute

- **Tools** — integrations in `bujji/tools/` (use `python main.py new-tool <name>` to scaffold)
- **Skills** — Markdown instruction sets for domains (Python, SQL, DevOps, etc.)
- **Connections** — messaging platform integrations in `bujji/connections/`
- **Bug fixes** — streaming, retry, memory edge cases
- **Documentation** — usage examples, tutorials, translated docs

### Rules

**The core must stay lean.** New code inside the bujji core (agent, server, session, llm, config, identity) must not add pip dependencies beyond `requests`.

**Tool integrations may add optional dependencies**, but must import them lazily and print a clear install message if missing. They must never crash the core agent.

**Test with Ollama.** It runs fully offline — no API key needed. If `python main.py agent` breaks with Ollama, it needs to be fixed before merging.

```bash
git checkout -b feature/your-feature
git commit -m "Add GitHub issues tool"
git push origin feature/your-feature
# open a pull request
```

---

## 🗺 Roadmap

### Done
- [x] Core agentic tool-use loop
- [x] Hot-reload tools and skills (no restart)
- [x] Persistent memory (`USER.md`, atomic writes)
- [x] Web UI with SSE streaming
- [x] Session management (per-user agent isolation)
- [x] Telegram + Discord connections
- [x] Heartbeat and cron background services
- [x] Skills marketplace
- [x] Sub-agents (`spawn_subagent`, `agent_pipeline`)
- [x] `python main.py new-tool <name>` scaffold generator
- [x] `param()` + `HttpClient` — zero-boilerplate tool creation

### Next
- [ ] Tools marketplace (GitHub, Gmail, Google Calendar, Linear)
- [ ] Channels marketplace (Slack, WhatsApp, Email)
- [ ] Voice input/output
- [ ] Better memory — semantic search over USER.md
- [ ] Mobile web UI improvements

### Future
- [ ] Plugin SDK — standardised packaging for marketplace submissions
- [ ] RAG over local documents (zero-cloud, local vector index)
- [ ] Skill and tool versioning

---

## 📄 License

MIT — fork it, modify it, use it commercially, run it offline.  
See [LICENSE](LICENSE) for the full text.

---

<div align="center">

*"Small agents that run anywhere are more powerful than big agents that need the cloud."*

**[⭐ Star on GitHub](https://github.com/MithilSaiReddy/bujji)** · **[Report a Bug](https://github.com/MithilSaiReddy/bujji/issues)** · **[Start a Discussion](https://github.com/MithilSaiReddy/bujji/discussions)**

</div>