#!/usr/bin/env python3
"""
main.py — Bujji CLI entry point (Python port)

Usage:
    python main.py onboard              # First-time setup wizard
    python main.py agent -m "..."       # Single message
    python main.py agent                # Interactive chat
    python main.py setup-telegram       # Configure Telegram bot
    python main.py gateway              # Start messaging gateway
    python main.py status               # Show config and status

Requirements:
    pip install requests                # Core — always needed
    pip install discord.py              # Optional — Discord gateway
"""

import argparse
import sys
import textwrap
import threading
import time

from bujji          import LOGO, __version__
from bujji.config   import (
    CONFIG_FILE, POPULAR_MODELS, PROVIDER_DEFAULTS, WORKSPACE_DEFAULT,
    get_active_provider, load_config, save_config, workspace_path,
)

# ─────────────────────────────────────────────────────────────────────────────
#  ONBOARD
# ─────────────────────────────────────────────────────────────────────────────

def cmd_onboard(args) -> None:
    print(f"\n{LOGO} Welcome to bujji (Python Port) v{__version__}\n")
    cfg           = load_config()
    provider_list = list(PROVIDER_DEFAULTS.keys())

    # ── Choose LLM provider ───────────────────────────────────────────────
    print("Available LLM providers:")
    for i, (p, (_, model)) in enumerate(PROVIDER_DEFAULTS.items(), 1):
        print(f"  {i:2}. {p:<12}  default model: {model}")

    print("""
  Get API keys:
    openrouter → https://openrouter.ai/keys            (all models, free tier)
    openai     → https://platform.openai.com/api-keys
    anthropic  → https://console.anthropic.com/settings/keys
    groq       → https://console.groq.com/keys         (free & fast)
    google     → https://aistudio.google.com/app/apikey   (Gemini, free tier)
    mistral    → https://console.mistral.ai/api-keys   (free trial credits)
    zhipu      → https://open.bigmodel.cn/usercenter/proj-mgmt/apikeys
    deepseek   → https://platform.deepseek.com/api-keys
    ollama     → (no key needed — runs locally)
""")

    choice   = input("Choose provider number (Enter = openrouter): ").strip()
    provider = (
        provider_list[int(choice) - 1]
        if choice.isdigit() and 1 <= int(choice) <= len(provider_list)
        else "openrouter"
    )
    print(f"\nSelected: {provider}")

    api_key = input(f"Enter your {provider} API key: ").strip()
    if provider == "ollama":
        api_key = api_key or "ollama"   # ollama needs a non-empty placeholder

    default_base, default_model = PROVIDER_DEFAULTS[provider]

    if provider in POPULAR_MODELS:
        print(f"\n  Popular {provider} models:")
        for m in POPULAR_MODELS[provider]:
            marker = "  ← default" if m == default_model else ""
            print(f"    • {m}{marker}")

    model = input(f"\nModel name (Enter = {default_model}): ").strip() or default_model

    cfg["providers"][provider] = {"api_key": api_key, "api_base": default_base}
    cfg["agents"]["defaults"]["model"] = model

    # ── Optional: Brave Search ────────────────────────────────────────────
    print("\n[Optional] Brave Search API key (https://brave.com/search/api)")
    print("           Free tier: 2 000 queries/month")
    brave = input("Brave API key (Enter to skip): ").strip()
    if brave:
        cfg["tools"]["web"]["search"]["api_key"] = brave

    # ── Workspace ─────────────────────────────────────────────────────────
    ws = input(f"\nWorkspace directory (Enter = {WORKSPACE_DEFAULT}): ").strip()
    if ws:
        cfg["agents"]["defaults"]["workspace"] = ws

    # ── Optional: Telegram ────────────────────────────────────────────────
    print("\n" + "─" * 52)
    print("  TELEGRAM SETUP  (optional — can be done later)")
    print("─" * 52)
    print("""
  Step 1 — Create a bot
    • Open Telegram → search @BotFather → send /newbot
    • Follow the prompts and copy the bot token

  Step 2 — Get your user ID
    • Search @userinfobot → send any message
    • It replies with your numeric user ID (e.g. 123456789)
""")
    if input("Set up Telegram now? (y/N): ").strip().lower() == "y":
        from bujji.connections.telegram import setup_telegram_interactive
        setup_telegram_interactive(cfg)
    else:
        print("  [Skipped]  Run later:  python main.py setup-telegram")

    # ── Save ──────────────────────────────────────────────────────────────
    save_config(cfg)
    import pathlib
    ws_path = pathlib.Path(cfg["agents"]["defaults"]["workspace"]).expanduser()
    ws_path.mkdir(parents=True, exist_ok=True)
    (ws_path / "skills").mkdir(exist_ok=True)
    (ws_path / "cron").mkdir(exist_ok=True)

    print(f"\n✅ Config:    {CONFIG_FILE}")
    print(f"✅ Workspace: {ws_path}")

    tg_ok = cfg.get("channels", {}).get("telegram", {}).get("enabled", False)
    if tg_ok:
        print(f"✅ Telegram: configured")
        print(f"\nStart the gateway:")
        print(f"  python main.py gateway")

    print(f"\nChat now:")
    print(f"  python main.py agent -m \"Hello!\"\n")


