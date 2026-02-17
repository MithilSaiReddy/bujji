"""
bujji/agent.py
AgentLoop — the core agentic reasoning + tool-use loop.
HeartbeatService — runs HEARTBEAT.md tasks on a schedule.
CronService — runs workspace/cron/jobs.json tasks on a schedule.
"""

import datetime
import json
import sys
import textwrap
import threading
from pathlib import Path

from bujji.config import get_active_provider, workspace_path
from bujji.llm    import LLMProvider
from bujji.tools  import ToolRegistry

LOGO = "🦞"


# ─────────────────────────────────────────────────────────────────────────────
#  SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

def _load_skills(workspace: Path) -> str:
    """Load all SKILL.md files from workspace/skills/*/SKILL.md."""
    skills_dir = workspace / "skills"
    if not skills_dir.exists():
        return ""
    parts = []
    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        try:
            content = skill_file.read_text(encoding="utf-8", errors="replace")
            parts.append(f"## Skill: {skill_file.parent.name}\n{content}")
        except Exception:
            pass
    return "\n\n".join(parts)


def build_system_prompt(cfg: dict) -> str:
    ws     = workspace_path(cfg)
    skills = _load_skills(ws)

    prompt = textwrap.dedent(f"""
        You are bujji, an ultra-lightweight personal AI assistant.
        Your workspace is: {ws}

        You are helpful, concise, and efficient. You have access to tools for:
        - Searching the web (Brave Search API)
        - Reading, writing, listing, and deleting files
        - Executing shell commands
        - Getting the current date and time
        - Sending messages to the user (via the 'message' tool — for scheduled tasks)

        Use tools when needed. After receiving tool results synthesize them into a
        clear, concise answer. Prefer action over lengthy explanation.
        Always complete the task before summarising for the user.
    """).strip()

    if skills:
        prompt += f"\n\n# Available Skills\n{skills}"

    return prompt


# ─────────────────────────────────────────────────────────────────────────────
#  AGENT LOOP
# ─────────────────────────────────────────────────────────────────────────────

