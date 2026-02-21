"""
bujji/llm.py  —  v2

LLMProvider — OpenAI-compatible /v1/chat/completions with:
• token_cb   : callback for streamed tokens instead of print-to-stdout
              → decouples the LLM from the output channel (CLI / web UI / tests)
• Exponential back-off retry: 2s → 4s → 8s on 429 / 5xx / connection errors
• Anthropic auth handled transparently
"""
from __future__ import annotations

import json
import sys
import time
from typing import Callable, Optional

_RETRY_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES  = 3
_BACKOFF_BASE = 2

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

class LLMProvider:
    """
    Thin wrapper around any OpenAI-compatible /v1/chat/completions endpoint.

    Parameters
    ──────────
    token_cb : optional callable(str) — receives each streamed token.
               If None, tokens are printed to stdout (original CLI behaviour).
    """

    def __init__(
        self,
        name:        str,
        api_key:     str,
        api_base:    str,
        model:       str,
        max_tokens:  int   = 8192,
        temperature: float = 0.7,
    ):
        self.name        = name
        self.api_key     = api_key
        self.api_base    = api_base.rstrip("/")
        self.model       = model
        self.max_tokens  = max_tokens
        self.temperature = temperature

    # ── Public ────────────────────────────────────────────────────────────

    def chat(
        self,
        messages: list,
        tools:    Optional[list]              = None,
        stream:   bool                        = False,
        token_cb: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """
        Send a chat request.

        If stream=True:
          • Calls token_cb(token) for each token (if provided)
          • Falls back to print(token) if token_cb is None
        Returns a synthetic dict shaped like a non-streamed OpenAI response.
        """
        if not _HAS_REQUESTS:
            raise RuntimeError("requests not installed — run: pip install requests")

        url     = f"{self.api_base}/chat/completions"
        headers = self._build_headers()
        payload = self._build_payload(messages, tools, stream)
        resp    = self._post_with_retry(url, headers, payload, stream)

        if stream:
            return self._collect_stream(resp, token_cb=token_cb)
        return resp.json()

    # ── Private ───────────────────────────────────────────────────────────

    def _build_headers(self) -> dict:
        h = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if self.name == "anthropic":
            h["x-api-key"]         = self.api_key
            h["anthropic-version"] = "2023-06-01"
        return h

    def _build_payload(self, messages, tools, stream) -> dict:
        p: dict = {
            "model":       self.model,
            "messages":    messages,
            "max_tokens":  self.max_tokens,
            "temperature": self.temperature,
            "stream":      stream,
        }
        if tools:
            p["tools"]       = tools
            p["tool_choice"] = "auto"
        return p

    def _post_with_retry(self, url, headers, payload, stream):
        last_exc = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = _requests.post(
                    url, headers=headers, json=payload,
                    timeout=120, stream=stream,
                )
            except _requests.exceptions.ConnectionError as e:
                last_exc = RuntimeError(
                    f"Cannot connect to {url}.\n"
                    "Check your API base URL and network connection."
                )
                if attempt < _MAX_RETRIES:
                    wait = _BACKOFF_BASE ** (attempt + 1)
                    print(
                        f"[WARN] Connection error (attempt {attempt+1}/{_MAX_RETRIES}), "
                        f"retrying in {wait}s…",
                        file=sys.stderr,
                    )
                    time.sleep(wait)
                continue

            if resp.status_code not in _RETRY_STATUS:
                if not resp.ok:
                    try:
                        body = resp.json()
                        msg  = body.get("error", {}).get("message", resp.text[:400])
                    except Exception:
                        msg  = resp.text[:400]
                    raise RuntimeError(f"API error {resp.status_code}: {msg}")
                return resp

            last_exc = RuntimeError(f"API error {resp.status_code}: {resp.text[:200]}")
            if attempt < _MAX_RETRIES:
                wait = _BACKOFF_BASE ** (attempt + 1)
                print(
                    f"[WARN] HTTP {resp.status_code} (attempt {attempt+1}/{_MAX_RETRIES}), "
                    f"retrying in {wait}s…",
                    file=sys.stderr,
                )
                time.sleep(wait)

        raise last_exc or RuntimeError("All retry attempts failed.")

    def _collect_stream(
        self,
        response,
        token_cb: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """Consume SSE stream, emit tokens via callback (or stdout), return synthetic dict."""
        full_content:   str            = ""
        tool_calls_raw: dict[int, dict] = {}
        finish_reason:  Optional[str]   = None

        for raw_line in response.iter_lines():
            if not raw_line:
                continue
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            if line.startswith("data: "):
                line = line[6:]
            if line == "[DONE]":
                break

            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue

            for choice in chunk.get("choices", []):
                delta = choice.get("delta", {})

                token = delta.get("content")
                if token:
                    full_content += token
                    if token_cb:
                        token_cb(token)
                    else:
                        print(token, end="", flush=True)

                for tc in delta.get("tool_calls", []):
                    idx = tc.get("index", 0)
                    if idx not in tool_calls_raw:
                        tool_calls_raw[idx] = {
                            "id": "", "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    if tc.get("id"):
                        tool_calls_raw[idx]["id"] = tc["id"]
                    fn = tc.get("function", {})
                    if fn.get("name"):
                        tool_calls_raw[idx]["function"]["name"] += fn["name"]
                    if fn.get("arguments"):
                        tool_calls_raw[idx]["function"]["arguments"] += fn["arguments"]

                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]

        if full_content and not token_cb:
            print()  # newline after stdout streaming

        msg: dict = {"role": "assistant", "content": full_content or None}
        if tool_calls_raw:
            msg["tool_calls"] = [tool_calls_raw[i] for i in sorted(tool_calls_raw)]

        return {
            "choices": [{"message": msg, "finish_reason": finish_reason or "stop"}]
        }