# ─────────────────────────────────────────────────────────────────────────────
#  SETUP-TELEGRAM
# ─────────────────────────────────────────────────────────────────────────────

def cmd_setup_telegram(args) -> None:
    cfg = load_config()
    print(f"\n{LOGO} Telegram Setup\n")
    print("─" * 52)
    print("""
  Step 1 — Create a bot
    • Open Telegram → search @BotFather → send /newbot
    • Follow the prompts and copy the bot token

  Step 2 — Get your user ID
    • Search @userinfobot → send any message
    • It replies with your numeric user ID (e.g. 123456789)
""")
    from bujji.connections.telegram import setup_telegram_interactive
    setup_telegram_interactive(cfg)
    save_config(cfg)
    print(f"\n✅ Saved to {CONFIG_FILE}")
    print(f"\nStart the bot:")
    print(f"  python main.py gateway\n")


# ─────────────────────────────────────────────────────────────────────────────
#  AGENT
# ─────────────────────────────────────────────────────────────────────────────

def cmd_agent(args) -> None:
    try:
        import requests  # noqa: F401
    except ImportError:
        sys.exit("ERROR: pip install requests")

    try:
        from bujji.agent import AgentLoop
        cfg   = load_config()
        agent = AgentLoop(cfg)
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}")

    stream = not getattr(args, "no_stream", False)

    if args.message:
        # ── Single-shot mode ──
        print(f"\n{LOGO}: ", end="", flush=True)
        result = agent.run(args.message, stream=stream)
        if result and not stream:
            print(result)
        print()
    else:
        # ── Interactive mode ──
        print(f"\n{LOGO} Interactive mode  (Ctrl+C or /quit to exit, /clear to reset)\n")
        history = []
        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
                    print(f"Bye! {LOGO}")
                    break
                if user_input.lower() == "/clear":
                    history.clear()
                    print("[History cleared]")
                    continue

                print(f"\n{LOGO}: ", end="", flush=True)
                result = agent.run(user_input, history=history, stream=stream)
                if not stream and result:
                    print(result)
                print()

                history.extend([
                    {"role": "user",      "content": user_input},
                    {"role": "assistant", "content": result or "[streamed]"},
                ])
                # Keep last 40 messages (20 turns) to limit memory
                if len(history) > 40:
                    history = history[-40:]

            except (KeyboardInterrupt, EOFError):
                print(f"\n\nBye! {LOGO}")
                break


# ─────────────────────────────────────────────────────────────────────────────
#  GATEWAY
# ─────────────────────────────────────────────────────────────────────────────

def cmd_gateway(args) -> None:
    try:
        import requests  # noqa: F401
    except ImportError:
        sys.exit("ERROR: pip install requests")

    try:
        from bujji.agent import AgentLoop, CronService, HeartbeatService
        cfg   = load_config()
        agent = AgentLoop(cfg)
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}")

    ws           = workspace_path(cfg)
    channels_cfg = cfg.get("channels", {})
    active       = []

    # ── Background services ───────────────────────────────────────────────
    hb   = HeartbeatService(agent, ws)
    cron = CronService(agent, ws)
    hb.start()
    cron.start()

    # ── Telegram ──────────────────────────────────────────────────────────
    tg_cfg = channels_cfg.get("telegram", {})
    if tg_cfg.get("enabled") and tg_cfg.get("token"):
        from bujji.connections.telegram import TelegramChannel
        tg = TelegramChannel(tg_cfg["token"], tg_cfg.get("allow_from", []), cfg)
        threading.Thread(target=tg.run, daemon=True).start()
        active.append("Telegram")

    # ── Discord ───────────────────────────────────────────────────────────
    dc_cfg = channels_cfg.get("discord", {})
    if dc_cfg.get("enabled") and dc_cfg.get("token"):
        from bujji.connections.discord import DiscordChannel
        dc = DiscordChannel(dc_cfg["token"], dc_cfg.get("allow_from", []), cfg)
        threading.Thread(target=dc.run, daemon=True).start()
        active.append("Discord")

    if not active:
        print(f"\n{LOGO} No channels enabled.")
        print("Run: python main.py setup-telegram")
        hb.stop()
        cron.stop()
        return

    print(f"\n{LOGO} Gateway running.  Active channels: {', '.join(active)}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{LOGO} Shutting down…")
        hb.stop()
        cron.stop()


