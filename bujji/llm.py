"""
bujji/llm.py
LLMProvider — OpenAI-compatible chat completions with streaming.
All providers (OpenAI, Anthropic, Google, Mistral, Groq, etc.) use the same
/chat/completions endpoint pattern; only the base URL and auth header differ.
"""

import json
import sys
import time

# ── Retry configuration ───────────────────────────────────────────────────────
# Retries on transient HTTP errors (429 rate-limit, 5xx server errors).
# Uses exponential back-off: 2s → 4s → 8s.  No new dependencies needed.
_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES        = 3
_BACKOFF_BASE       = 2   # seconds

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


class LLMProvider:
    """
    Thin wrapper around any OpenAI-compatible /v1/chat/completions endpoint.

    Usage:
        llm = LLMProvider("groq", api_key, "https://api.groq.com/openai/v1",
                          "llama3-8b-8192")
        response = llm.chat(messages, tools=tool_schema, stream=True)
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

    # ── Public API ────────────────────────────────────────────────────────

    def chat(
        self,
        messages: list,
        tools:    list  = None,
        stream:   bool  = False,
    ) -> dict:
        """
        Send a chat request.  Returns a dict shaped like an OpenAI response:
          {"choices": [{"message": {...}, "finish_reason": "..."}]}
        When stream=True tokens are printed to stdout as they arrive,
        and the same dict is returned once the stream is exhausted.
        """
        if not _HAS_REQUESTS:
            raise RuntimeError(
                "requests library is required.\n"
                "Install it with: pip install requests"
            )

        headers = self._build_headers()
        payload = self._build_payload(messages, tools, stream)
        url     = f"{self.api_base}/chat/completions"
        resp    = self._post_with_retry(url, headers, payload, stream)

        return self._collect_stream(resp) if stream else resp.json()

    # ── Private helpers ───────────────────────────────────────────────────

    def _build_headers(self) -> dict:
        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        # Anthropic uses a different auth scheme
        if self.name == "anthropic":
            headers["x-api-key"]         = self.api_key
            headers["anthropic-version"] = "2023-06-01"
        return headers

    def _post_with_retry(self, url: str, headers: dict, payload: dict, stream: bool):
        """
        POST with exponential back-off for transient errors.

        Retries up to _MAX_RETRIES times on:
          - Connection errors  (network blip)
          - 429 rate-limit     (back off and retry)
          - 5xx server errors  (upstream hiccup)

        Back-off schedule: 2s → 4s → 8s  (no new dependencies, just time.sleep).
        """
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
                    f"Check your API base URL and internet connection."
                )
                if attempt < _MAX_RETRIES:
                    wait = _BACKOFF_BASE ** (attempt + 1)
                    print(
                        f"[WARN] Connection error (attempt {attempt + 1}/{_MAX_RETRIES}), "
                        f"retrying in {wait}s…",
                        file=sys.stderr,
                    )
                    time.sleep(wait)
                continue

            # Successful connection — check HTTP status
            if resp.status_code not in _RETRY_STATUS_CODES:
                if not resp.ok:
                    raise RuntimeError(
                        f"API error {resp.status_code}: {resp.text[:400]}"
                    )
                return resp   # ← happy path

            # Retryable HTTP error
            last_exc = RuntimeError(
                f"API error {resp.status_code}: {resp.text[:400]}"
            )
            if attempt < _MAX_RETRIES:
                wait = _BACKOFF_BASE ** (attempt + 1)
                print(
                    f"[WARN] HTTP {resp.status_code} (attempt {attempt + 1}/{_MAX_RETRIES}), "
                    f"retrying in {wait}s…",
                    file=sys.stderr,
                )
                time.sleep(wait)

        raise last_exc or RuntimeError("All retry attempts failed.")

    def _build_payload(self, messages, tools, stream) -> dict:
        payload: dict = {
            "model":       self.model,
            "messages":    messages,
            "max_tokens":  self.max_tokens,
            "temperature": self.temperature,
            "stream":      stream,
        }
        if tools:
            payload["tools"]       = tools
            payload["tool_choice"] = "auto"
        return payload

    def _collect_stream(self, response) -> dict:
        """
        Consume a Server-Sent Events stream.
        Tokens are printed live to stdout.
        Returns a synthetic non-streamed response dict when done.
        """
        full_content   = ""
        tool_calls_raw: dict[int, dict] = {}
        finish_reason  = None

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

                # ── Text token ──
                token = delta.get("content")
                if token:
                    print(token, end="", flush=True)
                    full_content += token

                # ── Tool-call delta ──
                for tc in delta.get("tool_calls", []):
                    idx = tc.get("index", 0)
                    if idx not in tool_calls_raw:
                        tool_calls_raw[idx] = {
                            "id":   "",
                            "type": "function",
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

        if full_content:
            print()  # newline after streamed tokens

        msg: dict = {"role": "assistant", "content": full_content or None}
        if tool_calls_raw:
            msg["tool_calls"] = [tool_calls_raw[i] for i in sorted(tool_calls_raw)]

        return {
            "choices": [{
                "message":       msg,
                "finish_reason": finish_reason or "stop",
            }]
        }