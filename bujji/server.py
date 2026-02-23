from __future__ import annotations

"""
bujji/server.py  —  v2.1

Full config sync: every field in config.json is readable and writable
from the web UI — providers, channels (Telegram/Discord), tools, workspace.

Endpoints
─────────
GET  /                         → ui/index.html
GET  /api/config               → masked config (for display)
GET  /api/config/raw           → full config with real keys (populates forms)
POST /api/config               → deep-merge + save any config fields
POST /api/config/test-telegram → verify a Telegram bot token live
POST /api/config/test-llm      → ping LLM provider
GET  /api/status               → health summary
GET  /api/memory               → USER.md
POST /api/memory               → save USER.md
GET  /api/skills               → list skills
GET  /api/tools                → active tools
POST /api/chat                 → SSE streaming chat
POST /api/clear                → clear session history
"""

import json
import queue
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from bujji.config import (
    CONFIG_FILE, PROVIDER_DEFAULTS, get_active_provider,
    load_config, save_config, workspace_path,
)
from bujji.session import SessionManager

_UI_DIR = Path(__file__).parent.parent / "ui"

_cfg: dict = {}
_mgr: Optional[SessionManager] = None


def _deep_merge(base: dict, override: dict) -> None:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def _mask_config(cfg: dict) -> dict:
    import copy
    s = copy.deepcopy(cfg)
    for pname, pcfg in s.get("providers", {}).items():
        key = pcfg.get("api_key", "")
        if key and key not in ("ollama", ""):
            s["providers"][pname]["api_key"] = key[:8] + "…" if len(key) > 8 else "…"
    tg = s.get("channels", {}).get("telegram", {})
    if tg.get("token"):
        t = tg["token"]
        s["channels"]["telegram"]["token"] = t[:10] + "…" if len(t) > 10 else "…"
    dc = s.get("channels", {}).get("discord", {})
    if dc.get("token"):
        t = dc["token"]
        s["channels"]["discord"]["token"] = t[:10] + "…" if len(t) > 10 else "…"
    brave = s.get("tools", {}).get("web", {}).get("search", {}).get("api_key", "")
    if brave:
        s["tools"]["web"]["search"]["api_key"] = brave[:6] + "…"
    return s


def _strip_masked(obj, depth=0):
    """Remove values containing '…' so masked display values never overwrite real keys."""
    if not isinstance(obj, dict) or depth > 8:
        return
    for k in list(obj.keys()):
        v = obj[k]
        if isinstance(v, str) and "…" in v:
            del obj[k]
        elif isinstance(v, dict):
            _strip_masked(v, depth + 1)


class BujjiHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        code = str(args[1]) if len(args) > 1 else ""
        if code not in ("200", "204"):
            sys.stderr.write(f"[HTTP {code}] {args[0]}\n")

    def do_GET(self):
        path = urlparse(self.path).path
        routes = {
            "/":               self._serve_ui,
            "/api/status":     self._get_status,
            "/api/config":     self._get_config,
            "/api/config/raw": self._get_config_raw,
            "/api/memory":     self._get_memory,
            "/api/skills":     self._get_skills,
            "/api/tools":      self._get_tools,
        }
        fn = routes.get(path)
        if fn:
            try:
                fn()
            except Exception:
                self._send_error(500, traceback.format_exc())
        elif path.startswith("/ui/"):
            self._serve_static(path[4:])
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()
        routes = {
            "/api/config":               lambda: self._post_config(body),
            "/api/config/test-telegram": lambda: self._post_test_telegram(body),
            "/api/config/test-llm":      lambda: self._post_test_llm(body),
            "/api/memory":               lambda: self._post_memory(body),
            "/api/chat":                 lambda: self._post_chat(body),
            "/api/clear":                lambda: self._post_clear(body),
            "/api/skills":               lambda: self._post_skill(body),
            "/api/skills/update":        lambda: self._put_skill(body),
            "/api/skills/delete":        lambda: self._delete_skill(body),
        }
        fn = routes.get(path)
        if fn:
            try:
                fn()
            except Exception:
                self._send_error(500, traceback.format_exc())
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    # ── GET ───────────────────────────────────────────────────────────────

    def _serve_ui(self):
        f = _UI_DIR / "index.html"
        if not f.exists():
            self._send_text("ui/index.html not found", 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self._cors()
        self.end_headers()
        self.wfile.write(f.read_bytes())

    def _serve_static(self, rel):
        target = (_UI_DIR / rel).resolve()
        if not str(target).startswith(str(_UI_DIR.resolve())):
            self._send_error(403, "Forbidden")
            return
        if not target.exists():
            self._send_error(404, "Not found")
            return
        ct = {".js": "application/javascript", ".css": "text/css",
              ".png": "image/png", ".ico": "image/x-icon"}.get(target.suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self._cors()
        self.end_headers()
        self.wfile.write(target.read_bytes())

    def _get_status(self):
        pname, api_key, api_base, model = get_active_provider(_cfg)
        ws    = workspace_path(_cfg)
        tg    = _cfg.get("channels", {}).get("telegram", {})
        dc    = _cfg.get("channels", {}).get("discord",  {})
        brave = _cfg.get("tools", {}).get("web", {}).get("search", {}).get("api_key", "")
        tools = []
        try:
            from bujji.tools import ToolRegistry
            tools = [s["function"]["name"] for s in ToolRegistry(_cfg).schema()]
        except Exception:
            pass
        self._send_json({
            "configured": bool(pname),
            "provider":   pname or "",
            "model":      model or "",
            "api_base":   api_base or "",
            "workspace":  str(ws),
            "ws_exists":  ws.exists(),
            "tools":      tools,
            "web_search": bool(brave),
            "telegram": {
                "enabled":    tg.get("enabled", False),
                "has_token":  bool(tg.get("token", "")),
                "allow_from": tg.get("allow_from", []),
            },
            "discord": {
                "enabled":    dc.get("enabled", False),
                "has_token":  bool(dc.get("token", "")),
                "allow_from": dc.get("allow_from", []),
            },
        })

    def _get_config(self):
        self._send_json(_mask_config(_cfg))

    def _get_config_raw(self):
        """Unmasked — used to pre-fill form fields."""
        self._send_json(_cfg)

    def _get_memory(self):
        path = workspace_path(_cfg) / "USER.md"
        self._send_text(path.read_text(encoding="utf-8") if path.exists() else "")

    def _get_skills(self):
        ws  = workspace_path(_cfg)
        out = []
        sd  = ws / "skills"
        if sd.exists():
            for f in sorted(sd.glob("*/SKILL.md")):
                try:
                    out.append({"name": f.parent.name, "content": f.read_text(encoding="utf-8"), "path": str(f)})
                except Exception:
                    pass
        self._send_json(out)

    def _get_tools(self):
        try:
            from bujji.tools import ToolRegistry
            tools = [{"name": s["function"]["name"], "description": s["function"]["description"]}
                     for s in ToolRegistry(_cfg).schema()]
            self._send_json(tools)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    # ── POST ──────────────────────────────────────────────────────────────

    def _post_config(self, body: dict):
        global _cfg, _mgr
        # Never overwrite real keys with masked display values
        _strip_masked(body)
        _deep_merge(_cfg, body)
        save_config(_cfg)
        _mgr = SessionManager(_cfg)
        self._send_json({"ok": True})

    def _post_test_telegram(self, body: dict):
        token = body.get("token", "").strip()
        if not token:
            self._send_json({"ok": False, "error": "No token provided"})
            return
        try:
            import requests
            r    = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=8)
            data = r.json()
            if data.get("ok"):
                bot = data["result"]
                self._send_json({"ok": True, "username": bot.get("username"), "name": bot.get("first_name")})
            else:
                self._send_json({"ok": False, "error": data.get("description", "Invalid token")})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)})

    def _post_test_llm(self, body: dict):
        pname, api_key, api_base, model = get_active_provider(_cfg)
        if not pname:
            self._send_json({"ok": False, "error": "No provider configured"})
            return
        try:
            from bujji.llm import LLMProvider
            llm  = LLMProvider(pname, api_key, api_base, model, max_tokens=8)
            resp = llm.chat([{"role": "user", "content": "say hi"}], stream=False)
            preview = (resp.get("choices", [{}])[0].get("message", {}).get("content") or "")[:80]
            self._send_json({"ok": True, "model": model, "preview": preview})
        except Exception as e:
            self._send_json({"ok": False, "error": str(e)})

    def _post_memory(self, body: dict):
        ws = workspace_path(_cfg)
        ws.mkdir(parents=True, exist_ok=True)
        content = body.get("content", "")
        tmp = ws / "USER.tmp"
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(ws / "USER.md")
        self._send_json({"ok": True, "bytes": len(content)})

    def _post_clear(self, body: dict):
        sid = body.get("session_id", "web:default")
        if _mgr:
            _mgr.clear(sid)
        self._send_json({"ok": True})

    def _post_skill(self, body: dict):
        """Create a new skill — POST /api/skills"""
        name    = (body.get("name") or "").strip().replace(" ", "-").lower()
        content = (body.get("content") or "").strip()
        if not name:
            self._send_json({"ok": False, "error": "Skill name is required"}, 400)
            return
        if not content:
            self._send_json({"ok": False, "error": "Skill content is required"}, 400)
            return
        ws         = workspace_path(_cfg)
        skill_dir  = ws / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            self._send_json({
                "ok": False,
                "error": f"Skill '{name}' already exists. Use update to edit it."
            }, 409)
            return
        skill_file.write_text(content, encoding="utf-8")
        self._send_json({"ok": True, "name": name, "path": str(skill_file)})

    def _put_skill(self, body: dict):
        """Update an existing skill — POST /api/skills/update"""
        name    = (body.get("name") or "").strip()
        content = (body.get("content") or "").strip()
        if not name or not content:
            self._send_json({"ok": False, "error": "name and content required"}, 400)
            return
        ws         = workspace_path(_cfg)
        skill_file = ws / "skills" / name / "SKILL.md"
        if not skill_file.exists():
            self._send_json({"ok": False, "error": f"Skill '{name}' not found"}, 404)
            return
        skill_file.write_text(content, encoding="utf-8")
        self._send_json({"ok": True, "name": name})

    def _delete_skill(self, body: dict):
        """Delete a skill directory — POST /api/skills/delete"""
        import shutil
        name = (body.get("name") or "").strip()
        if not name:
            self._send_json({"ok": False, "error": "name required"}, 400)
            return
        ws        = workspace_path(_cfg)
        skill_dir = ws / "skills" / name
        if not skill_dir.exists():
            self._send_json({"ok": False, "error": f"Skill '{name}' not found"}, 404)
            return
        shutil.rmtree(skill_dir)
        self._send_json({"ok": True, "name": name})

    def _post_chat(self, body: dict):
        message    = (body.get("message") or "").strip()
        session_id = body.get("session_id") or "web:default"
        if not message:
            self._send_json({"error": "Empty message"}, 400)
            return

        self.send_response(200)
        self.send_header("Content-Type",      "text/event-stream")
        self.send_header("Cache-Control",     "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self._cors()
        self.end_headers()

        q: queue.Queue = queue.Queue()

        def emit(evt: dict):
            try:
                self.wfile.write(f"data: {json.dumps(evt)}\n\n".encode())
                self.wfile.flush()
            except Exception:
                pass

        callbacks = {
            "on_token":      lambda t:    q.put({"type": "token",      "content": t}),
            "on_tool_start": lambda n, a: q.put({"type": "tool_start", "name": n, "args": a}),
            "on_tool_done":  lambda n, r: q.put({"type": "tool_done",  "name": n,
                                                  "result": r[:600] + ("…" if len(r) > 600 else "")}),
            "on_error":      lambda e:    q.put({"type": "error",      "content": e}),
        }

        final: list[str] = []

        def run():
            try:
                agent   = _mgr.get(session_id, callbacks=callbacks)
                history = _mgr.history(session_id)
                result  = agent.run(message, history=history, stream=True)
                final.append(result or "")
            except Exception as e:
                q.put({"type": "error", "content": str(e)})
            finally:
                q.put(None)

        threading.Thread(target=run, daemon=True).start()

        while True:
            item = q.get()
            if item is None:
                break
            emit(item)

        reply = "".join(final)
        _mgr.append(session_id, "user",      message)
        _mgr.append(session_id, "assistant", reply)
        emit({"type": "done", "content": reply})

    # ── Helpers ───────────────────────────────────────────────────────────

    def _read_body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        if n == 0:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except Exception:
            return {}

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text, status=200):
        body = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status, msg):
        self._send_json({"error": msg}, status)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def run_server(cfg: dict, host: str = "127.0.0.1", port: int = 7337) -> None:
    global _cfg, _mgr
    _cfg = cfg
    _mgr = SessionManager(cfg)

    server = HTTPServer((host, port), BujjiHandler)
    url    = f"http://{host}:{port}"

    print(f"\n🦞 bujji web UI  →  {url}")
    print("   Press Ctrl+C to stop.\n")

    try:
        import webbrowser, threading as _t
        _t.Timer(0.6, lambda: webbrowser.open(url)).start()
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🦞 Stopped.")
        server.server_close()