# ─────────────────────────────────────────────────────────────────────────────
#  STATUS
# ─────────────────────────────────────────────────────────────────────────────

def cmd_status(args) -> None:
    import json
    cfg                              = load_config()
    pname, api_key, api_base, model  = get_active_provider(cfg)
    ws                               = workspace_path(cfg)

    print(f"\n{LOGO} bujji Python Port v{__version__}")
    print(f"  Config:    {CONFIG_FILE}  {'✅' if CONFIG_FILE.exists() else '❌ missing'}")
    print(f"  Workspace: {ws}  {'✅' if ws.exists() else '❌ missing'}")

    print(f"\n  LLM Provider:")
    if pname:
        masked = (api_key[:8] + "…") if api_key and len(api_key) > 8 else "(set)"
        print(f"    Provider : {pname}")
        print(f"    Model    : {model}")
        print(f"    API Base : {api_base}")
        print(f"    Key      : {masked}")
    else:
        print(f"    ⚠️  Not configured — run: python main.py onboard")

    print(f"\n  Channels:")
    for ch_name, ch_cfg in cfg.get("channels", {}).items():
        enabled = ch_cfg.get("enabled", False)
        mark    = "✅" if enabled else "  "
        extra   = ""
        if ch_name == "telegram" and enabled:
            af    = ch_cfg.get("allow_from", [])
            extra = f"  (allow_from: {af if af else 'everyone'})"
        print(f"    {mark} {ch_name}{extra}")

    brave = cfg["tools"]["web"]["search"].get("api_key", "")
    print(f"\n  Web search : {'✅ Brave API configured' if brave else '  not configured'}")

    # Installed tools (auto-discovered)
    try:
        from bujji.tools import ToolRegistry
        registry = ToolRegistry(cfg)
        tool_names = [s["function"]["name"] for s in registry.schema()]
        print(f"\n  Tools ({len(tool_names)}): {', '.join(tool_names)}")
    except Exception as e:
        print(f"\n  Tools: (error loading — {e})")

    if ws.exists():
        all_files = list(ws.rglob("*"))
        print(f"\n  Workspace : {len(all_files)} file(s)/dir(s)")
        hb_file   = ws / "HEARTBEAT.md"
        cron_file = ws / "cron" / "jobs.json"
        if hb_file.exists():
            print(f"    ✅ HEARTBEAT.md present")
        if cron_file.exists():
            try:
                jobs = json.loads(cron_file.read_text())
                print(f"    ✅ cron/jobs.json — {len(jobs)} job(s)")
            except Exception:
                print(f"    ⚠️  cron/jobs.json exists but could not be parsed")

    try:
        import requests  # noqa: F401
        requests_ok = True
    except ImportError:
        requests_ok = False

    print(f"\n  Python   : {sys.version.split()[0]}")
    print(f"  requests : {'✅ installed' if requests_ok else '❌  pip install requests'}\n")


# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bujji",
        description=f"{LOGO} bujji — Ultra-lightweight AI assistant (Python port)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
  examples:
    python main.py onboard
    python main.py agent -m "What is the capital of France?"
    python main.py agent
    python main.py setup-telegram
    python main.py gateway
    python main.py status
        """),
    )
    parser.add_argument("--version", action="version", version=f"bujji {__version__}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("onboard",        help="First-time setup wizard")
    sub.add_parser("setup-telegram", help="Configure the Telegram bot (can re-run anytime)")
    sub.add_parser("gateway",        help="Start messaging gateway (Telegram, Discord, …)")
    sub.add_parser("status",         help="Show configuration and runtime status")

    p_agent = sub.add_parser("agent", help="Chat with the AI agent")
    p_agent.add_argument(
        "-m", "--message", type=str, metavar="TEXT",
        help="Single message (non-interactive mode)",
    )
    p_agent.add_argument(
        "--no-stream", action="store_true",
        help="Disable token streaming (print full response at once)",
    )

    args = parser.parse_args()

    cmds = {
        "onboard":        cmd_onboard,
        "setup-telegram": cmd_setup_telegram,
        "agent":          cmd_agent,
        "gateway":        cmd_gateway,
        "status":         cmd_status,
    }

    if args.command in cmds:
        cmds[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()