class AgentLoop:
    """
    Core agentic loop:
    1. Send user message + history to LLM.
    2. If LLM requests tool calls, execute them and loop back.
    3. When LLM produces a plain text response, return it.
    """

    def __init__(self, cfg: dict, send_message_fn=None):
        self.cfg      = cfg
        defaults      = cfg["agents"]["defaults"]
        self.max_iter = defaults.get("max_tool_iterations", 20)

        pname, api_key, api_base, model = get_active_provider(cfg)
        if not pname:
            raise RuntimeError(
                "No LLM provider configured.\n"
                "Run: python main.py onboard\n"
                "Or edit ~/.bujji/config.json and add a provider with an api_key."
            )

        self.llm = LLMProvider(
            name=pname, api_key=api_key, api_base=api_base, model=model,
            max_tokens=defaults.get("max_tokens", 8192),
            temperature=defaults.get("temperature", 0.7),
        )
        self.tools         = ToolRegistry(cfg, send_message_fn=send_message_fn)
        self.system_prompt = build_system_prompt(cfg)

        print(
            f"[INFO] Agent ready — provider={pname}, model={model}, "
            f"tools={len(self.tools.schema())}",
            file=sys.stderr,
        )

    def run(
        self,
        user_message: str,
        history:      list = None,
        stream:       bool = True,
    ) -> str:
        """
        Execute one conversational turn.
        Returns the final text response (may be empty if it was streamed).
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        tools_schema = self.tools.schema()
        first_call   = True

        for _ in range(self.max_iter):
            use_stream = stream and first_call
            resp       = self.llm.chat(messages, tools=tools_schema, stream=use_stream)
            first_call = False

            choice     = resp["choices"][0]
            msg        = choice["message"]
            messages.append(msg)
            tool_calls = msg.get("tool_calls") or []

            if tool_calls:
                # ── Execute every requested tool ──
                for tc in tool_calls:
                    fn   = tc["function"]
                    name = fn["name"]
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}

                    preview_args = json.dumps(args, ensure_ascii=False)[:100]
                    print(f"\n{LOGO} [Tool] {name}({preview_args})", file=sys.stderr)

                    result  = self.tools.call(name, args)
                    preview = str(result)[:180].replace("\n", " ")
                    print(f"  → {preview}", file=sys.stderr)

                    messages.append({
                        "role":         "tool",
                        "tool_call_id": tc.get("id", "t0"),
                        "content":      str(result),
                    })
                # Loop back → let LLM see the tool results

            else:
                # ── Final text response ──
                final = (msg.get("content") or "").strip()
                if not final and use_stream:
                    return ""   # already streamed to stdout
                if final and not use_stream:
                    print(f"\n{LOGO}: {final}")
                return final

        return "[Max tool iterations reached]"


# ─────────────────────────────────────────────────────────────────────────────
#  HEARTBEAT
# ─────────────────────────────────────────────────────────────────────────────

class HeartbeatService:
    """
    Periodically reads workspace/HEARTBEAT.md and runs its contents as an
    agent prompt.  Create HEARTBEAT.md with plain-English task descriptions
    and bujji will execute them on schedule.

    Example HEARTBEAT.md:
        - Check disk space and warn if above 90 %
        - Append today's date to journal.md
    """

    def __init__(self, agent: AgentLoop, workspace: Path, interval_minutes: int = 30):
        self.agent    = agent
        self.hb_file  = workspace / "HEARTBEAT.md"
        self.interval = interval_minutes * 60
        self._stop    = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True).start()
        print(
            f"[INFO] Heartbeat started — interval={self.interval // 60}min, "
            f"file={self.hb_file}",
            file=sys.stderr,
        )

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            if not self.hb_file.exists():
                continue
            try:
                content = self.hb_file.read_text(encoding="utf-8")
                prompt  = (
                    "[HEARTBEAT] Please execute the periodic tasks listed in "
                    f"HEARTBEAT.md:\n\n{content}\n\n"
                    "Reply HEARTBEAT_OK when all tasks are complete."
                )
                print(f"\n{LOGO} [Heartbeat] Running periodic tasks...", file=sys.stderr)
                self.agent.run(prompt, stream=False)
            except Exception as e:
                print(f"[WARN] Heartbeat error: {e}", file=sys.stderr)

    def stop(self) -> None:
        self._stop.set()


# ─────────────────────────────────────────────────────────────────────────────
#  CRON
# ─────────────────────────────────────────────────────────────────────────────

class CronService:
    """
    Simple cron runner.  Reads workspace/cron/jobs.json every minute and
    fires any job whose interval has elapsed.

    jobs.json format:
    [
      {
        "name":             "daily-news",
        "prompt":           "Search for today's top AI news and save to news.md",
        "interval_minutes": 1440,
        "last_run":         null
      }
    ]
    """

    def __init__(self, agent: AgentLoop, workspace: Path):
        self.agent     = agent
        self.jobs_file = workspace / "cron" / "jobs.json"
        self._stop     = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self) -> None:
        while not self._stop.wait(60):   # check every minute
            if not self.jobs_file.exists():
                continue
            try:
                jobs    = json.loads(self.jobs_file.read_text(encoding="utf-8"))
                now     = datetime.datetime.now()
                changed = False

                for job in jobs:
                    if self._should_run(job, now):
                        print(f"[Cron] Running: {job.get('name', 'unnamed')}", file=sys.stderr)
                        self.agent.run(job["prompt"], stream=False)
                        job["last_run"] = now.isoformat()
                        changed = True

                if changed:
                    self.jobs_file.write_text(json.dumps(jobs, indent=2), encoding="utf-8")

            except Exception as e:
                print(f"[WARN] Cron error: {e}", file=sys.stderr)

    def _should_run(self, job: dict, now: datetime.datetime) -> bool:
        last_run = job.get("last_run")
        if not last_run:
            return True
        try:
            last = datetime.datetime.fromisoformat(last_run)
            return (now - last).total_seconds() >= job.get("interval_minutes", 60) * 60
        except Exception:
            return False

    def stop(self) -> None:
        self._stop.set()