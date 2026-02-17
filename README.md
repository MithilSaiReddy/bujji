This is a professional, GitHub-ready `README.md` for your project. It highlights the **Bujji** branding (inspired by the feisty AI from *Kalki 2898 AD*) and explains the "PicoClaw-style" modular architecture so users know how to extend it.

---

# 🏎️ Bujji (AI Assistant)

**Bujji** is an ultra-lightweight, modular AI assistant inspired by [Sipeed's PicoClaw](). It is designed to run on low-resource systems (like an old Mac, a Raspberry Pi, or a thin client) while providing powerful agentic capabilities through a "Skills and Tools" architecture.

Unlike heavy AI frameworks, Bujji is built to be **human-readable** and **pluggable**. You can teach it new tricks just by dropping a Markdown file into a folder or a Python script into a directory.

---

## ✨ Features

* **🧠 Brain (LLM):** OpenAI-compatible API support (Groq, Together, Local LLMs, etc.).
* **🛠️ Tools:** Pre-built tools for Shell execution, File operations, and Web searching.
* **📂 Skills:** Personality and domain knowledge managed via plain Markdown (`SKILL.md`).
* **🔌 Connections:** Built-in gateways for **Telegram** and **Discord**.
* **⏰ Automation:** Integrated Cron and Heartbeat services for recurring tasks.
* **🚀 Lightweight:** Zero heavy dependencies. Fast, simple, and clean.

---

## 🏗️ The Bujji Architecture

Bujji follows a strict modular structure to make customization easy:

| Component | Location | How to Change |
| --- | --- | --- |
| **Tools** | `bujji/tools/` | Drop a `.py` file here to give Bujji new "hands." |
| **Connections** | `bujji/connections/` | Add a `.py` file to connect Bujji to new platforms. |
| **Skills** | `workspace/skills/` | Create a folder with a `SKILL.md` to change its "brain." |
| **Config** | `~/.bujji/` | Edit `config.json` to change models or API keys. |

---

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/yourusername/bujji.git
cd bujji
python3 -m venv venv && source venv/bin/activate
pip install requests discord.py

```

### 2. Onboarding

Run the setup wizard to configure your LLM provider and API keys:

```bash
python3 main.py onboard

```

### 3. Usage

* **Interactive Chat:** `python3 main.py agent`
* **Single Command:** `python3 main.py agent -m "What is my disk usage?"`
* **Start Gateway (Telegram/Discord):** `python3 main.py gateway`
* **Check Status:** `python3 main.py status`

---

## 🛠️ Extending Bujji

### Adding a Skill

Skills are just Markdown. To make Bujji a "Linux Expert":

1. Create `workspace/skills/linux_pro/SKILL.md`.
2. Write: *"You are a Linux expert. Always prefer using 'ls -la' and check file permissions before editing."*
3. Restart Bujji. It now knows its new identity.

### Adding a Tool

Tools are Python functions. To add a "Weather" tool:

1. Create `bujji/tools/weather.py`.
2. Use the `@register_tool` decorator.
3. Add `from bujji.tools import weather` to `bujji/tools/__init__.py`.

---

## 📜 Credits & Inspiration

* **PicoClaw:** Original concept and architecture by [Sipeed]().
* **Bujji:** Character and name inspiration from *Kalki 2898 AD*.

---

## 🛡️ License

MIT License. Feel free to fork, hack, and improve!

---
