"""
bujji/config.py
Config loading, saving, defaults, and provider registry.
"""

import copy
import json
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
#  PATHS
# ─────────────────────────────────────────────────────────────────────────────

CONFIG_DIR        = Path.home() / ".bujji"
CONFIG_FILE       = CONFIG_DIR / "config.json"
WORKSPACE_DEFAULT = CONFIG_DIR / "workspace"

# ─────────────────────────────────────────────────────────────────────────────
#  DEFAULT CONFIG SCHEMA
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "agents": {
        "defaults": {
            "workspace":             str(WORKSPACE_DEFAULT),
            "model":                 "",
            "max_tokens":            8192,
            "temperature":           0.7,
            "max_tool_iterations":   20,
            "restrict_to_workspace": False,
        }
    },
    "providers": {},
    "channels": {
        "telegram": {"enabled": False, "token": "", "allow_from": []},
        "discord":  {"enabled": False, "token": "", "allow_from": []},
    },
    "tools": {
        "web": {
            "search": {"api_key": "", "max_results": 5}
        }
    },
}

# ─────────────────────────────────────────────────────────────────────────────
#  PROVIDER REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

# name -> (api_base_url, default_model)
PROVIDER_DEFAULTS = {
    "openrouter": ("https://openrouter.ai/api/v1",                            "openai/gpt-4o-mini"),
    "openai":     ("https://api.openai.com/v1",                               "gpt-4o-mini"),
    "anthropic":  ("https://api.anthropic.com/v1",                            "claude-3-haiku-20240307"),
    "groq":       ("https://api.groq.com/openai/v1",                         "llama3-8b-8192"),
    "google":     ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.0-flash"),
    "mistral":    ("https://api.mistral.ai/v1",                               "mistral-small-latest"),
    "zhipu":      ("https://open.bigmodel.cn/api/paas/v4",                   "glm-4-flash"),
    "deepseek":   ("https://api.deepseek.com/v1",                            "deepseek-chat"),
    "ollama":     ("http://localhost:11434/v1",                               "llama3.2"),
}

# Popular model suggestions shown during onboard
POPULAR_MODELS = {
    "google": [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-pro",
        "gemini-2.5-pro-preview-03-25",
    ],
    "mistral": [
        "mistral-small-latest",
        "mistral-medium-latest",
        "mistral-large-latest",
        "codestral-latest",
        "open-mistral-nemo",
    ],
    "openrouter": [
        "openai/gpt-4o-mini",
        "anthropic/claude-3-5-haiku",
        "google/gemini-2.0-flash",
        "mistralai/mistral-small",
        "meta-llama/llama-3.1-8b-instruct:free",
    ],
    "groq": [
        "llama3-8b-8192",
        "llama-3.1-70b-versatile",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
    ],
    "anthropic": [
        "claude-3-haiku-20240307",
        "claude-3-5-haiku-20241022",
        "claude-3-5-sonnet-20241022",
        "claude-opus-4-5-20251101",
    ],
    "openai": [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4-turbo",
        "o1-mini",
    ],
    "deepseek": [
        "deepseek-chat",
        "deepseek-reasoner",
    ],
    "ollama": [
        "llama3.2",
        "llama3.1",
        "mistral",
        "gemma2",
        "qwen2.5",
        "phi3",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
#  LOAD / SAVE
# ─────────────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load config from disk, deep-merging with defaults for missing keys."""
    if not CONFIG_FILE.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    with open(CONFIG_FILE, encoding="utf-8") as f:
        on_disk = json.load(f)
    merged = copy.deepcopy(DEFAULT_CONFIG)
    _deep_merge(merged, on_disk)
    return merged


def save_config(cfg: dict) -> None:
    """Persist config to ~/.bujji/config.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def _deep_merge(base: dict, override: dict) -> None:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_active_provider(cfg: dict):
    """
    Return (provider_name, api_key, api_base, model) for the first
    fully-configured provider, or (None, None, None, None) if none found.
    """
    model_override = cfg["agents"]["defaults"].get("model", "")
    for pname, pconf in cfg.get("providers", {}).items():
        api_key = pconf.get("api_key", "")
        if not api_key:
            continue
        fallback_base, fallback_model = PROVIDER_DEFAULTS.get(pname, ("", ""))
        api_base = pconf.get("api_base", fallback_base)
        if not api_base:
            continue
        model = model_override or pconf.get("model", fallback_model)
        return pname, api_key, api_base, model
    return None, None, None, None


def workspace_path(cfg: dict) -> Path:
    ws = cfg["agents"]["defaults"].get("workspace", str(WORKSPACE_DEFAULT))
    return Path(ws).expanduser()