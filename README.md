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

[Quick Start](#-quick-start) · [How It Works](#-how-it-works) · [Adding Tools](#-adding-tools) · [Configuration](#-configuration) · [LLM Providers](#-llm-providers) · [Contributing](#-contributing)

</div>

---

## What is bujji?

Bujji is a self-hosted AI agent framework. It connects any OpenAI-compatible LLM to a set of tools — shell, web, files, memory, Notion, and whatever else you wire up — and runs as a web app, a terminal chat, a Telegram bot, or a Discord bot, all from a single codebase with minimal setup.

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
  - [The Basics](#the-basics)
  - [Parameters](#parameters)
  - [Credentials](#credentials)
  - [HTTP APIs](#http-apis)
  - [Full Example — Weather API](#full-example--weather-api)
  - [Full Example — REST API with Auth](#full-example--rest-api-with-auth)
  - [Error Handling](#error-handling)
  - [Optional Dependencies](#optional-dependencies)
  - [Tool Checklist](#tool-checklist)
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
| Web search | *(none)* + [Brave API key](https://brave.com/search/api) (free, 2k/month) |
| Discord bot | `pip install discord.py` |
| Marketplace tools | Varies per tool — each prints a clear install message if missing |

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

This is the main extension point. A tool is a Python function with a `@register_tool` decorator. Drop the file into `bujji/tools/` and it's live immediately — no restart, no registration step.

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
2. The function name becomes the tool name the LLM calls. Keep it descriptive: `notion_search`, `github_list_issues`, `weather_get`.
3. `_ctx: ToolContext = None` is optional — include it if you need config, credentials, or workspace access.

---

### Parameters

Use `param()` to declare parameters. It replaces raw JSON schema with one line per parameter.

```python
from bujji.tools.base import register_tool, param, ToolContext

@register_tool(
    description="Search issues in a project.",
    params=[
        # Required string (default)
        param("query", "Search query"),

        # Optional integer with default
        param("limit", "Max results to return", type="integer", default=10),

        # Enum — LLM must pick one of these values
        param("status", "Filter by status", enum=["open", "closed", "all"], default="open"),

        # Optional string
        param("assignee", "Filter by assignee username", default=""),

        # Boolean flag
        param("verbose", "Include full descriptions", type="boolean", default=False),

        # Array of strings
        param("labels", "Filter by labels", type="array", default=[]),
    ]
)
def project_search(
    query:    str,
    limit:    int  = 10,
    status:   str  = "open",
    assignee: str  = "",
    verbose:  bool = False,
    labels:   list = None,
    _ctx: ToolContext = None,
) -> str:
    ...
```

**`param()` signature:**

```python
param(
    name,           # str  — must match the function argument name exactly
    description,    # str  — what the LLM sees; be specific
    type     = "string",   # "string" | "integer" | "number" | "boolean" | "array"
    required = True,       # auto-set to False if you pass a default
    default  = _MISSING,   # any value; makes the param optional
    enum     = None,       # list of allowed string values
    items    = None,       # for type="array": {"type": "string"} (default)
)
```

---

### Credentials

If your tool needs an API key, credentials live in `~/.bujji/config.json` under `tools.<service>.<key>`. Use `_ctx.cred()` to access them — it gives a clean, actionable error message to the LLM if the key is missing.

**1. Add it to `config.py`** — so the default config schema includes it:

```python
# bujji/config.py  →  DEFAULT_CONFIG["tools"]
"tools": {
    "web":    {"search": {"api_key": ""}},
    "notion": {"api_key": ""},
    "openweather": {"api_key": ""},   # ← add your service here
},
```

**2. Add it to `server.py`** — so the key gets masked in the web UI (never shown in full):

```python
# bujji/server.py  →  inside _mask_config()
weather_key = s.get("tools", {}).get("openweather", {}).get("api_key", "")
if weather_key:
    s["tools"]["openweather"]["api_key"] = weather_key[:6] + "…"
```

**3. Add it to the Setup tab in `ui/index.html`** — so users can paste the key in the UI:

```html
<!-- Inside the Setup panel, add a new card -->
<div class="card">
  <div class="card-title">
    🌤 OpenWeather <span style="font-weight:400;color:var(--muted)">(optional)</span>
    <span class="badge" id="openweather-badge" style="display:none">connected</span>
  </div>
  <div class="form-group">
    <label>API Key</label>
    <input type="password" class="field" id="s-openweather" placeholder="xxxxxxxxxxxxxxxx" autocomplete="off">
    <div class="hint"><a href="https://openweathermap.org/api" target="_blank">openweathermap.org/api</a> → Get API key (free tier)</div>
  </div>
  <div class="btn-row">
    <button class="btn btn-primary btn-sm" onclick="saveOpenWeather()">Save</button>
  </div>
</div>
```

```javascript
// In the <script> section of ui/index.html
async function saveOpenWeather() {
  const key = document.getElementById('s-openweather')?.value.trim() || ''
  await saveConfig({ tools: { openweather: { api_key: key } } }, 'OpenWeather key saved ✓')
  const r = await fetch('/api/config/raw')
  if (r.ok) {
    const cfg = await r.json()
    const badge = document.getElementById('openweather-badge')
    if (badge) badge.style.display = cfg.tools?.openweather?.api_key ? '' : 'none'
  }
}
```

**4. Use it in your tool:**

```python
def weather_get(city: str, _ctx: ToolContext = None) -> str:
    key = _ctx.cred("openweather.api_key")   # raises a clean error if missing
    ...
```

`_ctx.cred("service.key")` maps directly to `cfg["tools"]["service"]["key"]`. If the value is empty, bujji returns a message like:

```
[openweather] 'api_key' not configured.
  → Add it in the web UI: Setup → OpenWeather
  → Or in config.json: tools.openweather.api_key
```

The LLM reads this and tells the user exactly what to do — no silent failures.

---

### HTTP APIs

For any REST API, use `HttpClient`. It handles base URLs, headers, JSON parsing, and error messages in one place.

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

Then use it:

```python
# GET with query params
data = client.get("/search", params={"q": query, "limit": 10})

# POST with JSON body
result = client.post("/items", json={"name": "New item", "status": "open"})

# PATCH / PUT / DELETE
client.patch(f"/items/{item_id}", json={"status": "closed"})
client.delete(f"/items/{item_id}")
```

`HttpClient` auto-parses JSON responses and raises a `RuntimeError` with the HTTP status code and body on failure. The `ToolRegistry` catches that and turns it into a `[TOOL ERROR]` string the LLM can read.

---

### Full Example — Weather API

A complete, real tool that fetches current weather:

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
        "Get the current weather for any city. "
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

    data = client.get("/weather", params={
        "q":     city,
        "units": units,
        "appid": key,
    })

    unit_symbol = "°C" if units == "metric" else "°F"
    name        = data.get("name", city)
    temp        = data["main"]["temp"]
    feels_like  = data["main"]["feels_like"]
    humidity    = data["main"]["humidity"]
    description = data["weather"][0]["description"].capitalize()
    wind        = data["wind"]["speed"]
    wind_unit   = "m/s" if units == "metric" else "mph"

    return (
        f"{name}: {description}\n"
        f"Temperature: {temp}{unit_symbol} (feels like {feels_like}{unit_symbol})\n"
        f"Humidity: {humidity}%\n"
        f"Wind: {wind} {wind_unit}"
    )
```

Save the file. It's immediately callable by the LLM on the next message.

---

### Full Example — REST API with Auth

A tool that reads from a hypothetical project management API:

```python
# bujji/tools/tasks.py
import json
from bujji.tools.base import HttpClient, ToolContext, param, register_tool

SERVICE = "taskapp"


def _client(_ctx: ToolContext) -> HttpClient:
    return HttpClient(
        base_url = "https://api.taskapp.com/v2",
        headers  = {
            "Authorization": "Bearer " + _ctx.cred(f"{SERVICE}.api_key"),
            "Content-Type":  "application/json",
        },
    )


@register_tool(
    description="List tasks from your project board, with optional status and assignee filters.",
    params=[
        param("project",  "Project name or ID"),
        param("status",   "Filter by task status", enum=["open", "in_progress", "done", "all"], default="open"),
        param("assignee", "Filter by assignee username (leave empty for all)", default=""),
        param("limit",    "Max tasks to return", type="integer", default=20),
    ]
)
def task_list(
    project:  str,
    status:   str = "open",
    assignee: str = "",
    limit:    int = 20,
    _ctx: ToolContext = None,
) -> str:
    client = _client(_ctx)
    params = {"project": project, "limit": limit}
    if status != "all":
        params["status"] = status
    if assignee:
        params["assignee"] = assignee

    data  = client.get("/tasks", params=params)
    tasks = data.get("tasks", [])

    if not tasks:
        return f"No {status} tasks found in '{project}'."

    lines = []
    for t in tasks:
        assignee_str = f" → {t['assignee']}" if t.get("assignee") else ""
        lines.append(f"[{t['status'].upper()}] {t['title']} (#{t['id']}){assignee_str}")

    return f"Found {len(tasks)} task(s) in '{project}':\n\n" + "\n".join(lines)


@register_tool(
    description="Create a new task in a project.",
    params=[
        param("project",     "Project name or ID"),
        param("title",       "Task title"),
        param("description", "Task description", default=""),
        param("assignee",    "Assign to this username", default=""),
        param("priority",    "Task priority", enum=["low", "medium", "high"], default="medium"),
    ]
)
def task_create(
    project:     str,
    title:       str,
    description: str = "",
    assignee:    str = "",
    priority:    str = "medium",
    _ctx: ToolContext = None,
) -> str:
    client  = _client(_ctx)
    payload = {"project": project, "title": title, "priority": priority}
    if description:
        payload["description"] = description
    if assignee:
        payload["assignee"] = assignee

    result = client.post("/tasks", json=payload)
    return f"✓ Task created: '{title}' (#{result.get('id')}) in {project}"
```

---

### Error Handling

You don't need to wrap everything in try/except. The `ToolRegistry` catches all exceptions and returns them as `[TOOL ERROR] ...` strings — the LLM reads the error and can explain it to the user or try something different.

What you should handle explicitly:

```python
def my_tool(query: str, _ctx: ToolContext = None) -> str:
    # 1. Empty or invalid input — return early with a clear message
    if not query.strip():
        return "Please provide a search query."

    # 2. Empty results — always explain what happened
    items = fetch_items(query)
    if not items:
        return f"No results found for '{query}'."

    # 3. Partial failure — return what you have
    lines = []
    for item in items:
        try:
            lines.append(format_item(item))
        except Exception:
            lines.append(f"(could not format item {item.get('id', '?')})")

    return "\n".join(lines)
```

What you don't need to handle — the framework does this automatically:

- `ToolCredentialError` — missing API key → friendly "not configured" message
- `RuntimeError` from `HttpClient` — HTTP errors → `[TOOL ERROR] HTTP 401 from ...`
- Any other unhandled exception → `[TOOL ERROR] 'tool_name' raised ValueError: ...`

---

### Optional Dependencies

If your tool needs a pip package beyond `requests`, import it lazily inside the function and give a clear install message:

```python
@register_tool(
    description="Parse a PDF file and extract its text content.",
    params=[param("path", "Path to the PDF file")]
)
def pdf_read(path: str, _ctx: ToolContext = None) -> str:
    try:
        import pdfplumber
    except ImportError:
        return (
            "[pdf_read] 'pdfplumber' is not installed.\n"
            "Run: pip install pdfplumber"
        )

    with pdfplumber.open(path) as pdf:
        return "\n\n".join(page.extract_text() or "" for page in pdf.pages)
```

This way the core agent is never broken by a missing optional dependency, and the LLM can pass the install instruction directly to the user.

---

### Tool Checklist

Before shipping a tool:

- [ ] Function name is descriptive: `service_action` pattern (e.g. `github_list_issues`)
- [ ] `description=` is a full sentence explaining when the LLM should use it
- [ ] Every `param()` has a useful `description` — not just a variable name
- [ ] Returns a string that reads well as plain text
- [ ] Returns a non-empty message when there are no results (never return `""` or `[]`)
- [ ] Credential key added to `DEFAULT_CONFIG` in `config.py`
- [ ] Credential masking added to `server.py`
- [ ] UI input added to `index.html` if users need to paste a key (see [Credentials](#credentials))
- [ ] Optional pip packages are imported lazily with a clear install message

---

## 🛠 Built-in Tools

| Tool | Description |
|---|---|
| `exec` | Run shell commands |
| `web_search` | Search the web (Brave API — [free key](https://brave.com/search/api)) |
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
| `notion_search` | Search Notion pages and databases |
| `notion_get_page` | Read a Notion page's full content |
| `notion_create_page` | Create a new Notion page |
| `notion_append_to_page` | Append content to an existing Notion page |
| `notion_get_database` | List rows from a Notion database |
| `notion_add_database_row` | Add a row to a Notion database |
| `notion_update_property` | Update a property on a database row |
| `notion_get_comments` | Read comments on a page |
| `notion_add_comment` | Add a comment to a page |

> Notion tools require an integration secret — add it in Setup → Notion. See [notion.so/my-integrations](https://www.notion.so/my-integrations).

---

## 🧩 Skills

Skills are Markdown files that give bujji domain-specific instructions. They're injected into the system prompt on every message.

**Create a skill:**

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
- Suggest pathlib.Path over os.path
```

Save and it's active immediately. Delete the file to deactivate it. No restart.

Skills are also installable from the Marketplace tab in the web UI.

---

## ⏱ Background Automation

### Heartbeat

`HEARTBEAT.md` in your workspace runs every 30 minutes as an agent prompt. Use it for recurring checks or diary entries.

```markdown
# HEARTBEAT.md

- Check disk usage on /. If above 85%, append a warning to USER.md.
- Append today's weather summary to journal.md.
- If any process in the workspace/watch.txt list is not running, send me a message.
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
  },
  {
    "name": "disk-check",
    "prompt": "Check disk usage. If /home is above 80%, append a warning to USER.md.",
    "interval_minutes": 60,
    "last_run": null
  }
]
```

Start background services with:

```bash
python main.py gateway
```

---

## ⚙️ Configuration

Config lives at `~/.bujji/config.json`. It's created by `python main.py onboard` and fully editable from the web UI at `http://localhost:7337`.

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
    "web":    { "search": { "api_key": "", "max_results": 5 } },
    "notion": { "api_key": "" }
  }
}
```

| Key | Description |
|---|---|
| `active_provider` | Which provider to use when multiple are configured |
| `agents.defaults.max_tool_iterations` | Max tool calls per message before giving up (default: 20) |
| `agents.defaults.restrict_to_workspace` | If true, file tools are sandboxed to the workspace directory |
| `agents.defaults.max_tool_output_chars` | Tool output is truncated to this length (default: 8000) |

---

## 📋 Commands

| Command | What it does |
|---|---|
| `python main.py onboard` | First-time wizard — LLM, workspace, Telegram |
| `python main.py serve` | Web UI at `http://localhost:7337` |
| `python main.py serve --port 8080` | Custom port |
| `python main.py agent` | Interactive terminal chat |
| `python main.py agent -m "message"` | Single message, non-interactive |
| `python main.py agent --no-stream` | Disable streaming (useful for piping output) |
| `python main.py gateway` | Start Telegram + Discord bots + heartbeat + cron |
| `python main.py setup-telegram` | Configure Telegram bot interactively |
| `python main.py status` | Health check — provider, tools, channels |

---

## 🗂 The Workspace

The workspace (`~/.bujji/workspace/` by default) is where bujji's "mind" lives. Every file is plain Markdown or JSON — readable, editable, version-controllable.

```
workspace/
├── SOUL.md         Core values and ethics — bujji reads this on every message
├── IDENTITY.md     Name, personality, and purpose
├── USER.md         Persistent memory about you — bujji appends to this automatically
├── AGENT.md        Self-description of active tools and capabilities
├── HEARTBEAT.md    Task list bujji runs every 30 minutes
├── skills/
│   └── my-skill/
│       └── SKILL.md
└── cron/
    └── jobs.json
```

| File | Written by | Purpose |
|---|---|---|
| `SOUL.md` | You | Core values, ethics, and personality traits |
| `IDENTITY.md` | You | Name, description, and purpose |
| `USER.md` | bujji + you | Persistent memory — never overwritten, only appended |
| `AGENT.md` | bujji | Self-description of active tools |

---

## 🤖 LLM Providers

bujji works with any OpenAI-compatible API. Configure during `python main.py onboard` or via the web UI.

| Provider | Free Tier | Notes |
|---|---|---|
| [OpenRouter](https://openrouter.ai/keys) | ✅ Yes | Access to all major models with one key |
| [OpenAI](https://platform.openai.com/api-keys) | — | gpt-4o-mini is the cheapest option |
| [Anthropic](https://console.anthropic.com/settings/keys) | — | Claude Haiku is the fastest |
| [Groq](https://console.groq.com/keys) | ✅ Yes | Very fast inference, generous free tier |
| [Google AI Studio](https://aistudio.google.com/app/apikey) | ✅ Yes | Gemini 2.0 Flash, free tier |
| [Mistral](https://console.mistral.ai/) | — | mistral-small is affordable |
| [DeepSeek](https://platform.deepseek.com/) | — | Strong reasoning at low cost |
| [Ollama](https://ollama.com/) | ✅ Fully local | No API key, no internet. `ollama serve` first. |

**Using Ollama (fully offline):**

```bash
# 1. Install Ollama and pull a model
ollama pull llama3.2

# 2. Run the serve command
ollama serve

# 3. In bujji onboard, select "ollama" and model "llama3.2"
```

---

## 🔌 Channels — Telegram & Discord

### Telegram

```bash
python main.py setup-telegram   # interactive setup
python main.py gateway           # starts the bot
```

Use `allow_from` in config (or the web UI) to whitelist specific Telegram user IDs. Without a whitelist, anyone who finds your bot's username can use it. Find your user ID by messaging [@userinfobot](https://t.me/userinfobot) on Telegram.

### Discord

```bash
pip install discord.py
```

Enable Discord and add your bot token in Setup → Discord, or in `~/.bujji/config.json`:

```json
"channels": {
  "discord": {
    "enabled": true,
    "token": "your-discord-bot-token",
    "allow_from": ["your_server_channel_id"]
  }
}
```

Then: `python main.py gateway`

If `discord.py` is not installed, bujji skips Discord and continues with Telegram and the web UI — it never crashes.

### Adding a new channel

1. Create `bujji/connections/myplatform.py`
2. Implement a class with a `.run()` method (blocking loop, designed for a daemon thread)
3. Wire it into `main.py`'s `cmd_gateway()` following the Telegram pattern

```python
# bujji/connections/myplatform.py
from bujji.session import SessionManager

class MyPlatformChannel:
    def __init__(self, token: str, cfg: dict, mgr: SessionManager):
        self.token = token
        self.cfg   = cfg
        self.mgr   = mgr

    def run(self):
        # polling / event loop — runs in a daemon thread
        while True:
            messages = self.poll()
            for msg in messages:
                session = self.mgr.get(msg.user_id)
                reply   = session.run(msg.text)
                self.send(msg.user_id, reply)
```

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
│   │   ├── base.py             @register_tool · param() · ToolContext · HttpClient · ToolRegistry
│   │   ├── shell.py            exec
│   │   ├── web.py              web_search
│   │   ├── file_ops.py         read / write / append / list / delete
│   │   ├── memory.py           read / append / update USER.md
│   │   ├── utils.py            get_time, message
│   │   ├── notion.py           9 Notion tools
│   │   └── TEMPLATE.py         Copy-paste starting point for new tools
│   │
│   └── connections/
│       ├── telegram.py         Telegram bot (long-polling)
│       └── discord.py          Discord bot
│
├── ui/
│   └── index.html              Single-file web UI — no build step
│
└── workspace/                  Your personal agent workspace
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
The core agent, server, and all built-in tools including Telegram run on `requests` alone. This means bujji can run on any Python 3.9+ environment — Raspberry Pi OS, minimal cloud VMs, offline machines — without a complex install step.

**Why hot-reload?**  
The tool iteration loop is: write code → save → test. Not: write code → save → restart → wait → test. `ToolRegistry` rescans `bujji/tools/` on every message using mtimes, reloading only changed files. The same applies to skills.

**Why plain Markdown for memory?**  
`USER.md` is just a text file. You can read it, edit it, grep it, version it with git. The LLM can read and write it through the memory tools. No vector DB, no embeddings, no special format.

**Why a single-file web UI?**  
`ui/index.html` has no build step, no Node.js, no npm. You can open it in a browser directly. The server just serves it as a static file plus a handful of JSON endpoints.

---

## 🤝 Contributing

Contributions are welcome — especially new tools, skills, and connection integrations.

### Getting started

```bash
git clone https://github.com/MithilSaiReddy/bujji.git
cd bujji
pip install requests
python main.py onboard   # configure with any free provider (Google, Groq, OpenRouter)
```

Ollama works fully offline if you prefer not to use an API key during development.

### What to contribute

- **Tools** — integrations with external services in `bujji/tools/`
- **Skills** — Markdown instruction sets for specific domains
- **Connections** — messaging platform integrations in `bujji/connections/`
- **Bug fixes** — especially around streaming, retry, or memory edge cases
- **Documentation** — usage examples, tutorials, translated docs

### Rules

**The core must stay lean.** New code inside `bujji/` core (agent, server, session, llm, config, identity) must not add pip dependencies beyond `requests`. The agent must be runnable with `pip install requests` only, always.

**Tool integrations may add optional dependencies**, but they must:
- Import them lazily inside the function (not at module level)
- Print a clear, actionable install message if the package is missing
- Never crash the core agent

**Keep it simple.** Small, focused commits. One feature or fix per PR. If a change requires extensive explanation, that's a sign it might be too complex.

**Test with Ollama.** It runs fully offline — no API key needed. If your change breaks `python main.py agent` with Ollama, it needs to be fixed before merging.

### Submitting

```bash
git checkout -b feature/your-feature-name
# make changes
git commit -m "Add GitHub issues tool"
git push origin feature/your-feature-name
# open a pull request on GitHub
```

Include in your PR description: what it does, how to test it, and what config keys it requires (if any).

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
- [x] Notion integration (9 tools)
- [x] Notion key in Setup tab

### Next
- [ ] Tools marketplace (GitHub, Gmail, Google Calendar, Linear)
- [ ] Channels marketplace (Slack, WhatsApp, Email)
- [ ] Multi-agent support
- [ ] Voice input/output
- [ ] Mobile web UI improvements

### Future
- [ ] Plugin SDK — standardized packaging for marketplace submissions
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