#!/usr/bin/env python3
"""
main.py — bujji v2 CLI entry point

Usage:
    python main.py onboard              # First-time setup wizard
    python main.py serve                # ← NEW: open web UI in browser
    python main.py agent -m "..."       # Single message
    python main.py agent                # Interactive chat
    python main.py setup-telegram       # Configure Telegram bot
    python main.py gateway              # Start messaging gateway
    python main.py status               # Show config and status

Requirements:
    pip install requests                # Always needed
    pip install discord.py              # Optional: Discord gateway
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
    print(f"\n{LOGO} Welcome to bujji v{__version__}\n")
    cfg           = load_config()
    provider_list = list(PROVIDER_DEFAULTS.keys())

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
        api_key = api_key or "ollama"

    default_base, default_model = PROVIDER_DEFAULTS[provider]

    if provider in POPULAR_MODELS:
        print(f"\n  Popular {provider} models:")
        for m in POPULAR_MODELS[provider]:
            marker = "  ← default" if m == default_model else ""
            print(f"    • {m}{marker}")

    model = input(f"\nModel name (Enter = {default_model}): ").strip() or default_model

    cfg["providers"][provider] = {"api_key": api_key, "api_base": default_base}
    cfg["agents"]["defaults"]["model"] = model

    print("\n[Optional] Brave Search API key (https://brave.com/search/api)")
    print("           Free tier: 2,000 queries/month")
    brave = input("Brave API key (Enter to skip): ").strip()
    if brave:
        cfg["tools"]["web"]["search"]["api_key"] = brave

    ws = input(f"\nWorkspace directory (Enter = {WORKSPACE_DEFAULT}): ").strip()
    if ws:
        cfg["agents"]["defaults"]["workspace"] = ws

    # Telegram
    print("\n" + "─" * 52)
    print("  TELEGRAM SETUP  (optional — can be done later)")
    print("─" * 52)
    if input("Set up Telegram now? (y/N): ").strip().lower() == "y":
        from bujji.connections.telegram import setup_telegram_interactive
        setup_telegram_interactive(cfg)
    else:
        print("  [Skipped]  Run later:  python main.py setup-telegram")

    save_config(cfg)
    import pathlib
    ws_path = pathlib.Path(cfg["agents"]["defaults"]["workspace"]).expanduser()
    ws_path.mkdir(parents=True, exist_ok=True)
    (ws_path / "skills").mkdir(exist_ok=True)
    (ws_path / "cron").mkdir(exist_ok=True)

    print(f"\n✅ Config:    {CONFIG_FILE}")
    print(f"✅ Workspace: {ws_path}")
    print(f"\n💡 Tip: Open the web UI for a nicer experience:")
    print(f"   python main.py serve\n")


# ─────────────────────────────────────────────────────────────────────────────
#  SERVE  (web UI)
# ─────────────────────────────────────────────────────────────────────────────

def cmd_serve(args) -> None:
    try:
        import requests  # noqa: F401
    except ImportError:
        sys.exit("ERROR: pip install requests")

    cfg  = load_config()
    port = getattr(args, "port", 7337) or 7337
    host = getattr(args, "host", "127.0.0.1") or "127.0.0.1"

    from bujji.server import run_server
    run_server(cfg, host=host, port=port)


# ─────────────────────────────────────────────────────────────────────────────
#  SETUP-TELEGRAM
# ─────────────────────────────────────────────────────────────────────────────

def cmd_setup_telegram(args) -> None:
    cfg = load_config()
    print(f"\n{LOGO} Telegram Setup\n{'─'*52}")
    from bujji.connections.telegram import setup_telegram_interactive
    setup_telegram_interactive(cfg)
    save_config(cfg)
    print(f"\n✅ Saved to {CONFIG_FILE}")
    print(f"Start the bot:  python main.py gateway\n")


# ─────────────────────────────────────────────────────────────────────────────
#  AGENT
# ─────────────────────────────────────────────────────────────────────────────

def cmd_agent(args) -> None:
    try:
        import requests  # noqa: F401
    except ImportError:
        sys.exit("ERROR: pip install requests")

    try:
        from bujji.agent   import AgentLoop
        from bujji.session import SessionManager
        cfg = load_config()
        mgr = SessionManager(cfg)
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}")

    stream     = not getattr(args, "no_stream", False)
    session_id = "cli"

    # CLI callbacks
    callbacks = {
        "on_token":      lambda t: print(t, end="", flush=True),
        "on_tool_start": lambda n, a: print(f"\n{LOGO} [Tool] {n}({json_preview(a)})", file=sys.stderr),
        "on_tool_done":  lambda n, r: print(f"  → {r[:120].replace(chr(10),' ')}", file=sys.stderr),
        "on_error":      lambda e: print(f"\n[ERROR] {e}", file=sys.stderr),
    }

    import json
    def json_preview(d):
        return json.dumps(d, ensure_ascii=False)[:80]

    agent = mgr.get(session_id, callbacks=callbacks)

    if args.message:
        print(f"\n{LOGO}: ", end="", flush=True)
        result = agent.run(args.message, stream=stream)
        if result and not stream:
            print(result)
        print()
    else:
        print(f"\n{LOGO} Interactive mode  (Ctrl+C or /quit to exit, /clear to reset)\n")
        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
                    print(f"Bye! {LOGO}")
                    break
                if user_input.lower() == "/clear":
                    mgr.clear(session_id)
                    print("[History cleared]")
                    continue

                print(f"\n{LOGO}: ", end="", flush=True)
                history = mgr.history(session_id)
                result  = agent.run(user_input, history=history, stream=stream)
                if not stream and result:
                    print(result)
                print()

                mgr.append(session_id, "user",      user_input)
                mgr.append(session_id, "assistant", result or "[streamed]")

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
        from bujji.agent   import AgentLoop, HeartbeatService, CronService
        from bujji.session import SessionManager
        cfg = load_config()
        mgr = SessionManager(cfg)
        # Warm up a default agent (validates config early)
        agent = mgr.get("gateway:default")
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}")

    ws           = workspace_path(cfg)
    channels_cfg = cfg.get("channels", {})
    active       = []

    hb   = HeartbeatService(agent, ws)
    cron = CronService(agent, ws)
    hb.start()
    cron.start()

    tg_cfg = channels_cfg.get("telegram", {})
    if tg_cfg.get("enabled") and tg_cfg.get("token"):
        from bujji.connections.telegram import TelegramChannel
        tg = TelegramChannel(tg_cfg["token"], tg_cfg.get("allow_from", []), cfg, mgr)
        threading.Thread(target=tg.run, daemon=True).start()
        active.append("Telegram")

    dc_cfg = channels_cfg.get("discord", {})
    if dc_cfg.get("enabled") and dc_cfg.get("token"):
        from bujji.connections.discord import DiscordChannel
        dc = DiscordChannel(dc_cfg["token"], dc_cfg.get("allow_from", []), cfg, mgr)
        threading.Thread(target=dc.run, daemon=True).start()
        active.append("Discord")

    if not active:
        print(f"\n{LOGO} No channels enabled.  Run: python main.py setup-telegram")
        hb.stop(); cron.stop()
        return

    print(f"\n{LOGO} Gateway running.  Channels: {', '.join(active)}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{LOGO} Shutting down…")
        hb.stop(); cron.stop()


# ─────────────────────────────────────────────────────────────────────────────
#  STATUS
# ─────────────────────────────────────────────────────────────────────────────

def cmd_status(args) -> None:
    import json
    cfg                             = load_config()
    pname, api_key, api_base, model = get_active_provider(cfg)
    ws                              = workspace_path(cfg)

    print(f"\n{LOGO} bujji v{__version__}")
    print(f"  Config:    {CONFIG_FILE}  {'✅' if CONFIG_FILE.exists() else '❌ missing'}")
    print(f"  Workspace: {ws}  {'✅' if ws.exists() else '❌ missing'}")

    print(f"\n  LLM Provider:")
    if pname:
        masked = (api_key[:6] + "…") if api_key and len(api_key) > 6 else "(set)"
        print(f"    Provider : {pname}")
        print(f"    Model    : {model}")
        print(f"    API Base : {api_base}")
        print(f"    Key      : {masked}")
    else:
        print(f"    ⚠️  Not configured — run: python main.py onboard")

    print(f"\n  Channels:")
    for ch_name, ch_cfg in cfg.get("channels", {}).items():
        enabled = ch_cfg.get("enabled", False)
        print(f"    {'✅' if enabled else '  '} {ch_name}")

    brave = cfg["tools"]["web"]["search"].get("api_key", "")
    print(f"\n  Web search : {'✅ Brave API configured' if brave else '  not configured'}")

    try:
        from bujji.tools import ToolRegistry
        registry   = ToolRegistry(cfg)
        tool_names = [s["function"]["name"] for s in registry.schema()]
        print(f"\n  Tools ({len(tool_names)}): {', '.join(tool_names)}")
    except Exception as e:
        print(f"\n  Tools: (error — {e})")

    print(f"\n  Python : {sys.version.split()[0]}")
    try:
        import requests  # noqa
        print(f"  requests : ✅\n")
    except ImportError:
        print(f"  requests : ❌  pip install requests\n")

    print(f"  Web UI : python main.py serve  → http://localhost:7337\n")


# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bujji",
        description=f"{LOGO} bujji v2 — Ultra-lightweight AI assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
  examples:
    python main.py onboard                       # first-time setup
    python main.py serve                         # web UI (recommended)
    python main.py agent -m "What's my disk usage?"
    python main.py agent                         # interactive chat
    python main.py gateway                       # Telegram / Discord bot
        """),
    )
    parser.add_argument("--version", action="version", version=f"bujji {__version__}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("onboard",        help="First-time setup wizard")
    sub.add_parser("setup-telegram", help="Configure the Telegram bot")
    sub.add_parser("gateway",        help="Start Telegram / Discord gateway")
    sub.add_parser("status",         help="Show config and runtime status")

    p_serve = sub.add_parser("serve", help="Open web UI in browser (http://localhost:7337)")
    p_serve.add_argument("--port", type=int, default=7337)
    p_serve.add_argument("--host", type=str, default="127.0.0.1")

    p_agent = sub.add_parser("agent", help="Chat with the agent in the terminal")
    p_agent.add_argument("-m", "--message", type=str, metavar="TEXT")
    p_agent.add_argument("--no-stream", action="store_true")

    args = parser.parse_args()

    cmds = {
        "onboard":        cmd_onboard,
        "setup-telegram": cmd_setup_telegram,
        "serve":          cmd_serve,
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
